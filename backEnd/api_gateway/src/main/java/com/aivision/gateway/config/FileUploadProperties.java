package com.aivision.gateway.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@ConfigurationProperties(prefix = "file-upload")
public class FileUploadProperties {
    
    private List<String> allowedImageTypes;
    private String maxFileSize;
    private String maxTotalSize;
    private Integer batchMaxFiles = 10;
    private String batchMaxSize = "500MB";
    private Integer batchTimeoutBaseMs = 60000;
    private Integer batchTimeoutMsPerMB = 1500;
    private Integer maxRetries = 1;
    private LocalConfig local;
    
    // Getters and Setters
    public List<String> getAllowedImageTypes() {
        return allowedImageTypes;
    }
    
    public void setAllowedImageTypes(List<String> allowedImageTypes) {
        this.allowedImageTypes = allowedImageTypes;
    }
    
    public String getMaxFileSize() {
        return maxFileSize;
    }
    
    public void setMaxFileSize(String maxFileSize) {
        this.maxFileSize = maxFileSize;
    }
    
    public String getMaxTotalSize() {
        return maxTotalSize;
    }
    
    public void setMaxTotalSize(String maxTotalSize) {
        this.maxTotalSize = maxTotalSize;
    }

    public Integer getBatchMaxFiles() {
        return batchMaxFiles;
    }

    public void setBatchMaxFiles(Integer batchMaxFiles) {
        this.batchMaxFiles = batchMaxFiles;
    }

    public String getBatchMaxSize() {
        return batchMaxSize;
    }

    public void setBatchMaxSize(String batchMaxSize) {
        this.batchMaxSize = batchMaxSize;
    }

    public Integer getBatchTimeoutBaseMs() {
        return batchTimeoutBaseMs;
    }

    public void setBatchTimeoutBaseMs(Integer batchTimeoutBaseMs) {
        this.batchTimeoutBaseMs = batchTimeoutBaseMs;
    }

    public Integer getBatchTimeoutMsPerMB() {
        return batchTimeoutMsPerMB;
    }

    public void setBatchTimeoutMsPerMB(Integer batchTimeoutMsPerMB) {
        this.batchTimeoutMsPerMB = batchTimeoutMsPerMB;
    }

    public Integer getMaxRetries() {
        return maxRetries;
    }

    public void setMaxRetries(Integer maxRetries) {
        this.maxRetries = maxRetries;
    }
    
    public LocalConfig getLocal() { return local; }
    public void setLocal(LocalConfig local) { this.local = local; }

    // Local storage config
    public static class LocalConfig {
        private String baseDir;
        public String getBaseDir() { return baseDir; }
        public void setBaseDir(String baseDir) { this.baseDir = baseDir; }
    }
}
