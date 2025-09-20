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
    private MinioConfig minio;
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
    
    public MinioConfig getMinio() {
        return minio;
    }
    
    public void setMinio(MinioConfig minio) {
        this.minio = minio;
    }
    public LocalConfig getLocal() { return local; }
    public void setLocal(LocalConfig local) { this.local = local; }
    
    // MinIO配置子类
    public static class MinioConfig {
        private String bucketName;
        private String accessPolicy;
        
        public String getBucketName() {
            return bucketName;
        }
        
        public void setBucketName(String bucketName) {
            this.bucketName = bucketName;
        }
        
        public String getAccessPolicy() {
            return accessPolicy;
        }
        
        public void setAccessPolicy(String accessPolicy) {
            this.accessPolicy = accessPolicy;
        }
    }

    // Local storage config
    public static class LocalConfig {
        private String baseDir;
        public String getBaseDir() { return baseDir; }
        public void setBaseDir(String baseDir) { this.baseDir = baseDir; }
    }
} 