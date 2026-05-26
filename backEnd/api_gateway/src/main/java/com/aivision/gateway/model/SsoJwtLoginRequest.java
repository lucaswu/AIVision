package com.aivision.gateway.model;

import io.swagger.v3.oas.annotations.media.Schema;

import javax.validation.constraints.NotBlank;

@Schema(description = "SSO JWT单点登录请求")
public class SsoJwtLoginRequest {

    @Schema(description = "外部系统签发的RS256 JWT", required = true)
    @NotBlank(message = "SSO token不能为空")
    private String token;

    public String getToken() {
        return token;
    }

    public void setToken(String token) {
        this.token = token;
    }
}
