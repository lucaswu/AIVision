# AI Vision SSO 单点登录方案：JWT + RS256

本文档用于指导外部系统接入 AI Vision SSO 单点登录，方案采用标准的 `JWT + RS256` 非对称签名。

## 1. 方案目标

外部系统用户已登录后，外部系统签发一个 JWT，并使用自己的 RSA 私钥进行 `RS256` 签名。AI Vision 只保存外部系统提供的 RSA 公钥，用公钥验证 JWT 的真实性。

跳转形式：

```text
https://<AI_VISION_DOMAIN>/sso-login?token=<JWT>
```

其中：

- 外部系统持有：RSA 私钥
- AI Vision 持有：RSA 公钥
- 外部系统负责：生成 JWT、签名、跳转
- AI Vision 负责：验签、校验过期时间、校验签发方、创建或匹配本系统用户

## 2. RS256 方案优势

`RS256` 使用非对称密钥：

- 外部系统用私钥签名。
- AI Vision 用公钥验签。
- 公钥泄露不会导致伪造登录。
- AI Vision 不需要保存外部系统私钥。

注意：这里使用的是"私钥签名、公钥验签"，不是"公钥加密、私钥解密"。公钥加密不能证明数据来自可信系统。

## 3. 登录流程

```text
1. 用户登录外部系统
2. 外部系统生成 JWT payload
3. 外部系统使用 RSA 私钥对 JWT 做 RS256 签名
4. 外部系统跳转到 AI Vision：
   /sso-login?token=<JWT>
5. AI Vision 前端读取 token
6. AI Vision 前端调用后端：
   POST /api/v1/users/sso-login-jwt
7. AI Vision 后端使用外部系统公钥验证 JWT
8. 验证通过后，根据用户名查找或创建本系统用户
9. AI Vision 返回本系统登录态
10. 前端写入 localStorage 并跳转到 redirect 页面
```

## 4. JWT 内容规范

### 4.1 Header

```json
{
  "alg": "RS256",
  "typ": "JWT"
}
```

### 4.2 Payload

推荐字段：

```json
{
  "iss": "external-system",
  "aud": "ai-vision",
  "sub": "zhangsan",
  "username": "zhangsan",
  "role": "INSPECTOR",
  "redirect": "/projects",
  "iat": 1760000000,
  "exp": 1760000300,
  "nonce": "8f3a2c9b6d1e4a7f"
}
```

字段说明：

| 字段 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `iss` | 是 | `external-system` | JWT 签发方，AI Vision 会校验。 |
| `aud` | 是 | `ai-vision` | JWT 接收方，AI Vision 会校验。 |
| `sub` | 是 | `zhangsan` | 用户唯一标识，建议使用外部系统用户名或用户 ID。 |
| `username` | 否 | `zhangsan` | 用户名。若不传，AI Vision 可使用 `sub` 作为用户名。 |
| `role` | 否 | `INSPECTOR` | 用户角色，支持 `INSPECTOR`、`ADMIN`。普通用户建议传 `INSPECTOR`。 |
| `redirect` | 否 | `/projects` | 登录成功后进入 AI Vision 的页面。 |
| `iat` | 是 | `1760000000` | 签发时间，单位是秒。 |
| `exp` | 是 | `1760000300` | 过期时间，单位是秒。建议有效期 5 分钟以内。 |
| `nonce` | 否 | `8f3a2c9b6d1e4a7f` | 随机串，建议每次生成。需要防重放时由 AI Vision 记录已使用 nonce。 |

### 4.3 角色约定

AI Vision 当前支持：

```text
ADMIN
INSPECTOR
```

建议外部系统默认传：

```text
INSPECTOR
```

如果 AI Vision 中用户已存在，建议以内置数据库中的角色为准，不自动覆盖已有用户角色。

## 5. 密钥生成和交换

由外部系统生成 RSA 密钥对。

生成私钥：

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out sso_private_key.pem
```

生成公钥：

```bash
openssl rsa -in sso_private_key.pem -pubout -out sso_public_key.pem
```

交付规则：

- `sso_private_key.pem`：只保存在外部系统，不能提供给 AI Vision。
- `sso_public_key.pem`：提供给 AI Vision，用于验签。

公钥示例：

```text
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQE...
-----END PUBLIC KEY-----
```

## 6. 外部系统生成 JWT

### 6.1 Java 示例

示例使用 `java-jwt`：

```xml
<dependency>
    <groupId>com.auth0</groupId>
    <artifactId>java-jwt</artifactId>
    <version>4.4.0</version>
