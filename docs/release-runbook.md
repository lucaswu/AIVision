# AIVision 发布手册

- **版本**：v2（含模型交付运行时）
- **基准提交**：`3ce884e4ff6aa0a52e211a0050d8c3b31141b69b`
- **更新日期**：2026-08-15

自 `3ce884e` 起，"发布"分成了两条相互独立的线：**代码/镜像发布**（backend、frontend、ai-inference、model-agent 四个镜像，走原来 rebuild → push → pull 那一套，现补上了 model-agent）和**模型权重发布**（不再需要重建镜像或重启容器，改为对已运行的推理服务发起签名包安装 + 激活）。这份手册按这两条线分别给出可直接执行的步骤。

代码是唯一真实来源，如与本手册冲突以代码为准。

---

## 目录

0. [总览：两条发布线](#0-总览两条发布线)
1. [一次性环境初始化](#1-一次性环境初始化每台新推理机只做一次)
2. [.env 配置清单](#2-env-需要新增的内容)
3. [代码 / 镜像发布](#3-代码--镜像发布线路-a)
4. [制作签名模型包](#4-制作签名模型包线路-b--第一步)
5. [模型更新（安装 + 激活）](#5-模型更新安装--激活线路-b--第二步)
6. [模型回滚](#6-模型回滚线路-b--应急)
7. [发布后核对清单](#7-发布后核对清单)
8. [已知缺口](#8-已知缺口)

---

## 0. 总览：两条发布线

先分清楚这次要发的是"代码"还是"模型"——它们走完全不同的流程，混着做会误判影响面。

| | 线路 A：代码 / 镜像发布 | 线路 B：模型权重发布 |
|---|---|---|
| **触发条件** | 后端 API、前端、推理服务代码逻辑、model-agent 代码本身发生变化 | 只是换一版检测模型权重（ROI / 主检测 / 位置 / 方向矫正等），代码不变 |
| **怎么做** | rebuild → push → pull → `docker compose up -d` | model-agent 的 `/models/install` + `/models/activate` |
| **影响面** | 会重启 `ai-inference` 容器（在途推理任务中断），需要选低峰期 | 容器不重启，正在跑的推理任务用旧模型跑完，新任务用新模型；仅新提交请求在切换的短窗口内可能收到 409 需重试 |

```
1. rebuild.sh          本地构建 4 个镜像
2. push.sh TAG          推到阿里云镜像仓库
3. pull.sh TAG          部署机拉取
4. compose up -d        重启受影响容器
5. install + activate   模型权重单独热更新（独立于 1-4，不必等镜像发布窗口）
```

---

## 1. 一次性环境初始化（每台新推理机只做一次）

这些不是每次发布都要做的事，是给一台全新的推理机（或者轮换密钥时）做的准备工作。当前这台机器已经在 2026-08-13 做过一轮。

### 1.1 mTLS 证书（保护控制面）

放在 `deploy/model-mtls/`，供 `ai-inference` 的 9443 控制端口和 model-agent 的出站客户端证书使用：

| 文件 | 用途 |
|---|---|
| `ca.crt` / `ca.key` | 自签 CA，签发下面两张证书 |
| `inference.crt` / `inference.key` | ai-inference 9443 端口的服务端证书，CN 必须是 `ai-inference` |
| `agent.crt` / `agent.key` | model-agent 的客户端证书，同一 CA 签发 |

生成方式（仅首次或证书到期轮换时执行，在 `deploy/model-mtls/` 目录下）：

```bash
openssl genrsa -out ca.key 2048
openssl req -x509 -new -key ca.key -days 3650 -out ca.crt -subj "/CN=aivision-model-ca"

openssl genrsa -out inference.key 2048
openssl req -new -key inference.key -out inference.csr -subj "/CN=ai-inference"
openssl x509 -req -in inference.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out inference.crt -days 825

openssl genrsa -out agent.key 2048
openssl req -new -key agent.key -out agent.csr -subj "/CN=model-agent"
openssl x509 -req -in agent.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out agent.crt -days 825

rm -f *.csr
```

> **Danger**：`*.key`、`*.srl`、`*.crt`（除 README）已在 `.gitignore` 中排除——不要用 `git add -f` 强推这些文件。

### 1.2 信任链：根签名密钥列表（保护模型签名）

这一层和上面的 mTLS 是两回事：mTLS 保护"谁能调用控制接口"，信任链保护"谁签的模型包可信"。产出在 `deploy/model-trust/`：

| 文件 | 内容 |
|---|---|
| `root.pub` | 根公钥（base64 的 32 字节 Ed25519 公钥） |
| `keys.json` | 根签名过的"当前有效签名密钥"列表，含 `list_version`（防重放，只能单调递增） |

> **Danger · 离线保管**：根私钥只在**轮换/撤销签名密钥**时才需要，任何在线服务都不需要它。生成后立刻转移到离线介质，不要留在这台机器或任何仓库里。

首次生成（示例用 Python `cryptography` 库；只需跑一次）：

```python
python3 - <<'PY'
import base64, json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()

def canonical(v: dict) -> bytes:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

# 根密钥：签完 keys.json 立刻把私钥移出这台机器
root = Ed25519PrivateKey.generate()
print("root.pub  :", b64(root.public_key().public_bytes_raw()))

# 日常签名模型包用的密钥（私钥留在发布端，不进任何仓库）
signer = Ed25519PrivateKey.generate()
key_id = "delivery-ed25519-v1"
print("signer priv:", b64(signer.private_bytes_raw()), " <- 妥善保存，签 bundle 要用")
print("signer pub :", b64(signer.public_key().public_bytes_raw()))

trust = {
    "list_version": 1,
    "root_key_id": "root-1",
    "expires_at": "2030-01-01T00:00:00+00:00",
    "keys": {key_id: b64(signer.public_key().public_bytes_raw())},
    "revoked": [],
}
trust["signature"] = b64(root.sign(canonical(trust)))
print(json.dumps(trust, ensure_ascii=False, indent=2))
PY
```

把打印出的 `trust` JSON 存为 `deploy/model-trust/keys.json`，`root.pub` 单独存为 `deploy/model-trust/root.pub`。`signer priv` 那一行是**制作模型包**要用的签名私钥（见第 4 节），只交给有权发布模型的人，不进任何 Git 仓库。

### 1.3 轮换 / 撤销一个签名密钥

不需要重新生成根密钥。用根私钥重新签一份 `keys.json`：`list_version` 必须比当前值大（`model_agent.py` 会拒绝 `list_version` 回退的列表，防止把已撤销的旧列表重放回去），把要撤销的 `key_id` 从 `keys` 里删掉、加进 `revoked`，替换文件后 model-agent 会在下一次读信任列表时自动生效，无需重启容器。

### 1.4 网络与卷

`model-volume-init` 是一次性 busybox 容器，负责把 `model_store`/`model_active`/`model_inbox` 等命名卷 chown 给 `ai-inference` 的运行用户（uid 10001），`docker compose up -d` 会自动跑它，不需要手动干预；`ai-services` 网络若不存在，`deploy/start.sh` 会自动创建。

### 1.5 生产模式硬门禁自检

这些条件写死在 `api_server.py` 模块加载时的检查里，任一条不满足容器直接拒绝启动（而不是带着错误配置跑起来）：

- `INFERENCE_VERSION` 必须是合法语义化版本（`x.y.z`），不能是默认值 `0.0.0-dev`
- `INFERENCE_EXECUTION_MODE` 必须是 `direct`（生产不允许走裸脚本子进程）
- `INFERENCE_PREWARM_ENABLED`、`INFERENCE_HEALTH_REQUIRES_WARMUP` 必须为真
- `MODEL_AGENT_CONTROL_TOKEN` 不能为空

---

## 2. .env 需要新增的内容

当前 `deploy/.env` 里模型交付相关的变量已经配置好（2026-08-13 那批），下表是完整清单 + 说明。**模板文件 `deploy/.env.gpu` / `deploy/.env.cpu` 还没同步这些变量**——建议把下表追加进两个模板，否则下次"照模板新建 .env"会漏掉整套模型交付配置。

| 变量 | 示例 | 状态 | 说明 |
|---|---|---|---|
| `BUILD_FLAVOR` | `production` | 新增 | 决定是否启用 1.5 节的硬门禁、是否走 mTLS 控制面。开发机保持 `development`。 |
| `INFERENCE_VERSION` | `1.4.0` | 新增 | 推理服务自身的语义化版本，模型包 manifest 里的 `minimum_inference_version` 会拿它做比较。**每次推理代码有能力变化（新增字段、新契约版本）都要跟着升。** |
| `AI_INFERENCE_PORT` | `8100` | 已有 | 宿主机映射端口，与训练平台的 8000 错开。 |
| `INFERENCE_INTERNAL_URL` | `https://ai-inference:9443` | 新增 | model-agent 访问控制面的地址；生产必须是 9443/https，否则 model-agent 启动即拒绝。 |
| `MODEL_ADMIN_TOKEN` | *64 位随机 hex* | **敏感** | 调 `/models/install`、`/models/activate`、`/models/rollback` 等管理接口用的 Bearer 令牌，公网端口（8100）上仅靠它鉴权。`openssl rand -hex 32` 生成。 |
| `MODEL_AGENT_CONTROL_TOKEN` | *64 位随机 hex* | **敏感** | model-agent ↔ ai-inference 之间 `/internal/runtime/*` 的应用层令牌，和 mTLS 客户端证书是两道独立的门。同样 `openssl rand -hex 32` 生成，与上面那个不要用同一个值。 |
| `DEFAULT_RUNTIME_PROFILE` | `det-gpu-default` | 新增 | 客户端不传 `profile_id` 时用的默认 profile，要和 `/models/activate` 里激活的 profile 名对上。 |
| `MODEL_GPU_SAFETY_MARGIN_MB` | `1024` | 新增 | 容量准入的安全余量，决定蓝绿/排空/拒绝三选一的判定阈值。 |
| `MODEL_AGENT_IMAGE` | `${REGISTRY}/aivision-model-agent:latest` | 建议新增 | 目前 `.env` 里还没有这一项，走的是 `docker-compose.yml` 默认值 `aivision-model-agent:latest`。部署机上如果沿用"pull 完再 `docker tag` 成裸名"的老习惯也可以，但更干净的做法是像 `AI_INFERENCE_IMAGE` 一样直接在部署机 `.env` 里把它指向仓库里的完整镜像名，见第 3 节。 |

> **Danger · 当前会话已读到真实密钥**：本文档在生成过程中读取了当前 `deploy/.env`，其中 `MODEL_ADMIN_TOKEN` / `MODEL_AGENT_CONTROL_TOKEN` 是这台机器上正在使用的**真实生产令牌**。本手册没有把具体值写进来；如果这份文档会分享出去，也不要另外把 `.env`、`.env.bak-*`、`model-mtls/*.key`、`model-delivery-root-key/` 这些贴进去或截图。

---

## 3. 代码 / 镜像发布（线路 A）

和原来的流程一样，只是从 3 个镜像变成 4 个——本次已经把 `model-agent` 补进 `rebuild.sh` / `push.sh` / `pull.sh`。

### 3.1 开发机：构建 + 打标签 + 推送

`rebuild.sh`（已更新）：

```bash
# backend / frontend / ai-inference 照旧，新增：
docker build -t aivision-model-agent:latest -f model/weld/Dockerfile.model-agent model/
```

`push.sh`（已更新，用法不变）：

```bash
./push.sh 1.4.0   # TAG 建议和 INFERENCE_VERSION 保持一致，避免"镜像是新的但版本号没跟上"
```

> **Note**：推荐把 `TAG` 定成和这次要设置的 `INFERENCE_VERSION` 一样（比如都叫 `1.4.0`），这样镜像标签、运行时上报的 `inference_version`、以及模型包 manifest 里比较用的版本号三者能对上，排障时不用来回换算。

### 3.2 部署机：拉取 + 重启

`pull.sh`（已更新，用法不变）：

```bash
./pull.sh 1.4.0
```

拉下来的镜像名带仓库前缀（`${REGISTRY}/aivision-xxx:1.4.0`），而 `docker-compose.yml` 里 backend/frontend 用的是裸镜像名，ai-inference/model-agent 可以通过环境变量指向完整仓库名。按你们现在部署机的习惯二选一：

- **沿用现有习惯**：拉取后 `docker tag` 成 compose 期待的裸名（backend/frontend 一直这么做的话，model-agent 照做即可）。
- **或者**：部署机 `.env` 里设置 `AI_INFERENCE_IMAGE=${REGISTRY}/aivision-ai-inference:1.4.0` 和 `MODEL_AGENT_IMAGE=${REGISTRY}/aivision-model-agent:1.4.0`，这两个服务的镜像名在 compose 里本来就是通过这两个变量注入的，不用另外 tag。

```bash
cd deploy
docker compose up -d   # 只重建镜像变化的服务，其余容器不受影响
```

> **Caution**：`ai-inference` 这个容器如果镜像变了会被 `docker compose up -d` 重建（推理进程重启，在途任务全部丢失），**这一步和"模型权重发布"（第 5 节）不是一回事**——只改模型权重、代码没变时，不要走这条线，直接走第 5 节，容器不用重启。

选低峰期执行；如果只是 `model-agent` 自身代码升级（比如加固了包校验逻辑），可以只重建那一个服务：`docker compose up -d model-agent`，不影响 `ai-inference` 正在跑的任务。

---

## 4. 制作签名模型包（线路 B · 第一步）

这是 model-agent 唯一会接受的输入格式，字段名摘自 `model_agent.py` 的校验逻辑（`install_bundle` / `_validate_revisions` / `build_revisions`）。目前仓库里没有现成的打包脚本（见第 8 节），下面给的是能跑通校验的最小参考实现。

### 4.1 zip 包结构

```
release.zip
├── manifest.json      # 见下方字段表
├── manifest.sig       # base64 Ed25519 签名，对 manifest.json 的 canonical JSON 编码签名
├── key_id              # 纯文本，如 delivery-ed25519-v1，必须在 keys.json 的信任列表里
└── weights/
    └── <任意文件名>    # 有且只能有一个文件，不能是目录/软链接
```

> **Caution**：zip 里不允许出现 `weights/` 之外的多余成员、目录条目、软链接，也不允许绝对路径或 `..`；否则 `INVALID_BUNDLE_LAYOUT`。单文件体积上限默认 8GB（`MODEL_BUNDLE_MAX_WEIGHT_BYTES`）。

### 4.2 manifest.json 字段

| 字段 | 要求 |
|---|---|
| `release_id` | 任意字符串，标识这次发布（如 `rel-2026-08-15-roi-v3`） |
| `slot` | 必须是 `roi` / `primary` / `correction` / `location_0` / `location_1` 之一，且要和第 5 节激活请求里用的 slot 名一致 |
| `manifest_version` | 固定为整数 `2` |
| `artifact.sha256` | weights/ 下那个权重文件的真实 sha256（64 位十六进制），agent 会重新计算校验，算出来对不上直接拒绝 |
| `artifact.relative_path` | 任意路径字符串，只取文件名部分作为落盘文件名 |
| `compatibility.minimum_inference_version` | 语义化版本，必须 ≤ 当前 `INFERENCE_VERSION` |
| `compatibility.preprocess_contract_version` / `preprocess_config_sha256` | 同一个 profile 里所有 slot 必须完全一致 |
| `compatibility.postprocess_contract_version` | 同一个 profile 里所有 slot 必须完全一致 |
| `compatibility.input_size` | 正整数，只校验"有效"，不跨 slot 比较（ROI=640、主检测=840 这类差异是预期内的） |
| `compatibility.ordered_class_map` | 可选。给了就必须和同一 `class_map_group`（缺省用 `task_type` 或 slot 名）下的其它 slot 逐项一致 |
| `compatibility.interface.coordinate_space` / `.produces` / `.consumes` | 描述这个 slot 的输入输出坐标空间衔接关系；`consumes` 里的值必须能在同 profile 其它 slot 的 `produces` 里找到，或者等于外部输入 `image@v1` |

### 4.3 参考打包/签名脚本

需要 `pip install cryptography`。`SIGNING_KEY_B64` 是 1.2 节生成的那把签名私钥（不是根私钥），只在发布端使用，不要落进版本库：

```python
python3 - <<'PY'
import base64, hashlib, json, zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

WEIGHT_FILE   = "roi_v3.pt"
SLOT          = "roi"
KEY_ID        = "delivery-ed25519-v1"
SIGNING_KEY_B64 = "<发布端保管的签名私钥>"

def canonical(v: dict) -> bytes:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

sha256 = hashlib.sha256()
with open(WEIGHT_FILE, "rb") as f:
    for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
        sha256.update(chunk)
digest = sha256.hexdigest()

manifest = {
    "release_id": "rel-2026-08-15-roi-v3",
    "slot": SLOT,
    "manifest_version": 2,
    "artifact": {"sha256": digest, "relative_path": f"weights/{WEIGHT_FILE}"},
    "compatibility": {
        "minimum_inference_version": "1.4.0",
        "preprocess_contract_version": "v1",
        "preprocess_config_sha256": "<和同 profile 其它 slot 一致的值>",
        "postprocess_contract_version": "v1",
        "input_size": 640,
        "interface": {
            "coordinate_space": "roi_crop@v1",
            "produces": ["roi_crop@v1"],
            "consumes": ["image@v1"],
        },
    },
}

key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(SIGNING_KEY_B64))
signature = base64.b64encode(key.sign(canonical(manifest))).decode()

with zipfile.ZipFile("release.zip", "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("manifest.json", canonical(manifest))
    zf.writestr("manifest.sig", signature)
    zf.writestr("key_id", KEY_ID)
    zf.write(WEIGHT_FILE, f"weights/{WEIGHT_FILE}")

print("release.zip ready, sha256 =", digest)
PY
```

> **Gap**：上面这段是按校验逻辑反推的参考实现，字段语义（尤其 `preprocess_config_sha256` 具体怎么算、`interface` 的坐标空间命名规范）应以训练/发布端现有的 manifest 生成器为准；仓库里目前没有找到对应的官方设计文档或生成脚本，见第 8 节。

---

## 5. 模型更新：安装 + 激活（线路 B · 第二步）

全部通过 HTTP 调用推理机的公开端口（`AI_INFERENCE_PORT`，示例用 8100），用 `X-Model-Admin-Token` 鉴权，不需要 mTLS 客户端证书——那是 model-agent 自己内部用的。

### 5.1 上传签名包

```bash
curl -sS -X POST "http://<推理机IP>:8100/models/install" \
  -H "X-Model-Admin-Token: $MODEL_ADMIN_TOKEN" \
  -F "bundle=@release.zip"
# {"install_job_id": "a1b2c3...", "state": "QUEUED"}
```

model-agent 每 5 秒轮询一次收件箱，验签、查重、按 sha256 落盘。跟踪进度：

```bash
curl -sS "http://<推理机IP>:8100/models/jobs/a1b2c3..." \
  -H "X-Model-Admin-Token: $MODEL_ADMIN_TOKEN"
# state: QUEUED -> SUCCEEDED（或 FAILED，看 model-agent 容器日志找具体错误码）
```

确认制品已入库：

```bash
curl -sS "http://<推理机IP>:8100/models/installed" \
  -H "X-Model-Admin-Token: $MODEL_ADMIN_TOKEN"
```

> **Caution**：一个 profile 通常需要多个 slot（比如 `roi` + `primary`），每个 slot 都是独立的一次 `/models/install`。等所有需要的 slot 都显示在 `/models/installed` 里再进行下一步。

### 5.2 提交激活请求

把上一步返回的 sha256 组装成 profile，`set_id` 自己起一个便于追溯的名字：

```bash
curl -sS -X POST "http://<推理机IP>:8100/models/activate" \
  -H "X-Model-Admin-Token: $MODEL_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "set_id": "rs-2026-08-15-roi-v3",
    "profiles": {
      "det-gpu-default": {
        "slots": {
          "roi": "<roi 权重的 sha256>",
          "primary": "<primary 权重的 sha256>"
        },
        "runtime": {
          "mode": "det",
          "device": "cuda:0",
          "primary_conf": 0.15,
          "wide_slice": true,
          "enable_location": true,
          "enable_iqi": true
        },
        "gpu_budget_mb": 6000
      }
    }
  }'
# {"job_id": "d4e5f6...", "state": "QUEUED"}
```

`profiles` 的 key（示例里的 `det-gpu-default`）要和 `.env` 里 `DEFAULT_RUNTIME_PROFILE` 一致，客户端不显式传 `profile_id` 时用的就是这个。`gpu_budget_mb` 是必填项，用于蓝绿/排空的容量判定。

同样用 `/models/jobs/{job_id}` 跟踪，或者直接看 `/models` 的运行时状态：

```bash
curl -sS "http://<推理机IP>:8100/models" | python3 -m json.tool
# runtime_state 会经历 warming/active ->（如需排空）draining -> committing -> active
```

> **Note · 这一步不会打断正在跑的任务**：已经提交的推理任务全程绑定它拿到时的那份模型（同一个 lease），激活切换只影响**新提交**的请求：如果显存放得下新旧两份（蓝绿），新任务几乎无感知；如果放不下、必须先腾空（排空），排空等待和短暂的 commit 冻结窗口内新提交的请求会收到 `409 MODEL_SWITCH_IN_PROGRESS`，重试即可，正在跑的任务不受影响。

### 5.3 排空超时 / 容量不足怎么办

| 响应 | 含义 | 处理 |
|---|---|---|
| `504 DRAIN_TIMEOUT` | 在途任务在超时窗口内没跑完，无法腾空旧模型 | 等当前负载降下来后重新 `/models/activate`；或者临时调大 `drain_timeout_seconds`（激活体里可传，默认 900s） |
| `507 PROFILE_SET_UNSCHEDULABLE` | 就算清空显存也放不下新组合 | 降低 `gpu_budget_mb` 估算、精简 profile，或者换更大显存的卡；排空救不了这个错误 |
| `410 OPERATION_TIMED_OUT` | begin-commit 后 600s 内没收到 commit（agent 失联） | 运行时已自动回滚到旧模型继续接单；排查 model-agent 容器状态后重新发起激活 |

---

## 6. 模型回滚（线路 B · 应急）

回滚到"上一个成功激活的组合"，不需要重新上传或验签，本地已有制品直接复用。

```bash
curl -sS -X POST "http://<推理机IP>:8100/models/rollback" \
  -H "X-Model-Admin-Token: $MODEL_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "roi v3 误报率异常升高，回退 v2"}'
# {"job_id": "...", "state": "QUEUED"}
```

回滚内部按普通激活处理，走完整的 prepare/begin-commit/commit 三段式，并且拿到**更高的 generation**——不会复用旧编号，避免滞后的轮询把"坏"的那个 set 复活。查看历史确认状态变化：

```bash
curl -sS "http://<推理机IP>:8100/models/history" \
  -H "X-Model-Admin-Token: $MODEL_ADMIN_TOKEN" | python3 -m json.tool
# 被回滚的那个 set: state=ROLLED_BACK
# 新生成的 set: state=ACTIVE, rolled_back_from=<被回滚的 set_id>
```

> **Danger**：回滚只能退到**直接的上一个**成功组合（记录在 `previous_set_id`），不是任意历史版本的时间机器。要跳回更早的版本，从 `/models/history` 里找到那个 set 记录的 slot sha256，按 5.2 节重新发起一次 `/models/activate`。

---

## 7. 发布后核对清单

- **线路 A**：`docker compose ps` 四个服务都是 healthy；`curl http://localhost:8100/health` 返回 200
- **线路 A**：看一遍 `docker compose logs ai-inference --tail 100`，确认没有硬门禁报错（1.5 节那四条）
- **线路 B**：`GET /models` 里 `runtime_state=active`、`set_id`/`generation` 是这次发布的新值
- **线路 B**：挑 2-3 张历史底片跑一次真实推理，人工核对结果，不要只看健康检查
- **两条线通用**：观察 15-30 分钟错误率/耗时，确认没有异常再收工
- 把这次发布用的 `release.zip`、`set_id`、`release_id` 记录进发布日志，方便下次回滚时对照

---

## 8. 已知缺口

这两样东西在这份手册里是"手写命令"顶上去的，仓库里目前还没有对应的成熟工具：

**Gap 1**：`deploy/model-delivery.env.sh` 里 `source` 之后本应搭配一个 `scripts/model_delivery.py` 命令行工具（封装 install/activate/rollback/history），但仓库里找不到这个文件——大概率是规划中但还没写，或者存在于训练/发布端的另一个仓库里。目前第 5、6 节都是用裸 `curl` 顶上的。

**Gap 2**：第 4 节的打包/签名脚本是根据 `model_agent.py` 的校验代码反推的参考实现，不是仓库里现成的工具，也没找到 `docs/model-delivery-v7.1.md`（commit message 里提到的设计文档）来核对字段的权威定义，尤其是 `preprocess_config_sha256` 具体如何计算、`interface.coordinate_space` 的命名规范这些"跨 slot 但不在这份代码里定义"的约定。

如果需要，可以把这两个补成仓库里真正能跑、能复用的脚本（`model/weld/scripts/build_model_bundle.py` + `scripts/model_delivery.py`），而不是留在手册里当命令片段。
