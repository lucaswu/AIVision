package com.aivision.gateway.model;

/**
 * 文件图片数据
 * 用于封装图片的二进制数据和内容类型
 */
public class FileImageData {
    
    private byte[] imageBytes;
    private String contentType;
    private String fileName;
    private long fileSize;
    
    public FileImageData() {}
    
    public FileImageData(byte[] imageBytes, String contentType, String fileName, long fileSize) {
        this.imageBytes = imageBytes;
        this.contentType = contentType;
        this.fileName = fileName;
        this.fileSize = fileSize;
    }
    
    public byte[] getImageBytes() {
        return imageBytes;
    }
    
    public void setImageBytes(byte[] imageBytes) {
        this.imageBytes = imageBytes;
    }
    
    public String getContentType() {
        return contentType;
    }
    
    public void setContentType(String contentType) {
        this.contentType = contentType;
    }
    
    public String getFileName() {
        return fileName;
    }
    
    public void setFileName(String fileName) {
        this.fileName = fileName;
    }
    
    public long getFileSize() {
        return fileSize;
    }
    
    public void setFileSize(long fileSize) {
        this.fileSize = fileSize;
    }
} 