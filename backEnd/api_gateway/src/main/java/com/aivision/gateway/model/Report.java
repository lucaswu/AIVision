package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import javax.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "report")
public class Report {
    
    public enum Status {
        PENDING, COMPLETED, ARCHIVED
    }
    
    @Id
    @Column(name = "report_id", length = 255)
    @JsonProperty("ReportId")
    private String reportId;
    
    @Column(name = "task_id", nullable = false, unique = true, length = 255)
    @JsonProperty("TaskId")
    private String taskId;
    
    @Column(name = "project_id", nullable = false, length = 255)
    @JsonProperty("ProjectId")
    private String projectId;
    
    @Column(name = "user_id", nullable = false, length = 255)
    @JsonProperty("UserId")
    private String userId;
    
    @Column(name = "report_name", nullable = false, length = 255)
    @JsonProperty("ReportName")
    private String reportName;
    
    @Transient // 不持久化到数据库，仅用于接口返回
    @JsonProperty("TaskName")
    private String taskName;

    @Column(name = "total_files")
    @JsonProperty("TotalFiles")
    private Integer totalFiles = 0;
    
    @Column(name = "confirmed_files")
    @JsonProperty("ConfirmedFiles")
    private Integer confirmedFiles = 0;
    
    @Column(name = "total_defects")
    @JsonProperty("TotalDefects")
    private Integer totalDefects = 0;
    
    @Column(name = "severe_defects")
    @JsonProperty("SevereDefects")
    private Integer severeDefects = 0;
    
    @Column(name = "normal_defects")
    @JsonProperty("NormalDefects")
    private Integer normalDefects = 0;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", length = 20)
    @JsonProperty("Status")
    private Status status = Status.PENDING;

    @Column(name = "created_at")
    @JsonProperty("CreatedAt")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    @JsonProperty("UpdatedAt")
    private LocalDateTime updatedAt;

    public Report() {}

    public Report(String reportId, String taskId, String projectId, String userId, String reportName) {
        this.reportId = reportId;
        this.taskId = taskId;
        this.projectId = projectId;
        this.userId = userId;
        this.reportName = reportName;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    // Getters and Setters
    public String getReportId() { return reportId; }
    public void setReportId(String reportId) { this.reportId = reportId; }

    public String getTaskId() { return taskId; }
    public void setTaskId(String taskId) { this.taskId = taskId; }

    public String getProjectId() { return projectId; }
    public void setProjectId(String projectId) { this.projectId = projectId; }

    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }

    public String getReportName() { return reportName; }
    public void setReportName(String reportName) { this.reportName = reportName; }

    public String getTaskName() { return taskName; }
    public void setTaskName(String taskName) { this.taskName = taskName; }

    public Integer getTotalFiles() { return totalFiles; }
    public void setTotalFiles(Integer totalFiles) { this.totalFiles = totalFiles; }

    public Integer getConfirmedFiles() { return confirmedFiles; }
    public void setConfirmedFiles(Integer confirmedFiles) { this.confirmedFiles = confirmedFiles; }

    public Integer getTotalDefects() { return totalDefects; }
    public void setTotalDefects(Integer totalDefects) { this.totalDefects = totalDefects; }

    public Integer getSevereDefects() { return severeDefects; }
    public void setSevereDefects(Integer severeDefects) { this.severeDefects = severeDefects; }

    public Integer getNormalDefects() { return normalDefects; }
    public void setNormalDefects(Integer normalDefects) { this.normalDefects = normalDefects; }

    public Status getStatus() { return status; }
    public void setStatus(Status status) { this.status = status; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
    
    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }
    
    @PreUpdate
    protected void onUpdate() {
        this.updatedAt = LocalDateTime.now();
    }
}


