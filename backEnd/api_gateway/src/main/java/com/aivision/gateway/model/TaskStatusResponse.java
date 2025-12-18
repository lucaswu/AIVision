package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;
import java.util.List;

public class TaskStatusResponse {
    
    @JsonProperty("Id")
    private String id;
    
    @JsonProperty("Name")
    private String name;
    
    @JsonProperty("Description")
    private String description;
    
    @JsonProperty("ProjectId")
    private String projectId;
    
    @JsonProperty("UserId")
    private String userId;
    
    @JsonProperty("AlgorithmType")
    private String algorithmType;
    
    @JsonProperty("FileCount")
    private Integer fileCount;
    
    @JsonProperty("ProcessedFiles")
    private Integer processedFiles;
    
    @JsonProperty("SuccessFiles")
    private Integer successFiles;
    
    @JsonProperty("FailedFiles")
    private Integer failedFiles;
    
    @JsonProperty("CreateTime")
    private String createTime;
    
    @JsonProperty("UpdateTime")
    private String updateTime;
    
    @JsonProperty("Status")
    private String status;
    
    @JsonProperty("Progress")
    private Integer progress;
    
    @JsonProperty("ErrorMessage")
    private String errorMessage;
    
    @JsonProperty("SelectedFiles")
    private List<TaskFileResult> selectedFiles;
    
    @JsonProperty("ProcessingFiles")
    @Schema(description = "正在处理的文件数量", example = "1")
    private Integer processingFiles;
    
    @JsonProperty("InQueueFiles")
    @Schema(description = "等待处理的文件数量", example = "2")
    private Integer inQueueFiles;

    @JsonProperty("IsArchived")
    private Boolean isArchived;

    @JsonProperty("EndTime")
    private String endTime;

    @JsonProperty("TaskReport")
    private String taskReport;
    
    // 内部类：任务文件结果
    public static class TaskFileResult {
        @JsonProperty("TaskFileId")
        private String taskFileId;
        
        @JsonProperty("FileId")
        private String fileId;
        
        @JsonProperty("FileName")
        private String fileName;
        
        @JsonProperty("LogicalPath")
        private String logicalPath;
        
        @JsonProperty("Status")
        private String status;
        
        @JsonProperty("VisionResult")
        private String visionResult;
        
        @JsonProperty("LlmResult")
        private String llmResult;
        
        @JsonProperty("ReportPath")
        private String reportPath;
        
        @JsonProperty("ErrorMessage")
        private String errorMessage;
        
        @JsonProperty("ProcessingStartTime")
        private String processingStartTime;
        
        @JsonProperty("ProcessingEndTime")
        private String processingEndTime;
        
        // 构造函数
        public TaskFileResult() {}
        
        public TaskFileResult(String taskFileId, String fileId, String fileName, String logicalPath, 
                             String status, String visionResult, String llmResult, String reportPath, 
                             String errorMessage, String processingStartTime, String processingEndTime) {
            this.taskFileId = taskFileId;
            this.fileId = fileId;
            this.fileName = fileName;
            this.logicalPath = logicalPath;
            this.status = status;
            this.visionResult = visionResult;
            this.llmResult = llmResult;
            this.reportPath = reportPath;
            this.errorMessage = errorMessage;
            this.processingStartTime = processingStartTime;
            this.processingEndTime = processingEndTime;
        }
        
        // Getters and Setters
        public String getTaskFileId() { return taskFileId; }
        public void setTaskFileId(String taskFileId) { this.taskFileId = taskFileId; }
        
        public String getFileId() { return fileId; }
        public void setFileId(String fileId) { this.fileId = fileId; }
        
        public String getFileName() { return fileName; }
        public void setFileName(String fileName) { this.fileName = fileName; }
        
        public String getLogicalPath() { return logicalPath; }
        public void setLogicalPath(String logicalPath) { this.logicalPath = logicalPath; }
        
        public String getStatus() { return status; }
        public void setStatus(String status) { this.status = status; }
        