</dependency>
```

生成 JWT：

```java
import com.auth0.jwt.JWT;
import com.auth0.jwt.algorithms.Algorithm;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.KeyFactory;
import java.security.interfaces.RSAPrivateKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.time.Instant;
import java.util.Base64;
import java.util.Date;
import java.util.UUID;

public class AiVisionSsoJwtBuilder {
    public static void main(String[] args) throws Exception {
        String aiVisionBaseUrl = "https://<AI_VISION_DOMAIN>";

        RSAPrivateKey privateKey = loadPrivateKey("sso_private_key.pem");
        Algorithm algorithm = Algorithm.RSA256(null, privateKey);

        Instant now = Instant.now();
        String username = "zhangsan";
        String redirect = "/projects";

        String token = JWT.create()
                .withIssuer("external-system")
                .withAudience("ai-vision")
                .withSubject(username)
                .withClaim("username", username)
                .withClaim("role", "INSPECTOR")
                .withClaim("redirect", redirect)
                .withClaim("nonce", UUID.randomUUID().toString().replace("-", ""))
                .withIssuedAt(Date.from(now))
                .withExpiresAt(Date.from(now.plusSeconds(300)))
                .sign(algorithm);

        String url = aiVisionBaseUrl + "/sso-login?token=" + java.net.URLEncoder.encode(token, "UTF-8");
        System.out.println(url);
    }

    private static RSAPrivateKey loadPrivateKey(String path) throws Exception {
        String pem = new String(Files.readAllBytes(Paths.get(path)));
        pem = pem.replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s", "");

        byte[] decoded = Base64.getDecoder().decode(pem);
        PKCS8EncodedKeySpec keySpec = new PKCS8EncodedKeySpec(decoded);
        KeyFactory keyFactory = KeyFactory.getInstance("RSA");
        return (RSAPrivateKey) keyFactory.generatePrivate(keySpec);
    }
}
```

如果使用 `openssl genrsa` 生成了 `-----BEGIN RSA PRIVATE KEY-----` 格式的 PKCS#1 私钥，部分 Java 库读取会不方便。可以转换为 PKCS#8：

```bash
openssl pkcs8 -topk8 -inform PEM -outform PEM -nocrypt \
  -in sso_private_key.pem \
  -out sso_private_key_pkcs8.pem
```

### 6.2 Node.js 示例

安装依赖：

```bash
npm install jsonwebtoken
```

生成 JWT：

```javascript
const fs = require("fs");
const crypto = require("crypto");
const jwt = require("jsonwebtoken");

const aiVisionBaseUrl = "https://<AI_VISION_DOMAIN>";
const privateKey = fs.readFileSync("sso_private_key.pem", "utf8");

const username = "zhangsan";

const token = jwt.sign(
  {
    username,
    role: "INSPECTOR",
    redirect: "/projects",
    nonce: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
  },
  privateKey,
  {
    algorithm: "RS256",
    issuer: "external-system",
    audience: "ai-vision",
    subject: username,
    expiresIn: "5m",
  }
);

const url = `${aiVisionBaseUrl}/sso-login?token=${encodeURIComponent(token)}`;
console.log(url);
```

如果 Node.js 版本没有 `crypto.randomUUID`，可改用：

```javascript
const crypto = require("crypto");
const nonce = crypto.randomBytes(16).toString("hex");
```

## 7. 后端接口

### 7.1 接口

```http
POST /api/v1/users/sso-login-jwt
Content-Type: application/json

{
  "token": "<JWT>"
}
```

返回格式：

```json
{
  "Code": 200,
  "Message": "SSO登录成功",
  "Data": {
    "userId": "xxx",
    "username": "zhangsan",
    "role": "INSPECTOR",
    "token": "本系统登录token",
    "redirect": "/projects"
  }
}
```

### 7.2 配置

```yaml
sso:
  jwt:
    enabled: ${SSO_JWT_ENABLED:true}
    public-key: ${SSO_JWT_PUBLIC_KEY:}
    public-key-file: ${SSO_JWT_PUBLIC_KEY_FILE:classpath:sso_public_key.pem}
    issuer: ${SSO_JWT_ISSUER:external-system}
    audience: ${SSO_JWT_AUDIENCE:ai-vision}
    allowed-clock-skew-seconds: ${SSO_JWT_ALLOWED_CLOCK_SKEW_SECONDS:60}
    auto-create-users: ${SSO_JWT_AUTO_CREATE_USERS:true}
    default-role: ${SSO_JWT_DEFAULT_ROLE:INSPECTOR}
