package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import javax.persistence.*;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "task_file", indexes = {
    @Index(name = "idx_task_file_weld_id", columnList = "weld_id")
})
public class TaskFile {
    
    public enum Status {
        PENDING, PROCESSING, COMPLETED, FAILED
    }

    public enum ReviewStatus {
        PENDING, CONFIRMED
    }
    
    @Id
    @Column(name = "task_file_id", length = 255)
    @JsonProperty("TaskFileId")
    private String taskFileId;
    
    @Column(name = "task_id", nullable = false, length = 255)
    @JsonProperty("TaskId")
    private String taskId;
    
    @Column(name = "file_id", nullable = false, length = 255)
    @JsonProperty("FileId")
    private String fileId;
    
    @Column(name = "logical_file_path", nullable = false, length = 500)
    @JsonProperty("LogicalPath")
    private String logicalFilePath;
    
    @Column(name = "minio_file_path", length = 500)
    @JsonProperty("MinioFilePath")
    private String minioFilePath;
    
    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    @JsonProperty("Status")
    private Status status = Status.PENDING;
    
    @Column(name = "vision_result", columnDefinition = "TEXT")
    @JsonProperty("VisionResult")
    private String visionResult;
    
    @Column(name = "report_path", length = 500)
    @JsonProperty("ReportPath")
    private String reportPath;
    
    @Column(name = "error_message", columnDefinition = "TEXT")
    @JsonProperty("ErrorMessage")
    private String errorMessage;

    @Enumerated(EnumType.STRING)
    @Column(name = "review_status", length = 20)
    @JsonProperty("ReviewStatus")
    private ReviewStatus reviewStatus = ReviewStatus.PENDING;

    @Column(name = "manual_result", columnDefinition = "TEXT")
    @JsonProperty("ManualResult")
    private String manualResult;

    @Column(name = "plate_quality", length = 50)
    @JsonProperty("PlateQuality")
    private String plateQuality;

    // --- 新增：底片信息字段 ---
    @Column(name = "weld_id", length = 100)
    @JsonProperty("WeldId")
    private String weldId;

    @Column(name = "film_number", length = 100)
    @JsonProperty("FilmNumber")
    private String filmNumber;

    @Column(name = "film_density", length = 50)
    @JsonProperty("FilmDensity")
    private String filmDensity;

    @Column(name = "sensitivity", length = 50)
    @JsonProperty("Sensitivity")
    private String sensitivity;

