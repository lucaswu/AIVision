package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import javax.validation.constraints.NotBlank;
import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;
import java.util.List;

public class TaskSubmitRequest {
    
    @JsonProperty("Name")
    @NotBlank(message = "任务名称不能为空")
    private String name;
    
    @JsonProperty("Description")
    private String description;
    
    @JsonProperty("AlgorithmType")
    @NotBlank(message = "算法类型不能为空")
    private String algorithmType;
    
    @JsonProperty("SelectedFiles")
    private List<SelectedFile> selectedFiles;

    @JsonProperty("DirectoryIds")
    private List<String> directoryIds;
    
    // 内部类：选择的文件信息
    public static class SelectedFile {
        @JsonProperty("FileId")
        @NotBlank(message = "文件ID不能为空")
        private String fileId;
        
        public SelectedFile() {}
        
        public SelectedFile(String fileId) {
            this.fileId = fileId;
        }
        
        public String getFileId() {
            return fileId;
        }
        
        public void setFileId(String fileId) {
            this.fileId = fileId;
        }
        
        @Override
        public String toString() {
            return "SelectedFile{" +
                    "fileId='" + fileId + '\'' +
                    '}';
        }
    }
    
    // 构造函数
    public TaskSubmitRequest() {}
    
    // Getters and Setters
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
    
    public String getAlgorithmType() {
        return algorithmType;
    }
    
    public void setAlgorithmType(String algorithmType) {
        this.algorithmType = algorithmType;
    }
    
    public List<SelectedFile> getSelectedFiles() {
        return selectedFiles;
    }
    
    public void setSelectedFiles(List<SelectedFile> selectedFiles) {
        this.selectedFiles = selectedFiles;
    }

    public List<String> getDirectoryIds() {
        return directoryIds;
    }

    public void setDirectoryIds(List<String> directoryIds) {
        this.directoryIds = directoryIds;
    }
    
    @Override
    public String toString() {
        return "TaskSubmitRequest{" +
                "name='" + name + '\'' +
                ", description='" + description + '\'' +
                ", algorithmType='" + algorithmType + '\'' +
                ", selectedFiles=" + selectedFiles +
                '}';
    }
} 