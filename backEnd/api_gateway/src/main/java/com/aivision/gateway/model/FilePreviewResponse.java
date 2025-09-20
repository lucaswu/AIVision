package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 文件预览响应
 */
@Schema(description = "文件预览响应")
public class FilePreviewResponse {
    
    @JsonProperty("FileId")
    @Schema(description = "文件ID", example = "4852273e-b64a-44a7-b676-94b533c3ac23")
    private String fileId;
    
    @JsonProperty("FileName")
    @Schema(description = "文件名", example = "001.jpg")
    private String fileName;
    
    @JsonProperty("FileSize")
    @Schema(description = "文件大小（字节）", example = "1024000")
    private Long fileSize;
    
    @JsonProperty("ContentType")
    @Schema(description = "文件MIME类型", example = "image/jpeg")
    private String contentType;
    
    @JsonProperty("ImageData")
    @Schema(description = "Base64编码的图片数据", example = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD...")
    private String imageData;
    
    @JsonProperty("Width")
    @Schema(description = "图片宽度（像素）", example = "1920")
    private Integer width;
    
    @JsonProperty("Height")
    @Schema(description = "图片高度（像素）", example = "1080")
    private Integer height;
    
    public FilePreviewResponse() {}
    
    public FilePreviewResponse(String fileId, String fileName, Long fileSize, 
                              String contentType, String imageData, Integer width, Integer height) {
        this.fileId = fileId;
        this.fileName = fileName;
        this.fileSize = fileSize;
        this.contentType = contentType;
        this.imageData = imageData;
        this.width = width;
        this.height = height;
    }
    
    // Getters and Setters
    public String getFileId() { return fileId; }
    public void setFileId(String fileId) { this.fileId = fileId; }
    
    public String getFileName() { return fileName; }
    public void setFileName(String fileName) { this.fileName = fileName; }
    
    public Long getFileSize() { return fileSize; }
    public void setFileSize(Long fileSize) { this.fileSize = fileSize; }
    
    public String getContentType() { return contentType; }
    public void setContentType(String contentType) { this.contentType = contentType; }
    
    public String getImageData() { return imageData; }
    public void setImageData(String imageData) { this.imageData = imageData; }
    
    public Integer getWidth() { return width; }
    public void setWidth(Integer width) { this.width = width; }
    
    public Integer getHeight() { return height; }
    public void setHeight(Integer height) { this.height = height; }
} 