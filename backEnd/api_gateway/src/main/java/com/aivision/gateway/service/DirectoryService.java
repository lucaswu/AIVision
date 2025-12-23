package com.aivision.gateway.service;

import com.aivision.gateway.model.Directory;
import com.aivision.gateway.model.Project;
import com.aivision.gateway.model.User;
import com.aivision.gateway.model.UserProjectPermission;
import com.aivision.gateway.repository.DirectoryRepository;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Service
@Transactional
public class DirectoryService {
    
    @Autowired
    private DirectoryRepository directoryRepository;
    
    @Autowired
    private ProjectRepository projectRepository;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private UserProjectPermissionRepository permissionRepository;
    
    /**
     * 创建目录
     */
    public String createDirectory(String projectId, String userId, String dirName, String parentId) {
        // 1. 验证项目是否存在
        Optional<Project> projectOpt = projectRepository.findById(projectId);
        if (!projectOpt.isPresent()) {
            throw new IllegalArgumentException("项目不存在");
        }
        
        // 2. 检查权限：只有管理员、项目所有者或有读写权限的用户可以创建目录
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));
        
        if (user.getRole() != User.Role.ADMIN && !projectOpt.get().getOwnerId().equals(userId)) {
            // 检查是否有读写权限
            Optional<UserProjectPermission> permission = permissionRepository.findByUserIdAndProjectId(userId, projectId);
            if (!permission.isPresent() || permission.get().getPermission() != UserProjectPermission.Permission.READ_WRITE) {
                throw new IllegalArgumentException("无权限在该项目中创建目录");
            }
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
            // 验证父目录是否存在（不再严格限制所属用户，只要在同一个项目即可）
            Optional<Directory> parentDir = directoryRepository.findByDirIdAndProjectIdAndStatus(
                parentId, projectId, Directory.Status.ACTIVE);
            if (!parentDir.isPresent()) {
                throw new IllegalArgumentException("父目录不存在");
            }
            
            finalParentId = parentId;
            dirLevel = parentDir.get().getDirLevel() + 1;
            
            // 检查嵌套层级限制
            if (dirLevel > 10) { // 放宽到10层
                throw new IllegalArgumentException("目录嵌套层级不能超过10层");
            }
            
            dirPath = parentDir.get().getDirPath() + "/" + dirName;
        } else {
            // 根目录
            dirPath = "/" + dirName;
        }
        
        // 5. 检查同级目录名称是否重复
        Optional<Directory> existingDir = directoryRepository.findByProjectIdAndParentIdAndDirNameAndStatus(
            projectId, finalParentId, dirName, Directory.Status.ACTIVE);
        if (existingDir.isPresent()) {
            // 如果已存在，直接返回已存在的 ID 而不是抛错，这有利于前端的递归创建逻辑
            return existingDir.get().getDirId();
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
        Optional<Directory> directory = directoryRepository.findByDirIdAndProjectIdAndStatus(
            dirId, projectId, Directory.Status.ACTIVE);
        if (!directory.isPresent()) {
            throw new IllegalArgumentException("目录不存在");
        }
        return directory.get();
    }

    /**
     * 删除目录
     * @param dirId 目录ID
     * @param projectId 项目ID
     * @param userId 用户ID
     */
    public void deleteDirectory(String dirId, String projectId, String userId) {
        // 1. 获取项目信息
        Optional<Project> projectOpt = projectRepository.findById(projectId);
        if (!projectOpt.isPresent()) {
            throw new IllegalArgumentException("项目不存在");
        }

        // 2. 检查权限
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));
        
        if (user.getRole() != User.Role.ADMIN && !projectOpt.get().getOwnerId().equals(userId)) {
            // 检查是否有读写权限
            Optional<UserProjectPermission> permission = permissionRepository.findByUserIdAndProjectId(userId, projectId);
            if (!permission.isPresent() || permission.get().getPermission() != UserProjectPermission.Permission.READ_WRITE) {
                throw new IllegalArgumentException("无权限在该项目中删除目录");
            }
        }

        // 3. 获取目录
        Directory directory = getDirectoryById(dirId, projectId, userId);
        
        // 4. 检查是否有子目录（ACTIVE状态，放宽到整个项目范围）
        List<Directory> subDirs = directoryRepository.findByParentIdAndStatusOrderByDirNameAsc(
            dirId, Directory.Status.ACTIVE);
        if (!subDirs.isEmpty()) {
            throw new RuntimeException("无法删除：目录不为空（包含子目录）");
        }
        
        // 5. 标记为删除（软删除）
        directory.setStatus(Directory.Status.DELETED);
        directoryRepository.save(directory);
    }
} 