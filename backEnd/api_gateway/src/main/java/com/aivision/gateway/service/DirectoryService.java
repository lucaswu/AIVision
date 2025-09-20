package com.aivision.gateway.service;

import com.aivision.gateway.model.Directory;
import com.aivision.gateway.model.Project;
import com.aivision.gateway.repository.DirectoryRepository;
import com.aivision.gateway.repository.ProjectRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;
import java.util.UUID;

@Service
@Transactional
public class DirectoryService {
    
    @Autowired
    private DirectoryRepository directoryRepository;
    
    @Autowired
    private ProjectRepository projectRepository;
    
    /**
     * 创建目录
     */
    public String createDirectory(String projectId, String userId, String dirName, String parentId) {
        // 1. 验证项目是否存在并且属于当前用户
        Optional<Project> project = projectRepository.findById(projectId);
        if (!project.isPresent()) {
            throw new IllegalArgumentException("项目不存在");
        }
        
        // 2. 验证项目是否属于当前用户
        if (!project.get().getOwnerId().equals(userId)) {
            throw new IllegalArgumentException("无权限访问该项目");
        }
        
        // 3. 验证目录名称
        if (dirName == null || dirName.trim().isEmpty()) {
            throw new IllegalArgumentException("目录名称不能为空");
        }
        
        // 4. 处理父目录逻辑
        String finalParentId = null;
        String dirPath = "";
        int dirLevel = 1;
        
        if (parentId != null && !parentId.trim().isEmpty()) {
            // 验证父目录是否存在
            Optional<Directory> parentDir = directoryRepository.findByDirIdAndProjectIdAndUserIdAndStatus(
                parentId, projectId, userId, Directory.Status.ACTIVE);
            if (!parentDir.isPresent()) {
                throw new IllegalArgumentException("父目录不存在");
            }
            
            finalParentId = parentId;
            dirLevel = parentDir.get().getDirLevel() + 1;
            
            // 检查嵌套层级限制
            if (dirLevel > 5) {
                throw new IllegalArgumentException("目录嵌套层级不能超过5层");
            }
            
            dirPath = parentDir.get().getDirPath() + "/" + dirName;
        } else {
            // 根目录
            dirPath = "/" + dirName;
        }
        
        // 5. 检查同级目录名称是否重复
        Optional<Directory> existingDir = directoryRepository.findByProjectIdAndUserIdAndParentIdAndDirNameAndStatus(
            projectId, userId, finalParentId, dirName, Directory.Status.ACTIVE);
        if (existingDir.isPresent()) {
            throw new RuntimeException("同级目录下已存在相同名称的目录");
        }
        
        // 6. 创建新目录
        String dirId = UUID.randomUUID().toString();
        Directory directory = new Directory(dirId, projectId, userId, finalParentId, dirName, dirPath, dirLevel);
        
        // 7. 保存到数据库
        directoryRepository.save(directory);
        
        return dirId;
    }
    
    /**
     * 根据目录ID获取目录信息
     */
    public Directory getDirectoryById(String dirId, String projectId, String userId) {
        Optional<Directory> directory = directoryRepository.findByDirIdAndProjectIdAndUserIdAndStatus(
            dirId, projectId, userId, Directory.Status.ACTIVE);
        if (!directory.isPresent()) {
            throw new IllegalArgumentException("目录不存在");
        }
        return directory.get();
    }
} 