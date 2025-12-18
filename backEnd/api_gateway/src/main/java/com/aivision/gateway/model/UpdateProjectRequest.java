package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;
import javax.validation.constraints.Size;

@Schema(description = "更新项目请求")
public class UpdateProjectRequest {

    @JsonProperty("ProjectName")
    @Schema(description = "项目名称", example = "我的AI检测项目(新)")
    @Size(min = 1, max = 100, message = "项目名称长度必须在1-100之间")
    private String projectName;

    @JsonProperty("Description")
    @Schema(description = "项目描述", example = "更新后的项目描述")
    private String description;

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
}

