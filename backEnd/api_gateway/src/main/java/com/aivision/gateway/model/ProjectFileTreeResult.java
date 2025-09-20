package com.aivision.gateway.model;

import java.util.List;

public class ProjectFileTreeResult {
    private List<ProjectFileTreeResponse.TreeNode> fileTree;
    private int totalFileCount;
    
    public ProjectFileTreeResult() {}
    
    public ProjectFileTreeResult(List<ProjectFileTreeResponse.TreeNode> fileTree, int totalFileCount) {
        this.fileTree = fileTree;
        this.totalFileCount = totalFileCount;
    }
    
    public List<ProjectFileTreeResponse.TreeNode> getFileTree() {
        return fileTree;
    }
    
    public void setFileTree(List<ProjectFileTreeResponse.TreeNode> fileTree) {
        this.fileTree = fileTree;
    }
    
    public int getTotalFileCount() {
        return totalFileCount;
    }
    
    public void setTotalFileCount(int totalFileCount) {
        this.totalFileCount = totalFileCount;
    }
} 