    // --- 新增：缺陷记录列表（一对多关系）---
    @OneToMany(cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    @JoinColumn(name = "task_file_id", referencedColumnName = "task_file_id", insertable = false, updatable = false)
    @JsonProperty("DefectRecords")
    private List<DefectRecord> defectRecords = new ArrayList<>();
    
    @Column(name = "processing_start_time")
    @JsonProperty("ProcessingStartTime")
    private LocalDateTime processingStartTime;
    
    @Column(name = "processing_end_time")
    @JsonProperty("ProcessingEndTime")
    private LocalDateTime processingEndTime;
    
    @Column(name = "created_at")
    @JsonProperty("CreatedAt")
    private LocalDateTime createdAt;
    
    @Column(name = "updated_at")
    @JsonProperty("UpdatedAt")
    private LocalDateTime updatedAt;
    
    @Transient
    @JsonProperty("FileName")
    private String fileName;

    // 构造函数
    public TaskFile() {}
    
    public TaskFile(String taskFileId, String taskId, String fileId, 
                    String logicalFilePath, String minioFilePath) {
        this.taskFileId = taskFileId;
        this.taskId = taskId;
        this.fileId = fileId;
        this.logicalFilePath = logicalFilePath;
        this.minioFilePath = minioFilePath;
        this.status = Status.PENDING;
        this.reviewStatus = ReviewStatus.PENDING;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }
    
    // Getters and Setters
    public String getTaskFileId() {
        return taskFileId;
    }
    
    public void setTaskFileId(String taskFileId) {
        this.taskFileId = taskFileId;
    }
    
    public String getTaskId() {
        return taskId;
    }
    
    public void setTaskId(String taskId) {
        this.taskId = taskId;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getFileId() {
        return fileId;
    }
    
    public void setFileId(String fileId) {
        this.fileId = fileId;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getLogicalFilePath() {
        return logicalFilePath;
    }
    
    public void setLogicalFilePath(String logicalFilePath) {
        this.logicalFilePath = logicalFilePath;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getMinioFilePath() {
        return minioFilePath;
    }
    
    public void setMinioFilePath(String minioFilePath) {
        this.minioFilePath = minioFilePath;
        this.updatedAt = LocalDateTime.now();
    }
    
    public Status getStatus() {
        return status;
    }
    
    public void setStatus(Status status) {
        this.status = status;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getVisionResult() {
        return visionResult;
    }
    
    public void setVisionResult(String visionResult) {
        this.visionResult = visionResult;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getReportPath() {
        return reportPath;
    }
    
    public void setReportPath(String reportPath) {
        this.reportPath = reportPath;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getErrorMessage() {
        return errorMessage;
    }
    
    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
        this.updatedAt = LocalDateTime.now();
    }

    public ReviewStatus getReviewStatus() {
        return reviewStatus;
    }

    public void setReviewStatus(ReviewStatus reviewStatus) {
        this.reviewStatus = reviewStatus;
        this.updatedAt = LocalDateTime.now();
    }

    public String getManualResult() {
        return manualResult;
    }

    public void setManualResult(String manualResult) {
        this.manualResult = manualResult;
        this.updatedAt = LocalDateTime.now();
    }

    public String getPlateQuality() {
        return plateQuality;
    }

    public void setPlateQuality(String plateQuality) {
        this.plateQuality = plateQuality;
        this.updatedAt = LocalDateTime.now();
    }

    // --- 新增字段的 Getters and Setters ---
    public String getWeldId() {
        return weldId;
    }

    public void setWeldId(String weldId) {
        this.weldId = weldId;
        this.updatedAt = LocalDateTime.now();
    }

    public String getFilmNumber() {
        return filmNumber;
    }

    public void setFilmNumber(String filmNumber) {
        this.filmNumber = filmNumber;
        this.updatedAt = LocalDateTime.now();
    }

    public String getFilmDensity() {
        return filmDensity;
    }

    public void setFilmDensity(String filmDensity) {
        this.filmDensity = filmDensity;
        this.updatedAt = LocalDateTime.now();
    }

    public String getSensitivity() {
        return sensitivity;
    }

    public void setSensitivity(String sensitivity) {
        this.sensitivity = sensitivity;
        this.updatedAt = LocalDateTime.now();
    }

    public List<DefectRecord> getDefectRecords() {
        return defectRecords;
    }

    public void setDefectRecords(List<DefectRecord> defectRecords) {
        this.defectRecords = defectRecords;
        this.updatedAt = LocalDateTime.now();
    }
    
    public LocalDateTime getProcessingStartTime() {
        return processingStartTime;
    }
    
    public void setProcessingStartTime(LocalDateTime processingStartTime) {
        this.processingStartTime = processingStartTime;
        this.updatedAt = LocalDateTime.now();
    }
    
    public LocalDateTime getProcessingEndTime() {
        return processingEndTime;
    }
    
    public void setProcessingEndTime(LocalDateTime processingEndTime) {
        this.processingEndTime = processingEndTime;
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
    
    public String getFileName() {
        return fileName;
    }

    public void setFileName(String fileName) {
        this.fileName = fileName;
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
    
    /**
     * 计算处理时间（毫秒）
     */
    public Long getProcessingTimeMs() {
        if (processingStartTime != null && processingEndTime != null) {
            return java.time.Duration.between(processingStartTime, processingEndTime).toMillis();
        }
        return null;
    }
    
    @Override
    public String toString() {
        return "TaskFile{" +
                "taskFileId='" + taskFileId + '\'' +
                ", taskId='" + taskId + '\'' +
                ", fileId='" + fileId + '\'' +
                ", logicalFilePath='" + logicalFilePath + '\'' +
                ", minioFilePath='" + minioFilePath + '\'' +
                ", status=" + status +
                ", reviewStatus=" + reviewStatus +
                ", reportPath='" + reportPath + '\'' +
                ", errorMessage='" + errorMessage + '\'' +
                ", processingStartTime=" + processingStartTime +
                ", processingEndTime=" + processingEndTime +
                ", createdAt=" + createdAt +
                ", updatedAt=" + updatedAt +
                '}';
    }
}
