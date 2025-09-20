package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

/**
 * 任务列表响应
 */
@Schema(description = "任务列表响应")
public class TaskListResponse {
    
    @JsonProperty("Tasks")
    @Schema(description = "任务列表", example = "[{...}]")
    private List<TaskListItem> tasks;
    
    @JsonProperty("TotalCount")
    @Schema(description = "任务总数", example = "5")
    private int totalCount;
    
    public TaskListResponse() {}
    
    public TaskListResponse(List<TaskListItem> tasks, int totalCount) {
        this.tasks = tasks;
        this.totalCount = totalCount;
    }
    
    public List<TaskListItem> getTasks() {
        return tasks;
    }
    
    public void setTasks(List<TaskListItem> tasks) {
        this.tasks = tasks;
    }
    
    public int getTotalCount() {
        return totalCount;
    }
    
    public void setTotalCount(int totalCount) {
        this.totalCount = totalCount;
    }
    
    /**
     * 任务列表项
     */
    @Schema(description = "任务列表项")
    public static class TaskListItem {
        
        @JsonProperty("Id")
        @Schema(description = "任务ID", example = "4ff0c9a1-2025-4c2e-9bee-cab39d78ea39")
        private String id;
        
        @JsonProperty("Name")
        @Schema(description = "任务名称", example = "PCB缺陷检测任务")
        private String name;
        
        @JsonProperty("Description")
        @Schema(description = "任务描述", example = "检测PCB板上的焊接缺陷")
        private String description;
        
        @JsonProperty("ProjectId")
        @Schema(description = "项目ID", example = "398d6a89-21ad-4fde-b798-32436ab2d047")
        private String projectId;
        
        @JsonProperty("UserId")
        @Schema(description = "用户ID", example = "user001")
        private String userId;
        
        @JsonProperty("AlgorithmType")
        @Schema(description = "算法类型", example = "object-detection")
        private String algorithmType;
        
        @JsonProperty("Status")
        @Schema(description = "任务状态", example = "completed", allowableValues = {"pending", "processing", "completed", "failed"})
        private String status;
        
        @JsonProperty("Progress")
        @Schema(description = "处理进度", example = "100")
        private int progress;
        
        @JsonProperty("FileCount")
        @Schema(description = "文件总数", example = "3")
        private int fileCount;
        
        @JsonProperty("ProcessedFiles")
        @Schema(description = "已处理文件数", example = "3")
        private int processedFiles;
        
        @JsonProperty("SuccessFiles")
        @Schema(description = "成功处理文件数", example = "3")
        private int successFiles;
        
        @JsonProperty("FailedFiles")
        @Schema(description = "失败处理文件数", example = "0")
        private int failedFiles;
        
        @JsonProperty("CreateTime")
        @Schema(description = "创建时间", example = "2025-06-25 12:31:45")
        private String createTime;
        
        @JsonProperty("UpdateTime")
        @Schema(description = "更新时间", example = "2025-06-25 12:32:15")
        private String updateTime;
        
        @JsonProperty("ErrorMessage")
        @Schema(description = "错误信息", example = "null")
        private String errorMessage;
        
        @JsonProperty("TaskFiles")
        @Schema(description = "任务文件列表")
        private List<TaskFileItem> taskFiles;
        
        public TaskListItem() {}
        
        public TaskListItem(String id, String name, String description, String projectId, String userId, 
                           String algorithmType, String status, int progress, int fileCount, 
                           int processedFiles, int successFiles, int failedFiles, 
                           String createTime, String updateTime, String errorMessage) {
            this.id = id;
            this.name = name;
            this.description = description;
            this.projectId = projectId;
            this.userId = userId;
            this.algorithmType = algorithmType;
            this.status = status;
            this.progress = progress;
            this.fileCount = fileCount;
            this.processedFiles = processedFiles;
            this.successFiles = successFiles;
            this.failedFiles = failedFiles;
            this.createTime = createTime;
            this.updateTime = updateTime;
            this.errorMessage = errorMessage;
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
        
        public String getStatus() { return status; }
        public void setStatus(String status) { this.status = status; }
        
        public int getProgress() { return progress; }
        public void setProgress(int progress) { this.progress = progress; }
        
        public int getFileCount() { return fileCount; }
        public void setFileCount(int fileCount) { this.fileCount = fileCount; }
        
        public int getProcessedFiles() { return processedFiles; }
        public void setProcessedFiles(int processedFiles) { this.processedFiles = processedFiles; }
        
        public int getSuccessFiles() { return successFiles; }
        public void setSuccessFiles(int successFiles) { this.successFiles = successFiles; }
        
        public int getFailedFiles() { return failedFiles; }
        public void setFailedFiles(int failedFiles) { this.failedFiles = failedFiles; }
        
        public String getCreateTime() { return createTime; }
        public void setCreateTime(String createTime) { this.createTime = createTime; }
        
        public String getUpdateTime() { return updateTime; }
        public void setUpdateTime(String updateTime) { this.updateTime = updateTime; }
        
        public String getErrorMessage() { return errorMessage; }
        public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
        
        public List<TaskFileItem> getTaskFiles() { return taskFiles; }
        public void setTaskFiles(List<TaskFileItem> taskFiles) { this.taskFiles = taskFiles; }
    }
    
    /**
     * 任务文件项
     */
    @Schema(description = "任务文件项")
    public static class TaskFileItem {
        
        @JsonProperty("TaskFileId")
        @Schema(description = "任务文件ID", example = "xxx-xxx-xxx")
        private String taskFileId;
        
        @JsonProperty("FileId")
        @Schema(description = "文件ID", example = "4852273e-b64a-44a7-b676-94b533c3ac23")
        private String fileId;
        
        @JsonProperty("FileName")
        @Schema(description = "文件名", example = "001.jpg")
        private String fileName;
        
        @JsonProperty("LogicalPath")
        @Schema(description = "逻辑路径", example = "/test-images/defective/001.jpg")
        private String logicalPath;
        
        @JsonProperty("Status")
        @Schema(description = "处理状态", example = "completed", allowableValues = {"pending", "processing", "completed", "failed"})
        private String status;
        
        @JsonProperty("VisionResult")
        @Schema(description = "视觉检测结果", example = "{\"detections\": []}")
        private String visionResult;
        
        @JsonProperty("LlmResult")
        @Schema(description = "LLM分析结果", example = "检测报告内容")
        private String llmResult;
        
        @JsonProperty("ReportPath")
        @Schema(description = "报告路径", example = "null")
        private String reportPath;
        
        @JsonProperty("ErrorMessage")
        @Schema(description = "错误信息", example = "null")
        private String errorMessage;
        
        @JsonProperty("ProcessingStartTime")
        @Schema(description = "处理开始时间", example = "2025-06-25 12:31:50")
        private String processingStartTime;
        
        @JsonProperty("ProcessingEndTime")
        @Schema(description = "处理结束时间", example = "2025-06-25 12:32:10")
        private String processingEndTime;
        
        public TaskFileItem() {}
        
        public TaskFileItem(String taskFileId, String fileId, String fileName, String logicalPath, 
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
} 