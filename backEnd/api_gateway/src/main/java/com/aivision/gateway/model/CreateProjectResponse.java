package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "创建项目响应")
public class CreateProjectResponse {
    
    @JsonProperty("ProjectId")
    @Schema(description = "项目ID", example = "550e8400-e29b-41d4-a716-446655440000")
    private String projectId;
    
    // 构造函数
    public CreateProjectResponse() {}
    
    public CreateProjectResponse(String projectId) {
        this.projectId = projectId;
    }
    
    // Getters and Setters
    public String getProjectId() {
        return projectId;
    }
    
    public void setProjectId(String projectId) {
        this.projectId = projectId;
    }
    
    @Override
    public String toString() {
        return "CreateProjectResponse{" +
                "projectId='" + projectId + '\'' +
                '}';
    }
} 