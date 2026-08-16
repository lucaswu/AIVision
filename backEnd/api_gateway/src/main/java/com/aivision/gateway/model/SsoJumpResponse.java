package com.aivision.gateway.model;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "SSO 跳转响应")
public class SsoJumpResponse {

    @Schema(description = "跳转地址（携带已签名的JWT）")
    private String url;

    public SsoJumpResponse(String url) {
        this.url = url;
    }

    public String getUrl() {
        return url;
    }

    public void setUrl(String url) {
        this.url = url;
    }
}
