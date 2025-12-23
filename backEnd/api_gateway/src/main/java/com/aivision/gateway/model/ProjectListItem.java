package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "项目列表项")
public class ProjectListItem {
    
    @JsonProperty("Id")
    @Schema(description = "项目ID", example = "1")
    private String id;
    
    @JsonProperty("Name")
    @Schema(description = "项目名称", example = "检测项目1")
    private String name;
    
    @JsonProperty("Description")
    @Schema(description = "项目描述", example = "PCB板自动化检测项目，用于电路板缺陷识别")
    private String description;
    
    @JsonProperty("CreateTime")
    @Schema(description = "创建时间", example = "2023-10-01 14:30:22")
    private String createTime;
    
    @JsonProperty("UpdateTime") 
    @Schema(description = "更新时间", example = "2023-10-15 09:15:18")
    private String updateTime;
    
    @JsonProperty("FileCount")
    @Schema(description = "文件数量", example = "24")
    private Integer fileCount;
    
    @JsonProperty("TaskCount")
    @Schema(description = "任务数量", example = "3")
    private Integer taskCount;
    
    @JsonProperty("Permission")
    @Schema(description = "用户对该项目的权限 (OWNER, READ_ONLY, READ_WRITE)", example = "READ_ONLY")
    private String permission;
    
    // 构造函数
    public ProjectListItem() {}
    
    public ProjectListItem(String id, String name, String description, String createTime, String updateTime, Integer fileCount, Integer taskCount, String permission) {
        this.id = id;
        this.name = name;
        this.description = description;
        this.createTime = createTime;
        this.updateTime = updateTime;
        this.fileCount = fileCount;
        this.taskCount = taskCount;
        this.permission = permission;
    }
    
    // Getters and Setters
    public String getId() {
        return id;
    }
    
    public void setId(String id) {
        this.id = id;
    }
    
    public String getName() {
        return name;
    }
    
    public void setName(String name) {
        this.name = name;
    }
    
    public String getDescription() {
        return description;
    }
    
    public void setDescription(String description) {
        this.description = description;
    }
    
    public String getCreateTime() {
        return createTime;
    }
    
    public void setCreateTime(String createTime) {
        this.createTime = createTime;
    }
    
    public String getUpdateTime() {
        return updateTime;
    }
    
    public void setUpdateTime(String updateTime) {
        this.updateTime = updateTime;
    }
    
    public Integer getFileCount() {
        return fileCount;
    }
    
    public void setFileCount(Integer fileCount) {
        this.fileCount = fileCount;
    }
    
    public Integer getTaskCount() {
        return taskCount;
    }
    
    public void setTaskCount(Integer taskCount) {
        this.taskCount = taskCount;
    }

    public String getPermission() {
        return permission;
    }

    public void setPermission(String permission) {
        this.permission = permission;
    }
    
    @Override
    public String toString() {
        return "ProjectListItem{" +
                "id='" + id + '\'' +
                ", name='" + name + '\'' +
                ", description='" + description + '\'' +
                ", createTime='" + createTime + '\'' +
                ", updateTime='" + updateTime + '\'' +
                ", fileCount=" + fileCount +
                ", taskCount=" + taskCount +
                '}';
    }
} 