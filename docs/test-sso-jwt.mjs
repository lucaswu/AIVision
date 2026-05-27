/**
 * SSO JWT 登录测试脚本
 * 用法: node docs/test-sso-jwt.mjs [username] [role] [redirect]
 * 示例: node docs/test-sso-jwt.mjs zhangsan INSPECTOR /projects
 */

import { createSign } from "crypto";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

const API_BASE = process.env.API_BASE || "http://localhost:9541";
const username = process.argv[2] || "test-user";
const role = process.argv[3] || "INSPECTOR";
const redirect = process.argv[4] || "/projects";

// 读取私钥
const privateKeyPem = readFileSync(join(__dirname, "sso_private_key.pem"), "utf8");

// 手动构造 RS256 JWT（无需第三方库）
function base64url(buf) {
  return Buffer.from(buf)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}

function buildJwt(payload, privateKeyPem) {
  const header = base64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const body = base64url(JSON.stringify(payload));
  const input = `${header}.${body}`;

  const sign = createSign("RSA-SHA256");
  sign.update(input);
  sign.end();
  const signature = base64url(sign.sign(privateKeyPem));

  return `${input}.${signature}`;
}

const now = Math.floor(Date.now() / 1000);
const payload = {
  iss: "external-system",
  aud: "ai-vision",
  sub: username,
  username,
  role,
  redirect,
  iat: now,
  exp: now + 300,
  nonce: Math.random().toString(36).slice(2),
};

console.log("Payload:", JSON.stringify(payload, null, 2));
const token = buildJwt(payload, privateKeyPem);
console.log("\nJWT:", token.slice(0, 60) + "...");

// 调用 SSO 登录接口
console.log(`\nPOST ${API_BASE}/api/v1/users/sso-login-jwt`);

const response = await fetch(`${API_BASE}/api/v1/users/sso-login-jwt`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ token }),
});

const result = await response.json();
console.log("\nHTTP Status:", response.status);
console.log("Response:", JSON.stringify(result, null, 2));

// 同时打印前端跳转 URL
const frontendUrl = `http://localhost:3000/sso-login?token=${encodeURIComponent(token)}`;
console.log("\n前端测试 URL（浏览器打开）:");
console.log(frontendUrl);
