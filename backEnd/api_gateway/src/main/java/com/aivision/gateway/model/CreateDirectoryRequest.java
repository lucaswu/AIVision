package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;

public class CreateDirectoryRequest {
    
    @JsonProperty("Name")
    @NotBlank(message = "目录名称不能为空")
    @Size(max = 255, message = "目录名称长度不能超过255个字符")
    private String Name;
    
    @JsonProperty("ParentDirectoryId")
    @Size(max = 255, message = "父目录ID长度不能超过255个字符")
    private String ParentDirectoryId;
    
    // 构造函数
    public CreateDirectoryRequest() {}
    
    public CreateDirectoryRequest(String name, String parentDirectoryId) {
        this.Name = name;
        this.ParentDirectoryId = parentDirectoryId;
    }
    
    // Getters and Setters
    public String getName() {
        return Name;
    }
    
    public void setName(String name) {
        this.Name = name;
    }
    
    public String getParentDirectoryId() {
        return ParentDirectoryId;
    }
    
    public void setParentDirectoryId(String parentDirectoryId) {
        this.ParentDirectoryId = parentDirectoryId;
    }
    
    @Override
    public String toString() {
        return "CreateDirectoryRequest{" +
                "Name='" + Name + '\'' +
                ", ParentDirectoryId='" + ParentDirectoryId + '\'' +
                '}';
    }
} 