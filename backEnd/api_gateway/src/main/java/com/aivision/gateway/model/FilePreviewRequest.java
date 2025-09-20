package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 文件预览请求
 */
@Schema(description = "文件预览请求")
public class FilePreviewRequest {
    
    @JsonProperty("FileId")
    @Schema(description = "文件ID", example = "4852273e-b64a-44a7-b676-94b533c3ac23", required = true)
    private String fileId;
    
    @JsonProperty("ProjectId")
    @Schema(description = "项目ID", example = "c6f4c9b9-a12e-4b11-9792-24993a69497a", required = true)
    private String projectId;
    
    @JsonProperty("UserId")
    @Schema(description = "用户ID", example = "user001", required = true)
    private String userId;
    
    public FilePreviewRequest() {}
    
    public FilePreviewRequest(String fileId, String projectId, String userId) {
        this.fileId = fileId;
        this.projectId = projectId;
        this.userId = userId;
    }
    
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
    }
    
    public String getUserId() {
        return userId;
    }
    
    public void setUserId(String userId) {
        this.userId = userId;
    }
} 