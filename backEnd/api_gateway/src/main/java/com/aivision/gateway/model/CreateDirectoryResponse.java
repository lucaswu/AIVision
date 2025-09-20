package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public class CreateDirectoryResponse {
    
    @JsonProperty("DirId")
    private String dirId;
    
    @JsonProperty("DirPath")
    private String dirPath;
    
    // 构造函数
    public CreateDirectoryResponse() {}
    
    public CreateDirectoryResponse(String dirId, String dirPath) {
        this.dirId = dirId;
        this.dirPath = dirPath;
    }
    
    // Getters and Setters
    public String getDirId() {
        return dirId;
    }
    
    public void setDirId(String dirId) {
        this.dirId = dirId;
    }
    
    public String getDirPath() {
        return dirPath;
    }
    
    public void setDirPath(String dirPath) {
        this.dirPath = dirPath;
    }
    
    @Override
    public String toString() {
        return "CreateDirectoryResponse{" +
                "dirId='" + dirId + '\'' +
                ", dirPath='" + dirPath + '\'' +
                '}';
    }
} 