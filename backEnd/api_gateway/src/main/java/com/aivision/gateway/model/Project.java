package com.aivision.gateway.model;

import javax.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "project")
public class Project {
    
    public enum Status {
        ACTIVE, INACTIVE, ARCHIVED, DELETED
    }
    
    @Id
    @Column(name = "project_id", length = 255)
    private String projectId;
    
    @Column(name = "project_name", nullable = false, length = 255)
    private String projectName;
    
    @Column(name = "description", columnDefinition = "TEXT")
    private String description;
    
    @Column(name = "owner_id", nullable = false, length = 255)
    private String ownerId;
    
    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private Status status = Status.ACTIVE;
    
    @Column(name = "project_type", length = 100)
    private String projectType;
    
    @Column(name = "settings", columnDefinition = "TEXT")
    private String settings;
    
    @Column(name = "created_at")
    private LocalDateTime createdAt;
    
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
    
    // 构造函数
    public Project() {}
    
    public Project(String projectId, String projectName, String ownerId) {
        this.projectId = projectId;
        this.projectName = projectName;
        this.ownerId = ownerId;
        this.status = Status.ACTIVE;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }
    
    // Getters and Setters
    public String getProjectId() {
        return projectId;
    }
    
    public void setProjectId(String projectId) {
        this.projectId = projectId;
    }
    
    public String getProjectName() {
        return projectName;
    }
    
    public void setProjectName(String projectName) {
        this.projectName = projectName;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getDescription() {
        return description;
    }
    
    public void setDescription(String description) {
        this.description = description;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getOwnerId() {
        return ownerId;
    }
    
    public void setOwnerId(String ownerId) {
        this.ownerId = ownerId;
        this.updatedAt = LocalDateTime.now();
    }
    
    public Status getStatus() {
        return status;
    }
    
    public void setStatus(Status status) {
        this.status = status;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getProjectType() {
        return projectType;
    }
    
    public void setProjectType(String projectType) {
        this.projectType = projectType;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getSettings() {
        return settings;
    }
    
    public void setSettings(String settings) {
        this.settings = settings;
        this.updatedAt = LocalDateTime.now();
    }
    
    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
    
    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }
    
    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }
    
    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
    
    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }
    
    @PreUpdate
    protected void onUpdate() {
        this.updatedAt = LocalDateTime.now();
    }
    
    @Override
    public String toString() {
        return "Project{" +
                "projectId='" + projectId + '\'' +
                ", projectName='" + projectName + '\'' +
                ", ownerId='" + ownerId + '\'' +
                ", status=" + status +
                ", projectType='" + projectType + '\'' +
                ", createdAt=" + createdAt +
                ", updatedAt=" + updatedAt +
                '}';
    }
} 