        public String getVisionResult() { return visionResult; }
        public void setVisionResult(String visionResult) { this.visionResult = visionResult; }
        
        public String getLlmResult() { return llmResult; }
        public void setLlmResult(String llmResult) { this.llmResult = llmResult; }
        
        public String getReportPath() { return reportPath; }
        public void setReportPath(String reportPath) { this.reportPath = reportPath; }
        
        public String getErrorMessage() { return errorMessage; }
        public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
        
        public String getProcessingStartTime() { return processingStartTime; }
        public void setProcessingStartTime(String processingStartTime) { this.processingStartTime = processingStartTime; }
        
        public String getProcessingEndTime() { return processingEndTime; }
        public void setProcessingEndTime(String processingEndTime) { this.processingEndTime = processingEndTime; }
    }
    
    // 构造函数
    public TaskStatusResponse() {}
    
    public TaskStatusResponse(String id, String name, String description, String projectId, String userId,
                             String algorithmType, Integer fileCount, Integer processedFiles, 
                             Integer successFiles, Integer failedFiles, String createTime, String updateTime,
                             String status, Integer progress, String errorMessage, List<TaskFileResult> selectedFiles,
                             Integer processingFiles, Integer inQueueFiles) {
        this.id = id;
        this.name = name;
        this.description = description;
        this.projectId = projectId;
        this.userId = userId;
        this.algorithmType = algorithmType;
        this.fileCount = fileCount;
        this.processedFiles = processedFiles;
        this.successFiles = successFiles;
        this.failedFiles = failedFiles;
        this.createTime = createTime;
        this.updateTime = updateTime;
        this.status = status;
        this.progress = progress;
        this.errorMessage = errorMessage;
        this.selectedFiles = selectedFiles;
        this.processingFiles = processingFiles;
        this.inQueueFiles = inQueueFiles;
    }
    
    // Getters and Setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    
    public String getProjectId() { return projectId; }
    public void setProjectId(String projectId) { this.projectId = projectId; }
    
    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }
    
    public String getAlgorithmType() { return algorithmType; }
    public void setAlgorithmType(String algorithmType) { this.algorithmType = algorithmType; }
    
    public Integer getFileCount() { return fileCount; }
    public void setFileCount(Integer fileCount) { this.fileCount = fileCount; }
    
    public Integer getProcessedFiles() { return processedFiles; }
    public void setProcessedFiles(Integer processedFiles) { this.processedFiles = processedFiles; }
    
    public Integer getSuccessFiles() { return successFiles; }
    public void setSuccessFiles(Integer successFiles) { this.successFiles = successFiles; }
    
    public Integer getFailedFiles() { return failedFiles; }
    public void setFailedFiles(Integer failedFiles) { this.failedFiles = failedFiles; }
    
    public String getCreateTime() { return createTime; }
    public void setCreateTime(String createTime) { this.createTime = createTime; }
    
    public String getUpdateTime() { return updateTime; }
    public void setUpdateTime(String updateTime) { this.updateTime = updateTime; }
    
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    
    public Integer getProgress() { return progress; }
    public void setProgress(Integer progress) { this.progress = progress; }
    
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    
    public List<TaskFileResult> getSelectedFiles() { return selectedFiles; }
    public void setSelectedFiles(List<TaskFileResult> selectedFiles) { this.selectedFiles = selectedFiles; }
    
    public Integer getProcessingFiles() { return processingFiles; }
    public void setProcessingFiles(Integer processingFiles) { this.processingFiles = processingFiles; }
    
    public Integer getInQueueFiles() { return inQueueFiles; }
    public void setInQueueFiles(Integer inQueueFiles) { this.inQueueFiles = inQueueFiles; }

    public Boolean getIsArchived() { return isArchived; }
    public void setIsArchived(Boolean isArchived) { this.isArchived = isArchived; }

    public String getEndTime() { return endTime; }
    public void setEndTime(String endTime) { this.endTime = endTime; }

    public String getTaskReport() { return taskReport; }
    public void setTaskReport(String taskReport) { this.taskReport = taskReport; }
} 