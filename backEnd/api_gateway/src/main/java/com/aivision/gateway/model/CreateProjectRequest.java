package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;

@Schema(description = "创建项目请求")
public class CreateProjectRequest {
    
    @JsonProperty("ProjectName")
    @NotBlank(message = "项目名称不能为空")
    @Size(max = 100, message = "项目名称长度不能超过100个字符")
    @Schema(description = "项目名称", example = "我的AI检测项目", required = true)
    private String projectName;
    
    @JsonProperty("Description")
    @Size(max = 500, message = "项目描述长度不能超过500个字符")
    @Schema(description = "项目描述", example = "PCB板自动化检测项目，用于电路板缺陷识别")
    private String description;
    
    // 构造函数
    public CreateProjectRequest() {}
    
    public CreateProjectRequest(String projectName, String description) {
        this.projectName = projectName;
        this.description = description;
    }
    
    // Getters and Setters
    public String getProjectName() {
        return projectName;
    }
    
    public void setProjectName(String projectName) {
        this.projectName = projectName;
    }
    
    public String getDescription() {
        return description;
    }
    
    public void setDescription(String description) {
        this.description = description;
    }
    
    @Override
    public String toString() {
        return "CreateProjectRequest{" +
                "projectName='" + projectName + '\'' +
                ", description='" + description + '\'' +
                '}';
    }
} 