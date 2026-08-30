# 默认 slot 的签名交付包

`roi`、`location_0`、`location_1` 这几个 slot 不走训练平台的发布/部署流程重新训练——
它们一直是同一份权重文件（`weld/weight/weldROI4.pt`、`weld/weight/location_0.pt`、
`weld/weight/location_1.pt`），只有 `primary` 会通过训练平台持续更新。

`model_agent.py` 启动时会自动把这个目录下的 `*.zip` 装进本地 store（见
`ModelAgent.install_bundled_defaults()`），已装过的 sha256 会跳过，可以放心每次
`rebuild.sh` 都重新走一遍。

## 这些 zip 是什么

跟训练平台发布出来的 release 包结构完全一样（`manifest.json` + `manifest.sig` +
`key_id` + `weights/<file>`），用训练平台的签名私钥离线签发，只是不经过训练平台的
发布数据库/审批流程。**不进 git**（跟裸权重文件一样，见 `model/.gitignore`），每台
部署机器需要跟 `weld/weight/*.pt` 一样手动放一份过来。

## 怎么重新签发

权重文件本身不变的情况下，正常不需要重签；如果 `model_delivery_registry.py` 里的
`preprocess_config_sha256`/`preprocess_contract_version`/`postprocess_contract_version`
常量以后变了，roi/location_0/location_1 也要跟着走一遍，否则会在激活时报
`CROSS_SLOT_PREPROCESS_MISMATCH`/`CROSS_SLOT_POSTPROCESS_MISMATCH`。

```bash
export SIGNING_KEY_B64=$(grep '^MODEL_DELIVERY_SIGNING_KEY=' <训练平台仓库>/.env | cut -d= -f2-)
cd model/weld/scripts

python3 build_model_bundle.py \
  --weight-file ../weight/weldROI4.pt \
  --slot roi \
  --release-id rel-default-roi-v1 \
  --minimum-inference-version 1.0.0 \
  --preprocess-contract-version weld-pipeline-v1 \
  --preprocess-config-sha256 d6c73c0084591985d57a5db785ae7c2331325b72eb6fa51ae0da91e1ee6d4701 \
  --postprocess-contract-version weld-postprocess-v1 \
  --input-size 640 \
  --coordinate-space roi_crop_pixels \
  --produces roi_crop@v1 \
  --consumes image@v1 \
  --key-id delivery-ed25519-v1 \
  --output ../bootstrap-bundles/roi.zip

# location_0 / location_1：--slot、--weight-file、--release-id 换一下，
# --coordinate-space image@v1、--consumes image@v1、不传 --produces，其余相同。
```

`--preprocess-config-sha256`/`--preprocess-contract-version`/`--postprocess-contract-version`
必须跟 `backend/app/services/model_delivery_registry.py`（训练平台仓库）里当前的常量
一致——那边才是权威来源，这几个值不是随便起的。
