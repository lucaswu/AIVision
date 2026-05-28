package com.aivision.gateway.service;

import com.aivision.gateway.model.Directory;
import com.aivision.gateway.model.File;
import com.aivision.gateway.model.Project;
import com.aivision.gateway.model.User;
import com.aivision.gateway.model.UserProjectPermission;
import com.aivision.gateway.repository.DirectoryRepository;
import com.aivision.gateway.repository.FileRepository;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import com.aivision.gateway.service.storage.StorageStrategy;
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

    @Autowired
    private FileRepository fileRepository;

    @Autowired
    private StorageStrategy storageStrategy;

    private static final int DEFAULT_SORT_ORDER = 99;

    /**
     * 创建目录
     */
    public String createDirectory(String projectId, String userId, String dirName, String parentId) {
        return createDirectory(projectId, userId, dirName, parentId, DEFAULT_SORT_ORDER);
    }

    /**
     * 创建目录
     */
    public String createDirectory(String projectId, String userId, String dirName, String parentId, Integer sortOrder) {
        validateWritePermission(projectId, userId, "创建目录");
        String normalizedName = normalizeDirectoryName(dirName);
        int normalizedSortOrder = normalizeSortOrder(sortOrder);

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

            dirPath = parentDir.get().getDirPath() + "/" + normalizedName;
        } else {
            // 根目录
            dirPath = "/" + normalizedName;
        }

        // 5. 检查同级目录名称是否重复
        Optional<Directory> existingDir = directoryRepository.findByProjectIdAndParentIdAndDirNameAndStatus(
            projectId, finalParentId, normalizedName, Directory.Status.ACTIVE);
        if (existingDir.isPresent()) {
            // 如果已存在，直接返回已存在的 ID 而不是抛错，这有利于前端的递归创建逻辑
            return existingDir.get().getDirId();
        }

        // unique_dir_name_per_parent 约束不包含 status，软删除的同名目录行仍占用唯一槽位，
        // 直接插入新行会违反约束。这里先物理清除这些残留行（其子目录/文件由外键级联删除），再插入。
        directoryRepository.deleteByProjectIdAndParentIdAndDirNameAndStatus(
            projectId, finalParentId, normalizedName, Directory.Status.DELETED);

        // 6. 创建新目录
        String dirId = UUID.randomUUID().toString();
        Directory directory = new Directory(dirId, projectId, userId, finalParentId, normalizedName, dirPath, dirLevel, normalizedSortOrder);

        // 7. 保存到数据库
        directoryRepository.save(directory);

        return dirId;
    }

    private Project validateWritePermission(String projectId, String userId, String actionName) {
        // 1. 验证项目是否存在
        Optional<Project> projectOpt = projectRepository.findById(projectId);
        if (!projectOpt.isPresent()) {
            throw new IllegalArgumentException("项目不存在");
        }

        // 2. 检查权限：只有管理员、项目所有者或有读写权限的用户可以操作目录
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));

        if (user.getRole() != User.Role.ADMIN && !projectOpt.get().getOwnerId().equals(userId)) {
            Optional<UserProjectPermission> permission = permissionRepository.findByUserIdAndProjectId(userId, projectId);
            if (!permission.isPresent() || permission.get().getPermission() != UserProjectPermission.Permission.READ_WRITE) {
                throw new IllegalArgumentException("无权限在该项目中" + actionName);
            }
        }

        return projectOpt.get();
    }

    private String normalizeDirectoryName(String dirName) {
        if (dirName == null || dirName.trim().isEmpty()) {
            throw new IllegalArgumentException("目录名称不能为空");
        }

        String normalizedName = dirName.trim();
        if (normalizedName.contains("/")) {
            throw new IllegalArgumentException("目录名称不能包含 /");
        }

        return normalizedName;
    }

    private int normalizeSortOrder(Integer sortOrder) {
        if (sortOrder == null) {
            return DEFAULT_SORT_ORDER;
        }
        if (sortOrder < 0) {
            throw new IllegalArgumentException("排序号不能小于0");
        }
        return sortOrder;
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
     * 更新目录名称和排序号
     */
    public void updateDirectory(String dirId, String projectId, String userId, String dirName, Integer sortOrder) {
        validateWritePermission(projectId, userId, "修改目录");
        Directory directory = getDirectoryById(dirId, projectId, userId);
        boolean updated = false;

        if (dirName != null) {
            String normalizedName = normalizeDirectoryName(dirName);
            if (!normalizedName.equals(directory.getDirName())) {
                Optional<Directory> existingDir = directoryRepository.findByProjectIdAndParentIdAndDirNameAndStatus(
                    projectId, directory.getParentId(), normalizedName, Directory.Status.ACTIVE);
                if (existingDir.isPresent() && !existingDir.get().getDirId().equals(dirId)) {
                    throw new RuntimeException("同级目录名称已存在");
                }

                String oldPath = directory.getDirPath();
                String newPath = buildDirectoryPath(directory.getParentId(), projectId, normalizedName);
                directory.setDirName(normalizedName);
                directory.setDirPath(newPath);
                updateChildDirectoryPaths(projectId, oldPath, newPath);
                updated = true;
            }
        }

        if (sortOrder != null) {
            int normalizedSortOrder = normalizeSortOrder(sortOrder);
            if (!Integer.valueOf(normalizedSortOrder).equals(directory.getSortOrder())) {
                directory.setSortOrder(normalizedSortOrder);
                updated = true;
            }
        }

        if (updated) {
            directoryRepository.save(directory);
        }
    }

    private String buildDirectoryPath(String parentId, String projectId, String dirName) {
        if (parentId == null || parentId.trim().isEmpty()) {
            return "/" + dirName;
        }

        Directory parentDirectory = directoryRepository.findByDirIdAndProjectIdAndStatus(
                parentId, projectId, Directory.Status.ACTIVE)
            .orElseThrow(() -> new IllegalArgumentException("父目录不存在"));
        return parentDirectory.getDirPath() + "/" + dirName;
    }

    private void updateChildDirectoryPaths(String projectId, String oldPath, String newPath) {
        List<Directory> childDirectories = directoryRepository.findByProjectIdAndStatusAndDirPathStartingWith(
            projectId, Directory.Status.ACTIVE, oldPath + "/");
        for (Directory childDirectory : childDirectories) {
            String suffix = childDirectory.getDirPath().substring(oldPath.length());
            childDirectory.setDirPath(newPath + suffix);
        }
        if (!childDirectories.isEmpty()) {
            directoryRepository.saveAll(childDirectories);
        }
    }

    /**
     * 删除目录
     * @param dirId 目录ID
     * @param projectId 项目ID
     * @param userId 用户ID
     */
    public void deleteDirectory(String dirId, String projectId, String userId) {
        validateWritePermission(projectId, userId, "删除目录");
        Directory directory = getDirectoryById(dirId, projectId, userId);

        List<Directory> directoriesToDelete = new java.util.ArrayList<>();
        collectDirectorySubtree(projectId, directory, directoriesToDelete);

        for (Directory dir : directoriesToDelete) {
            List<File> files = fileRepository.findByDirectoryId(dir.getDirId());
            for (File file : files) {
                deleteStoredObjectQuietly(file.getFilePath());
                deleteStoredObjectQuietly(file.getThumbnailPath());
            }
            fileRepository.deleteAll(files);
        }

        for (Directory dir : directoriesToDelete) {
            dir.setStatus(Directory.Status.DELETED);
        }
        directoryRepository.saveAll(directoriesToDelete);
    }

    private void collectDirectorySubtree(String projectId, Directory directory, List<Directory> result) {
        result.add(directory);
        List<Directory> subDirectories = directoryRepository.findByProjectIdAndParentIdAndStatus(
            projectId, directory.getDirId(), Directory.Status.ACTIVE);
        for (Directory subDirectory : subDirectories) {
            collectDirectorySubtree(projectId, subDirectory, result);
        }
    }

    private void deleteStoredObjectQuietly(String objectPath) {
        if (objectPath == null || objectPath.trim().isEmpty()) {
            return;
        }

        try {
            storageStrategy.delete(objectPath);
        } catch (Exception ignored) {
            // 存储清理失败不阻塞数据库清理，保持与单文件删除的容错策略一致。
        }
    }
}
