package com.aivision.gateway.model;

import io.swagger.v3.oas.annotations.media.Schema;
import java.time.LocalDateTime;
import java.util.List;

@Schema(description = "用户详情响应")
public class UserResponse {

    @Schema(description = "用户ID")
    private String userId;

    @Schema(description = "用户名")
    private String username;

    @Schema(description = "角色")
    private String role;

    @Schema(description = "状态")
    private String status;

    @Schema(description = "创建时间")
    private LocalDateTime createdAt;

    @Schema(description = "项目权限列表")
    private List<UserProjectPermissionDTO> permissions;

    public static class UserProjectPermissionDTO {
        private String projectId;
        private String projectName;
        private String permission; // READ_ONLY, READ_WRITE

        public UserProjectPermissionDTO(String projectId, String projectName, String permission) {
            this.projectId = projectId;
            this.projectName = projectName;
            this.permission = permission;
        }

        // Getters
        public String getProjectId() { return projectId; }
        public String getProjectName() { return projectName; }
        public String getPermission() { return permission; }
    }

    public UserResponse() {}

    // Getters and Setters
    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public List<UserProjectPermissionDTO> getPermissions() { return permissions; }
    public void setPermissions(List<UserProjectPermissionDTO> permissions) { this.permissions = permissions; }
}

