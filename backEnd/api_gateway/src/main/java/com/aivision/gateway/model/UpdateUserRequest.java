package com.aivision.gateway.model;

import io.swagger.v3.oas.annotations.media.Schema;
import java.util.List;

@Schema(description = "更新用户请求")
public class UpdateUserRequest {

    // Removed email update capability as username is the ID/login now
    // and username update is allowed? Usually ID is immutable but username can be changeable if ID is separate UUID.
    // Assuming username is login, let's keep it updatable if needed, or remove if strictly ID.
    // For now, let's allow updating password/role/status.
    
    @Schema(description = "密码 (留空则不修改)", example = "123456")
    private String password;

    @Schema(description = "角色 (ADMIN/INSPECTOR)", example = "INSPECTOR")
    private String role;

    @Schema(description = "状态 (ACTIVE/DISABLED)", example = "ACTIVE")
    private String status;

    @Schema(description = "项目权限列表 (覆盖原有权限)")
    private List<CreateUserRequest.ProjectPermissionDTO> projectPermissions;

    // Getters and Setters
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public List<CreateUserRequest.ProjectPermissionDTO> getProjectPermissions() { return projectPermissions; }
    public void setProjectPermissions(List<CreateUserRequest.ProjectPermissionDTO> projectPermissions) { this.projectPermissions = projectPermissions; }
}

