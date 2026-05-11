package com.aivision.gateway.model;

import javax.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "directory")
public class Directory {

    public enum Status {
        ACTIVE, DELETED
    }

    @Id
    @Column(name = "dir_id", length = 255)
    private String dirId;

    @Column(name = "project_id", nullable = false, length = 255)
    private String projectId;

    @Column(name = "user_id", nullable = false, length = 255)
    private String userId;

    @Column(name = "parent_id", length = 255)
    private String parentId;

    @Column(name = "dir_name", nullable = false, length = 255)
    private String dirName;

    @Column(name = "dir_path", nullable = false, columnDefinition = "TEXT")
    private String dirPath;

    @Column(name = "dir_level", nullable = false)
    private Integer dirLevel = 1;

    @Column(name = "sort_order", nullable = false, columnDefinition = "INTEGER DEFAULT 99")
    private Integer sortOrder = 99;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private Status status = Status.ACTIVE;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    // 构造函数
    public Directory() {}

    public Directory(String dirId, String projectId, String userId, String parentId, String dirName, String dirPath, Integer dirLevel) {
        this.dirId = dirId;
        this.projectId = projectId;
        this.userId = userId;
        this.parentId = parentId;
        this.dirName = dirName;
        this.dirPath = dirPath;
        this.dirLevel = dirLevel;
        this.sortOrder = 99;
        this.status = Status.ACTIVE;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    public Directory(String dirId, String projectId, String userId, String parentId, String dirName, String dirPath, Integer dirLevel, Integer sortOrder) {
        this.dirId = dirId;
        this.projectId = projectId;
        this.userId = userId;
        this.parentId = parentId;
        this.dirName = dirName;
        this.dirPath = dirPath;
        this.dirLevel = dirLevel;
        this.sortOrder = sortOrder == null ? 99 : sortOrder;
        this.status = Status.ACTIVE;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    // Getters and Setters
    public String getDirId() {
        return dirId;
    }

    public void setDirId(String dirId) {
        this.dirId = dirId;
    }

    public String getProjectId() {
        return projectId;
    }

    public void setProjectId(String projectId) {
        this.projectId = projectId;
        this.updatedAt = LocalDateTime.now();
    }

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
        this.updatedAt = LocalDateTime.now();
    }

    public String getParentId() {
        return parentId;
    }

    public void setParentId(String parentId) {
        this.parentId = parentId;
        this.updatedAt = LocalDateTime.now();
    }

    public String getDirName() {
        return dirName;
    }

    public void setDirName(String dirName) {
        this.dirName = dirName;
        this.updatedAt = LocalDateTime.now();
    }

    public String getDirPath() {
        return dirPath;
    }

    public void setDirPath(String dirPath) {
        this.dirPath = dirPath;
        this.updatedAt = LocalDateTime.now();
    }

    public Integer getDirLevel() {
        return dirLevel;
    }

    public void setDirLevel(Integer dirLevel) {
        this.dirLevel = dirLevel;
        this.updatedAt = LocalDateTime.now();
    }

    public Integer getSortOrder() {
        return sortOrder;
    }

    public void setSortOrder(Integer sortOrder) {
        this.sortOrder = sortOrder == null ? 99 : sortOrder;
        this.updatedAt = LocalDateTime.now();
    }

    public Status getStatus() {
        return status;
    }

    public void setStatus(Status status) {
        this.status = status;
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
        return "Directory{" +
                "dirId='" + dirId + '\'' +
                ", projectId='" + projectId + '\'' +
                ", userId='" + userId + '\'' +
                ", parentId='" + parentId + '\'' +
                ", dirName='" + dirName + '\'' +
                ", dirPath='" + dirPath + '\'' +
                ", dirLevel=" + dirLevel +
                ", sortOrder=" + sortOrder +
                ", status=" + status +
                ", createdAt=" + createdAt +
                ", updatedAt=" + updatedAt +
                '}';
    }
}
