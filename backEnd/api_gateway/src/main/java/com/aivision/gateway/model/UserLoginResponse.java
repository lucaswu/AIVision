package com.aivision.gateway.model;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "用户登录响应")
public class UserLoginResponse {
    
    @Schema(description = "用户ID")
    private String userId;
    
    @Schema(description = "用户名")
    private String username;
    
    @Schema(description = "角色")
    private String role;
    
    @Schema(description = "访问令牌")
    private String token;

    public UserLoginResponse(String userId, String username, String role, String token) {
        this.userId = userId;
        this.username = username;
        this.role = role;
        this.token = token;
    }

    // Getters
    public String getUserId() { return userId; }
    public String getUsername() { return username; }
    public String getRole() { return role; }
    public String getToken() { return token; }
}

