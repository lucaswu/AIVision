package com.aivision.gateway.model;

import io.swagger.v3.oas.annotations.media.Schema;
import javax.validation.constraints.Email;
import javax.validation.constraints.NotBlank;

@Schema(description = "用户登录请求")
public class UserLoginRequest {

    @Schema(description = "用户名", example = "admin", required = true)
    @NotBlank(message = "用户名不能为空")
    private String username;

    @Schema(description = "密码", example = "123456", required = true)
    @NotBlank(message = "密码不能为空")
    private String password;

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
}

