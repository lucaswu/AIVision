package com.aivision.gateway.model;

import javax.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "file", indexes = {
    // 上传幂等查询的覆盖索引：findByProjectIdAndDirectoryIdAndUploadSessionIdAndUploadKey
    // 在 ddl-auto=update 下随表自动创建，消除上传热路径的全表顺序扫描
    @Index(name = "idx_file_upload_idem",
        columnList = "project_id,directory_id,upload_session_id,upload_key")
})
public class File {
    
    @Id
    @Column(name = "file_id", length = 255)
    private String fileId;
    
    @Column(name = "project_id", nullable = false, length = 255)
    private String projectId;
    
    @Column(name = "user_id", nullable = false, length = 255)
    private String userId;
    
    @Column(name = "directory_id", nullable = false, length = 255)
    private String directoryId;
    
    @Column(name = "original_name", nullable = false, length = 255)
    private String originalName;
    
    @Column(name = "stored_name", nullable = false, length = 255)
    private String storedName;
    
    @Column(name = "file_path", nullable = false, length = 500)
    private String filePath;
    
    @Column(name = "file_size", nullable = false)
    private Long fileSize;
    
    @Column(name = "mime_type", length = 100)
    private String mimeType;
    
    @Column(name = "file_extension", length = 10)
    private String fileExtension;
    
    @Column(name = "created_at")
    private LocalDateTime createdAt;
    
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    /** JPEG 预览图在 Storage 中的路径；NULL 表示尚未生成或转换仍在进行中 */
    @Column(name = "thumbnail_path", length = 500)
    private String thumbnailPath;

    /** 前端一次上传操作的会话 ID，用于请求超时后的幂等重试 */
    @Column(name = "upload_session_id", length = 100)
    private String uploadSessionId;

    /** 单文件幂等键；同一上传会话内重试同一个文件时保持不变 */
    @Column(name = "upload_key", length = 128)
    private String uploadKey;
    
    // 构造函数
    public File() {}
    
    public File(String fileId, String projectId, String userId, String directoryId, 
                String originalName, String storedName, String filePath, Long fileSize, 
                String mimeType, String fileExtension) {
        this.fileId = fileId;
        this.projectId = projectId;
        this.userId = userId;
        this.directoryId = directoryId;
        this.originalName = originalName;
        this.storedName = storedName;
        this.filePath = filePath;
        this.fileSize = fileSize;
        this.mimeType = mimeType;
        this.fileExtension = fileExtension;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }
    
    // Getters and Setters

    public String getFileId() {
        return fileId;
    }
    
    public void setFileId(String fileId) {
        this.fileId = fileId;
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
    
    public String getDirectoryId() {
        return directoryId;
    }
    
    public void setDirectoryId(String directoryId) {
        this.directoryId = directoryId;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getOriginalName() {
        return originalName;
    }
    
    public void setOriginalName(String originalName) {
        this.originalName = originalName;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getStoredName() {
        return storedName;
    }
    
    public void setStoredName(String storedName) {
        this.storedName = storedName;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getFilePath() {
        return filePath;
    }
    
    public void setFilePath(String filePath) {
        this.filePath = filePath;
        this.updatedAt = LocalDateTime.now();
    }
    
    public Long getFileSize() {
        return fileSize;
    }
    
    public void setFileSize(Long fileSize) {
        this.fileSize = fileSize;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getMimeType() {
        return mimeType;
    }
    
    public void setMimeType(String mimeType) {
        this.mimeType = mimeType;
        this.updatedAt = LocalDateTime.now();
    }
    
    public String getFileExtension() {
        return fileExtension;
    }
    
    public void setFileExtension(String fileExtension) {
        this.fileExtension = fileExtension;
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

    public String getThumbnailPath() {
        return thumbnailPath;
    }

    public void setThumbnailPath(String thumbnailPath) {
        this.thumbnailPath = thumbnailPath;
    }

    public String getUploadSessionId() {
        return uploadSessionId;
    }

    public void setUploadSessionId(String uploadSessionId) {
        this.uploadSessionId = uploadSessionId;
    }

    public String getUploadKey() {
        return uploadKey;
    }

    public void setUploadKey(String uploadKey) {
        this.uploadKey = uploadKey;
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
        return "File{" +
                "fileId='" + fileId + '\'' +
                ", projectId='" + projectId + '\'' +
                ", userId='" + userId + '\'' +
                ", directoryId='" + directoryId + '\'' +
                ", originalName='" + originalName + '\'' +
                ", storedName='" + storedName + '\'' +
                ", filePath='" + filePath + '\'' +
                ", fileSize=" + fileSize +
                ", mimeType='" + mimeType + '\'' +
                ", fileExtension='" + fileExtension + '\'' +
                ", thumbnailPath='" + thumbnailPath + '\'' +
                ", uploadSessionId='" + uploadSessionId + '\'' +
                ", uploadKey='" + uploadKey + '\'' +
                ", createdAt=" + createdAt +
                ", updatedAt=" + updatedAt +
                '}';
    }
}
