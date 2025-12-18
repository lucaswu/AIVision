package com.aivision.gateway.model;

import javax.persistence.*;
import java.time.LocalDateTime;
import java.util.List;

@Entity
@Table(name = "task")
public class Task {
    
    public enum Status {
        PENDING, PROCESSING, COMPLETED, FAILED
    }
    
    @Id
    @Column(name = "task_id", length = 255)
    private String taskId;
    
    @Column(name = "project_id", nullable = false, length = 255)
    private String projectId;
    
    @Column(name = "user_id", nullable = false, length = 255)
    private String userId;
    
    @Column(name = "task_name", nullable = false, length = 255)
    private String taskName;
    
    @Column(name = "description", columnDefinition = "TEXT")
    private String description;
    
    @Column(name = "algorithm_type", nullable = false, length = 50)
    private String algorithmType = "object-detection";
    
    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private Status status = Status.PENDING;
    
    @Column(name = "total_files", nullable = false)
    private Integer totalFiles = 0;
    
    @Column(name = "processed_files", nullable = false)
    private Integer processedFiles = 0;
    
    @Column(name = "success_files", nullable = false)
    private Integer successFiles = 0;
    
    @Column(name = "failed_files", nullable = false)
    private Integer failedFiles = 0;
    
    @Column(name = "progress", nullable = false)
    private Integer progress = 0;
    
    @Column(name = "parallel_count", nullable = false)
    private Integer parallelCount = 10;
    
    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;
    
    @Column(name = "is_archived", nullable = false)
    private Boolean isArchived = false;
    
    @Column(name = "task_report", columnDefinition = "TEXT")
    private String taskReport;
    
    @Column(name = "end_time")
    private LocalDateTime endTime;
    
    @Column(name = "created_at")
    private LocalDateTime createdAt;
    
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
    
    // 关联的任务文件（可选，用于查询）
    @OneToMany(mappedBy = "taskId", fetch = FetchType.LAZY)
    private List<TaskFile> taskFiles;
    
    // 构造函数
    public Task() {}
    
    public Task(String taskId, String projectId, String userId, String taskName, 
                String description, String algorithmType, Integer totalFiles) {
        this.taskId = taskId;
        this.projectId = projectId;
        this.userId = userId;
        this.taskName = taskName;
        this.description = description;
        this.algorithmType = algorithmType;
        this.totalFiles = totalFiles;
        this.status = Status.PENDING;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }
    
    // Getters and Setters
    public String getTaskId() {
        return taskId;
    }
    
    public void setTaskId(String taskId) {
        this.taskId = taskId;
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
    
    public String getTaskName() {
        return taskName;
    }
    
    public void setTaskName(String taskName) {
        this.taskName = taskName;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getDescription() {
        return description;
    }
    
    public void setDescription(String description) {
        this.description = description;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getAlgorithmType() {
        return algorithmType;
    }
    
    public void setAlgorithmType(String algorithmType) {
        this.algorithmType = algorithmType;
        this.updatedAt = LocalDateTime.now();
    }
    
    public Status getStatus() {
        return status;
    }
    
    public void setStatus(Status status) {
        this.status = status;
        this.updatedAt = LocalDateTime.now();
    }
    
    public Integer getTotalFiles() {
        return totalFiles;
    }
    
    public void setTotalFiles(Integer totalFiles) {
        this.totalFiles = totalFiles;
        this.updatedAt = LocalDateTime.now();
    }
    
    public Integer getProcessedFiles() {
        return processedFiles;
    }
    
    public void setProcessedFiles(Integer processedFiles) {
        this.processedFiles = processedFiles;
        // 自动计算进度
        if (this.totalFiles != null && this.totalFiles > 0) {
            this.progress = (processedFiles * 100) / this.totalFiles;
        }
        this.updatedAt = LocalDateTime.now();
    }
    
    public Integer getSuccessFiles() {
        return successFiles;
    }
    
    public void setSuccessFiles(Integer successFiles) {
        this.successFiles = successFiles;
        this.updatedAt = LocalDateTime.now();
    }
    
    public Integer getFailedFiles() {
        return failedFiles;
    }
    
    public void setFailedFiles(Integer failedFiles) {
        this.failedFiles = failedFiles;
        this.updatedAt = LocalDateTime.now();
    }
    
    public Integer getProgress() {
        return progress;
    }
    
    public void setProgress(Integer progress) {
        this.progress = progress;
        this.updatedAt = LocalDateTime.now();
    }
    
    public Integer getParallelCount() {
        return parallelCount;
    }
    
    public void setParallelCount(Integer parallelCount) {
        this.parallelCount = parallelCount;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getErrorMessage() {
        return errorMessage;
    }
    
    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
        this.updatedAt = LocalDateTime.now();
    }
    
    public Boolean getIsArchived() {
        return isArchived;
    }

    public void setIsArchived(Boolean isArchived) {
        this.isArchived = isArchived;
        this.updatedAt = LocalDateTime.now();
    }

    public String getTaskReport() {
        return taskReport;
    }

    public void setTaskReport(String taskReport) {
        this.taskReport = taskReport;
        this.updatedAt = LocalDateTime.now();
    }

    public LocalDateTime getEndTime() {
        return endTime;
    }

    public void setEndTime(LocalDateTime endTime) {
        this.endTime = endTime;
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
    
    public List<TaskFile> getTaskFiles() {
        return taskFiles;
    }
    
    public void setTaskFiles(List<TaskFile> taskFiles) {
        this.taskFiles = taskFiles;
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
        return "Task{" +
                "taskId='" + taskId + '\'' +
                ", projectId='" + projectId + '\'' +
                ", userId='" + userId + '\'' +
                ", taskName='" + taskName + '\'' +
                ", description='" + description + '\'' +
                ", algorithmType='" + algorithmType + '\'' +
                ", status=" + status +
                ", totalFiles=" + totalFiles +
                ", processedFiles=" + processedFiles +
                ", successFiles=" + successFiles +
                ", failedFiles=" + failedFiles +
                ", progress=" + progress +
                ", parallelCount=" + parallelCount +
                ", errorMessage='" + errorMessage + '\'' +
                ", createdAt=" + createdAt +
                ", updatedAt=" + updatedAt +
                '}';
    }
} 