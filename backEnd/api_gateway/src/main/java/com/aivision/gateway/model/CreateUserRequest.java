package com.aivision.gateway.model;

import io.swagger.v3.oas.annotations.media.Schema;
import javax.validation.constraints.Email;
import javax.validation.constraints.NotBlank;
import java.util.List;

@Schema(description = "创建用户请求")
public class CreateUserRequest {

    @Schema(description = "用户名", example = "admin", required = true)
    @NotBlank(message = "用户名不能为空")
    private String username;

    @Schema(description = "密码", example = "123456", required = true)
    @NotBlank(message = "密码不能为空")
    private String password;

    @Schema(description = "角色 (ADMIN/INSPECTOR)", example = "INSPECTOR", required = true)
    @NotBlank(message = "角色不能为空")
    private String role;

    @Schema(description = "项目权限列表")
    private List<ProjectPermissionDTO> projectPermissions;

    public static class ProjectPermissionDTO {
        @Schema(description = "项目ID")
        private String projectId;
        
        @Schema(description = "权限 (READ_ONLY/READ_WRITE)")
        private String permission;

        // Getters and Setters
        public String getProjectId() { return projectId; }
        public void setProjectId(String projectId) { this.projectId = projectId; }
        
        public String getPermission() { return permission; }
        public void setPermission(String permission) { this.permission = permission; }
    }

    // Getters and Setters
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }

    public List<ProjectPermissionDTO> getProjectPermissions() { return projectPermissions; }
    public void setProjectPermissions(List<ProjectPermissionDTO> projectPermissions) { this.projectPermissions = projectPermissions; }
}

