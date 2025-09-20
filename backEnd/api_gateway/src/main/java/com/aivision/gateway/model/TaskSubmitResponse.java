package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public class TaskSubmitResponse {
    
    @JsonProperty("TaskId")
    private String taskId;
    
    @JsonProperty("Status")
    private String status;
    
    @JsonProperty("FileCount")
    private Integer fileCount;
    
    @JsonProperty("Timestamp")
    private String timestamp;
    
    // 构造函数
    public TaskSubmitResponse() {}
    
    public TaskSubmitResponse(String taskId, String status, Integer fileCount, String timestamp) {
        this.taskId = taskId;
        this.status = status;
        this.fileCount = fileCount;
        this.timestamp = timestamp;
    }
    
    // Getters and Setters
    public String getTaskId() {
        return taskId;
    }
    
    public void setTaskId(String taskId) {
        this.taskId = taskId;
    }
    
    public String getStatus() {
        return status;
    }
    
    public void setStatus(String status) {
        this.status = status;
    }
    
    public Integer getFileCount() {
        return fileCount;
    }
    
    public void setFileCount(Integer fileCount) {
        this.fileCount = fileCount;
    }
    
    public String getTimestamp() {
        return timestamp;
    }
    
    public void setTimestamp(String timestamp) {
        this.timestamp = timestamp;
    }
    
    @Override
    public String toString() {
        return "TaskSubmitResponse{" +
                "taskId='" + taskId + '\'' +
                ", status='" + status + '\'' +
                ", fileCount=" + fileCount +
                ", timestamp='" + timestamp + '\'' +
                '}';
    }
} 