package com.aivision.gateway.model;

import javax.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "user_project_permission", 
    uniqueConstraints = @UniqueConstraint(columnNames = {"user_id", "project_id"}))
public class UserProjectPermission {

    public enum Permission {
        READ_ONLY,  // 只读
        READ_WRITE  // 可编辑
    }

    @Id
    @Column(name = "id", length = 36)
    private String id;

    @Column(name = "user_id", nullable = false, length = 36)
    private String userId;

    @Column(name = "project_id", nullable = false, length = 255)
    private String projectId;

    @Enumerated(EnumType.STRING)
    @Column(name = "permission", nullable = false, length = 20)
    private Permission permission;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    public UserProjectPermission() {}

    public UserProjectPermission(String id, String userId, String projectId, Permission permission) {
        this.id = id;
        this.userId = userId;
        this.projectId = projectId;
        this.permission = permission;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    // Getters and Setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }

    public String getProjectId() { return projectId; }
    public void setProjectId(String projectId) { this.projectId = projectId; }

    public Permission getPermission() { return permission; }
    public void setPermission(Permission permission) { this.permission = permission; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }

    @PrePersist
    protected void onCreate() {
        if (createdAt == null) createdAt = LocalDateTime.now();
        if (updatedAt == null) updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}


