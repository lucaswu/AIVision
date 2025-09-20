package com.aivision.gateway.model;

import io.swagger.v3.oas.annotations.media.Schema;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;

/**
 * 任务更新请求
 * 
 * @author AIVision Team
 */
@Schema(description = "任务更新请求")
public class TaskUpdateRequest {
    
    @Schema(description = "任务名称", example = "PCB缺陷检测任务")
    @NotBlank(message = "任务名称不能为空")
    @Size(max = 100, message = "任务名称长度不能超过100个字符")
    private String Name;
    
    @Schema(description = "任务描述", example = "检测PCB板上的缺陷")
    @Size(max = 500, message = "任务描述长度不能超过500个字符")
    private String Description;
    
    @Schema(description = "算法类型", example = "object-detection", 
            allowableValues = {"object-detection", "defect-detection", "classification", "segmentation"})
    @NotBlank(message = "算法类型不能为空")
    private String AlgorithmType;

    // 构造函数
    public TaskUpdateRequest() {}

    public TaskUpdateRequest(String name, String description, String algorithmType) {
        this.Name = name;
        this.Description = description;
        this.AlgorithmType = algorithmType;
    }

    // Getter 和 Setter
    public String getName() {
        return Name;
    }

    public void setName(String name) {
        this.Name = name;
    }

    public String getDescription() {
        return Description;
    }

    public void setDescription(String description) {
        this.Description = description;
    }

    public String getAlgorithmType() {
        return AlgorithmType;
    }

    public void setAlgorithmType(String algorithmType) {
        this.AlgorithmType = algorithmType;
    }

    @Override
    public String toString() {
        return "TaskUpdateRequest{" +
                "Name='" + Name + '\'' +
                ", Description='" + Description + '\'' +
                ", AlgorithmType='" + AlgorithmType + '\'' +
                '}';
    }
}

