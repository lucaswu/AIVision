package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public class ProjectFileTreeResponse {
    
    public static class TreeNode {
        @JsonProperty("Id")
        private String id;
        
        @JsonProperty("Name")
        private String name;
        
        @JsonProperty("Type")
        private String type; // "directory" or "file"
        
        @JsonProperty("ProjectId")
        private String projectId;
        
        @JsonProperty("UserId")
        private String userId;
        
        // 文件特有字段
        @JsonProperty("FileType")
        private String fileType;
        
        @JsonProperty("Size")
        private String size;
        
        @JsonProperty("UploadDate")
        private String uploadDate;
        
        // 目录特有字段 - 子节点
        @JsonProperty("Children")
        private List<TreeNode> children;
        
        // 构造函数
        public TreeNode() {}
        
        // 目录构造函数
        public TreeNode(String id, String name, String projectId, String userId, List<TreeNode> children) {
            this.id = id;
            this.name = name;
            this.type = "directory";
            this.projectId = projectId;
            this.userId = userId;
            this.children = children;
        }
        
        // 文件构造函数
        public TreeNode(String id, String name, String projectId, String userId, String fileType, String size, String uploadDate) {
            this.id = id;
            this.name = name;
            this.type = "file";
            this.projectId = projectId;
            this.userId = userId;
            this.fileType = fileType;
            this.size = size;
            this.uploadDate = uploadDate;
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
        
        public String getType() {
            return type;
        }
        
        public void setType(String type) {
            this.type = type;
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
        
        public String getFileType() {
            return fileType;
        }
        
        public void setFileType(String fileType) {
            this.fileType = fileType;
        }
        
        public String getSize() {
            return size;
        }
        
        public void setSize(String size) {
            this.size = size;
        }
        
        public String getUploadDate() {
            return uploadDate;
        }
        
        public void setUploadDate(String uploadDate) {
            this.uploadDate = uploadDate;
        }
        
        public List<TreeNode> getChildren() {
            return children;
        }
        
        public void setChildren(List<TreeNode> children) {
            this.children = children;
        }
    }
} 