```

### 7.3 验签逻辑

后端必须校验：

1. `alg` 必须是 `RS256`。
2. JWT 签名必须能用配置的公钥验证通过。
3. `iss` 必须等于配置的 `SSO_JWT_ISSUER`。
4. `aud` 必须包含配置的 `SSO_JWT_AUDIENCE`。
5. `exp` 未过期。
6. `iat` 不应明显晚于服务器当前时间。
7. `sub` 或 `username` 必须存在。
8. `role` 如果存在，必须是 AI Vision 支持的角色。
9. `redirect` 必须是站内相对路径，不能是外部 URL。
10. 如需防重放，`nonce` 必须未使用过，验证成功后记录为已使用。

### 7.4 用户匹配规则

```text
1. 优先使用 username claim
2. username 为空时使用 sub
3. 按 username 查询 AI Vision users 表
4. 用户存在：使用 AI Vision 数据库中的 role/status
5. 用户不存在且允许自动创建：创建 ACTIVE 用户
6. 用户不存在且不允许自动创建：拒绝登录
7. 用户状态不是 ACTIVE：拒绝登录
```

### 7.5 redirect 安全规则

只允许站内相对路径：

允许：

```text
/projects
/projects/123/files
```

拒绝：

```text
https://example.com
//example.com
javascript:alert(1)
```

redirect 为空或非法时，自动回退到 `/projects`。

## 8. 错误码

| 场景 | HTTP 状态 | Message |
| --- | --- | --- |
| 未启用 SSO JWT | 400 | `SSO JWT登录未启用` |
| token 为空 | 400 | `SSO token不能为空` |
| 签名无效 | 400 | `SSO token签名无效` |
| token 过期 | 400 | `SSO token已过期` |
| issuer 不匹配 | 400 | `SSO token签发方无效` |
| audience 不匹配 | 400 | `SSO token接收方无效` |
| 用户不存在且不允许自动创建 | 400 | `用户不存在` |
| 用户被禁用 | 400 | `账号已被禁用` |

## 9. 测试用例建议

1. 正确 JWT 可以登录成功。
2. 正确 JWT 且用户不存在时自动创建用户。
3. 签名被篡改时拒绝。
4. `exp` 过期时拒绝。
5. `iss` 不匹配时拒绝。
6. `aud` 不匹配时拒绝。
7. `role` 非法时拒绝。
8. 已禁用用户拒绝登录。
9. 非法 `redirect` 自动回退到 `/projects`。
10. 如果启用 nonce 防重放，同一个 `nonce` 第二次使用时拒绝。

## 10. 出站方向：跳转到训练平台（AIVision-training）

AI Vision 与训练平台 AIVision-training 共享同一对密钥。除了本文档前面描述的"验证"能力外，AI Vision 也可以用同一把私钥签发 JWT，供已登录用户跳转登录到训练平台。

```http
POST /api/v1/users/sso/jump?redirect=/projects
user-id: <当前登录用户ID>
```

返回：

```json
{
  "Code": 200,
  "Message": "获取跳转地址成功",
  "Data": { "url": "https://<训练平台域名>/sso-login?token=<JWT>" }
}
```

签发的 JWT `iss`/`aud` 默认对应训练平台的入站校验默认值（`external-system` / `aivision-training`），因此**默认配置下训练平台无需任何改动**即可验签通过。

配置项（`application.yml` `sso.jwt.*` / 环境变量）：

```yaml
sso:
  jwt:
    private-key: ${SSO_JWT_PRIVATE_KEY:}
    private-key-file: ${SSO_JWT_PRIVATE_KEY_FILE:classpath:sso_private_key.pem}
    issuer-self: ${SSO_JWT_ISSUER_SELF:external-system}
    target-audience: ${SSO_JWT_TARGET_AUDIENCE:aivision-training}
    training-base-url: ${SSO_JWT_TRAINING_BASE_URL:}
    issued-token-ttl-seconds: ${SSO_JWT_ISSUED_TOKEN_TTL_SECONDS:300}
```

`training-base-url` 未配置时，`/sso/jump` 返回 400（`未配置训练平台跳转地址`）。

该接口沿用本项目现有的"信任 `user-id` 请求头"方式识别当前用户（本项目后端目前没有真正的会话/JWT 校验，所有受保护接口都是这个模式），不引入新的、与其他接口不一致的鉴权逻辑。
