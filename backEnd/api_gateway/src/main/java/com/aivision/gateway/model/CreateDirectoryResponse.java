package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public class CreateDirectoryResponse {

    @JsonProperty("DirId")
    private String dirId;

    @JsonProperty("DirPath")
    private String dirPath;

    @JsonProperty("SortOrder")
    private Integer sortOrder;

    // 构造函数
    public CreateDirectoryResponse() {}

    public CreateDirectoryResponse(String dirId, String dirPath) {
        this.dirId = dirId;
        this.dirPath = dirPath;
    }

    public CreateDirectoryResponse(String dirId, String dirPath, Integer sortOrder) {
        this.dirId = dirId;
        this.dirPath = dirPath;
        this.sortOrder = sortOrder;
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

    public Integer getSortOrder() {
        return sortOrder;
    }

    public void setSortOrder(Integer sortOrder) {
        this.sortOrder = sortOrder;
    }

    @Override
    public String toString() {
        return "CreateDirectoryResponse{" +
                "dirId='" + dirId + '\'' +
                ", dirPath='" + dirPath + '\'' +
                ", sortOrder=" + sortOrder +
                '}';
    }
}
