package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public class FileUploadResponse {
    
    @JsonProperty("SuccessCount")
    private int successCount;
    
    @JsonProperty("FailedCount")
    private int failedCount;
    
    @JsonProperty("SuccessFiles")
    private List<SuccessFileInfo> successFiles;
    
    @JsonProperty("FailedFiles")
    private List<FailedFileInfo> failedFiles;
    
    // 构造函数
    public FileUploadResponse() {}
    
    public FileUploadResponse(int successCount, int failedCount, 
                             List<SuccessFileInfo> successFiles, List<FailedFileInfo> failedFiles) {
        this.successCount = successCount;
        this.failedCount = failedCount;
        this.successFiles = successFiles;
        this.failedFiles = failedFiles;
    }
    
    // Getters and Setters
    public int getSuccessCount() {
        return successCount;
    }
    
    public void setSuccessCount(int successCount) {
        this.successCount = successCount;
    }
    
    public int getFailedCount() {
        return failedCount;
    }
    
    public void setFailedCount(int failedCount) {
        this.failedCount = failedCount;
    }
    
    public List<SuccessFileInfo> getSuccessFiles() {
        return successFiles;
    }
    
    public void setSuccessFiles(List<SuccessFileInfo> successFiles) {
        this.successFiles = successFiles;
    }
    
    public List<FailedFileInfo> getFailedFiles() {
        return failedFiles;
    }
    
    public void setFailedFiles(List<FailedFileInfo> failedFiles) {
        this.failedFiles = failedFiles;
    }
    
    // 成功文件信息
    public static class SuccessFileInfo {
        @JsonProperty("FileId")
        private String fileId;
        
        @JsonProperty("OriginalName")
        private String originalName;
        
        @JsonProperty("FileSize")
        private Long fileSize;
        
        @JsonProperty("FilePath")
        private String filePath;
        
        public SuccessFileInfo() {}
        
        public SuccessFileInfo(String fileId, String originalName, Long fileSize, String filePath) {
            this.fileId = fileId;
            this.originalName = originalName;
            this.fileSize = fileSize;
            this.filePath = filePath;
        }
        
        public String getFileId() {
            return fileId;
        }
        
        public void setFileId(String fileId) {
            this.fileId = fileId;
        }
        
        public String getOriginalName() {
            return originalName;
        }
        
        public void setOriginalName(String originalName) {
            this.originalName = originalName;
        }
        
        public Long getFileSize() {
            return fileSize;
        }
        
        public void setFileSize(Long fileSize) {
            this.fileSize = fileSize;
        }
        
        public String getFilePath() {
            return filePath;
        }
        
        public void setFilePath(String filePath) {
            this.filePath = filePath;
        }
    }
    
    // 失败文件信息
    public static class FailedFileInfo {
        @JsonProperty("OriginalName")
        private String originalName;
        
        @JsonProperty("ErrorMessage")
        private String errorMessage;
        
        public FailedFileInfo() {}
        
        public FailedFileInfo(String originalName, String errorMessage) {
            this.originalName = originalName;
            this.errorMessage = errorMessage;
        }
        
        public String getOriginalName() {
            return originalName;
        }
        
        public void setOriginalName(String originalName) {
            this.originalName = originalName;
        }
        
        public String getErrorMessage() {
            return errorMessage;
        }
        
        public void setErrorMessage(String errorMessage) {
            this.errorMessage = errorMessage;
        }
    }
} 