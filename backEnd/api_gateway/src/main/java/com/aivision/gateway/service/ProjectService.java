package com.aivision.gateway.service;

import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.DirectoryRepository;
import com.aivision.gateway.repository.FileRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import com.aivision.gateway.repository.TaskRepository;
import com.aivision.gateway.repository.TaskFileRepository;
import com.aivision.gateway.repository.ReportRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Service
@Transactional
public class ProjectService {
    
    @Autowired
    private ProjectRepository projectRepository;
    
    @Autowired
    private DirectoryRepository directoryRepository;
    
    @Autowired
    private FileRepository fileRepository;

    @Autowired
    private UserProjectPermissionRepository permissionRepository;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private TaskRepository taskRepository;

    @Autowired
    private TaskFileRepository taskFileRepository;

    @Autowired
    private ReportRepository reportRepository;
    
    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    
    /**
     * 创建项目 (新版本，支持描述)
     * @param ownerId 项目所有者ID
     * @param projectName 项目名称
     * @param description 项目描述
     * @return 创建的项目ID
     */
    public String createProject(String ownerId, String projectName, String description) {
        // 验证输入参数
        if (ownerId == null || ownerId.trim().isEmpty()) {
            throw new IllegalArgumentException("用户ID不能为空");
        }

        // 验证权限：只有管理员才能创建项目
        User user = userRepository.findById(ownerId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));
        if (user.getRole() != User.Role.ADMIN) {
            throw new RuntimeException("只有管理员才能创建项目");
        }

        if (projectName == null || projectName.trim().isEmpty()) {
            throw new IllegalArgumentException("项目名称不能为空");
        }
        
        // 检查项目名称是否已存在（同一个用户下）
        if (projectRepository.existsByProjectNameAndOwnerId(projectName.trim(), ownerId)) {
            throw new RuntimeException("项目名称已存在: " + projectName);
        }
        
        // 创建新项目
        Project project = new Project();
        project.setProjectId(UUID.randomUUID().toString());
        project.setProjectName(projectName.trim());
        project.setDescription(description);
        project.setOwnerId(ownerId);
        project.setStatus(Project.Status.ACTIVE);
        project.setProjectType("AI_DETECTION"); // 默认类型
        
        Project savedProject = projectRepository.save(project);
        return savedProject.getProjectId();
    }
    
    /**
     * 获取用户的项目列表 (返回格式化的DTO)
     * @param userId 用户ID
     * @return 项目列表
     */
    public List<ProjectListItem> getProjectListByUserId(String userId) {
        if (userId == null || userId.trim().isEmpty()) {
            throw new IllegalArgumentException("用户ID不能为空");
        }
        
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));

        List<Project> projects;
        if (user.getRole() == User.Role.ADMIN) {
            // 管理员可以看到所有项目
            projects = projectRepository.findAll();
            return projects.stream()
                .map(p -> convertToProjectListItem(p, userId)) // 传递 userId 以确定权限
                .collect(Collectors.toList());
        } else {
            // 非管理员（质检员）可以看到：
            // 1. 自己创建的项目 (Owner)
            // 2. 被授权的项目 (UserProjectPermission)
            Set<String> projectIds = new HashSet<>();
            
            // 获取拥有的项目ID
            projectRepository.findByOwnerId(userId).forEach(p -> projectIds.add(p.getProjectId()));
            
            // 获取被授权的项目ID
            permissionRepository.findByUserId(userId).forEach(p -> projectIds.add(p.getProjectId()));
            
            projects = projectRepository.findAllById(projectIds);
        
        return projects.stream()
                .map(p -> convertToProjectListItem(p, userId)) // 传递 userId 以确定权限
                .collect(Collectors.toList());
        }
    }
    
    /**
     * 将Project实体转换为ProjectListItem DTO
     */
    private ProjectListItem convertToProjectListItem(Project project, String userId) {
        String createTime = project.getCreatedAt() != null ? 
            project.getCreatedAt().format(DATE_TIME_FORMATTER) : "";
        String updateTime = project.getUpdatedAt() != null ? 
            project.getUpdatedAt().format(DATE_TIME_FORMATTER) : "";
            
        // 查询项目下的文件数量
        int fileCount = (int) fileRepository.countByProjectId(project.getProjectId());

        // 确定权限
        String permission = "READ_ONLY"; // 默认只读
        User user = userRepository.findById(userId).orElse(null);

        if (user != null && user.getRole() == User.Role.ADMIN) {
            permission = "OWNER"; // 管理员视为所有者权限
        } else if (project.getOwnerId().equals(userId)) {
            permission = "OWNER";
        } else {
            permission = permissionRepository.findByUserIdAndProjectId(userId, project.getProjectId())
                .map(p -> p.getPermission().name())
                .orElse("READ_ONLY");
        }
        
        return new ProjectListItem(
            project.getProjectId(),
            project.getProjectName(),
            project.getDescription(),
            createTime,
            updateTime,
            fileCount, 
            0, // taskCount
            permission
        );
    }

    /**
     * 更新项目信息
     * @param projectId 项目ID
     * @param userId 用户ID (用于权限验证)
     * @param name 新名称 (可选)
     * @param description 新描述 (可选)
     * @return 更新后的项目ID
     */
    public String updateProject(String projectId, String userId, String name, String description) {
        if (projectId == null || projectId.trim().isEmpty()) {
            throw new IllegalArgumentException("项目ID不能为空");
        }
        
        Project project = projectRepository.findById(projectId)
            .orElseThrow(() -> new RuntimeException("项目不存在"));
            
        // 验证权限
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));

        if (user.getRole() != User.Role.ADMIN && !project.getOwnerId().equals(userId)) {
            // 检查是否有 READ_WRITE 权限
            UserProjectPermission perm = permissionRepository.findByUserIdAndProjectId(userId, projectId)
                .orElseThrow(() -> new RuntimeException("无权限修改该项目"));
            
            if (perm.getPermission() != UserProjectPermission.Permission.READ_WRITE) {
                throw new RuntimeException("无权限修改该项目（仅只读权限）");
            }
        }
        
        boolean updated = false;
        
        if (name != null && !name.trim().isEmpty() && !name.equals(project.getProjectName())) {
            // 检查重名
            if (projectRepository.existsByProjectNameAndOwnerId(name.trim(), userId)) {
                throw new RuntimeException("项目名称已存在: " + name);
            }
            project.setProjectName(name.trim());
            updated = true;
        }
        
        if (description != null && !description.equals(project.getDescription())) {
            project.setDescription(description);
            updated = true;
        }
        
        if (updated) {
            projectRepository.save(project);
        }
        
        return project.getProjectId();
    }
    
    /**
     * 删除项目
     * @param projectId 项目ID
     * @param userId 用户ID (用于权限验证)
     */
    public void deleteProject(String projectId, String userId) {
        if (projectId == null || projectId.trim().isEmpty()) {
            throw new IllegalArgumentException("项目ID不能为空");
        }
        
        Project project = projectRepository.findById(projectId)
            .orElseThrow(() -> new RuntimeException("项目不存在"));
            
        // 验证权限
        if (!project.getOwnerId().equals(userId)) {
            throw new RuntimeException("无权限删除该项目");
        }
        
        // 级联删除在数据库层通过 Foreign Key CASCADE 处理
        // 但如果文件存储在 MinIO，这里需要调用 FileService 删除物理文件
        // TODO: 集成 MinIO 删除逻辑
        
        // delete related entities
        // 1. fetch all tasks for the project
        List<Task> tasks = taskRepository.findByProjectIdOrderByCreatedAtDesc(projectId);
        for (Task task : tasks) {
            taskFileRepository.deleteByTaskId(task.getTaskId());
        }

        // 2. delete reports
        reportRepository.deleteByProjectId(projectId);

        // 3. delete tasks
        taskRepository.deleteByProjectId(projectId);

        // 4. delete files
        fileRepository.deleteByProjectId(projectId);

        // 5. delete directories
        directoryRepository.deleteByProjectId(projectId);

        // 6. delete permissions
        permissionRepository.deleteByProjectId(projectId);
      
        // 7. delete project 
        projectRepository.delete(project);
    }
    
    /**
     * 创建项目 (旧版本，保持兼容性)
     * @param ownerId 项目所有者ID
     * @param projectName 项目名称
     * @return 创建的项目
     */
    public Project createProject(String ownerId, String projectName) {
        // 验证输入参数
        if (ownerId == null || ownerId.trim().isEmpty()) {
            throw new IllegalArgumentException("用户ID不能为空");
        }

        // 验证权限：只有管理员才能创建项目
        User user = userRepository.findById(ownerId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));
        if (user.getRole() != User.Role.ADMIN) {
            throw new RuntimeException("只有管理员才能创建项目");
        }

        if (projectName == null || projectName.trim().isEmpty()) {
            throw new IllegalArgumentException("项目名称不能为空");
        }
        
        // 检查项目名称是否已存在（同一个用户下）
        if (projectRepository.existsByProjectNameAndOwnerId(projectName.trim(), ownerId)) {
            throw new RuntimeException("项目名称已存在: " + projectName);
        }
        
        // 创建新项目
        Project project = new Project();
        project.setProjectId(UUID.randomUUID().toString());
        project.setProjectName(projectName.trim());
        project.setOwnerId(ownerId);
        project.setStatus(Project.Status.ACTIVE);
        project.setProjectType("AI_DETECTION"); // 默认类型
        
        return projectRepository.save(project);
    }
    
    /**
     * 根据项目ID获取项目信息
     * @param projectId 项目ID
     * @return 项目信息
     */
    public Optional<Project> getProjectById(String projectId) {
        if (projectId == null || projectId.trim().isEmpty()) {
            throw new IllegalArgumentException("项目ID不能为空");
        }
        return projectRepository.findById(projectId);
    }
    
    /**
     * 获取用户的所有项目
     * @param ownerId 项目所有者ID
     * @return 项目列表
     */
    public List<Project> getProjectsByOwnerId(String ownerId) {
        if (ownerId == null || ownerId.trim().isEmpty()) {
            throw new IllegalArgumentException("用户ID不能为空");
        }
        return projectRepository.findByOwnerId(ownerId);
    }
    
    /**
     * 获取用户的活跃项目
     * @param ownerId 项目所有者ID
     * @return 活跃项目列表
     */
    public List<Project> getActiveProjectsByOwnerId(String ownerId) {
        if (ownerId == null || ownerId.trim().isEmpty()) {
            throw new IllegalArgumentException("用户ID不能为空");
        }
        return projectRepository.findByOwnerIdAndStatus(ownerId, Project.Status.ACTIVE);
    }
    
    /**
     * 统计用户的项目数量
     * @param ownerId 项目所有者ID
     * @return 项目数量
     */
    public long countProjectsByOwnerId(String ownerId) {
        if (ownerId == null || ownerId.trim().isEmpty()) {
            return 0;
        }
        return projectRepository.countByOwnerId(ownerId);
    }
    
    /**
     * 更新项目状态
     * @param projectId 项目ID
     * @param status 新状态
     * @return 更新后的项目
     */
    public Project updateProjectStatus(String projectId, Project.Status status) {
        Project project = projectRepository.findById(projectId)
            .orElseThrow(() -> new RuntimeException("项目不存在: " + projectId));
        
        project.setStatus(status);
        return projectRepository.save(project);
    }
    
    /**
     * 删除项目
     * @param projectId 项目ID
     */
    public void deleteProject(String projectId) {
        if (!projectRepository.existsById(projectId)) {
            throw new RuntimeException("项目不存在: " + projectId);
        }
        projectRepository.deleteById(projectId);
    }
    
    /**
     * 获取项目文件树结构和文件统计
     * @param projectId 项目ID
     * @param userId 用户ID
     * @return 包含文件树和总文件数的结果
     */
    public ProjectFileTreeResult getProjectFileTree(String projectId, String userId) {
        if (projectId == null || projectId.trim().isEmpty()) {
            throw new IllegalArgumentException("项目ID不能为空");
        }
        
        if (userId == null || userId.trim().isEmpty()) {
            throw new IllegalArgumentException("用户ID不能为空");
        }
        
        // 验证项目是否存在
        Optional<Project> project = projectRepository.findById(projectId);
        if (!project.isPresent()) {
            throw new RuntimeException("项目不存在: " + projectId);
        }
        
        // 验证权限
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("用户不存在"));
        
        if (user.getRole() != User.Role.ADMIN && !project.get().getOwnerId().equals(userId)) {
            // 如果不是管理员且不是所有者，检查是否有显式授权
            boolean hasPermission = permissionRepository.findByUserIdAndProjectId(userId, projectId).isPresent();
            if (!hasPermission) {
            throw new RuntimeException("无权限访问该项目: " + projectId);
            }
        }
        
        // 获取项目下的所有目录，按层级和名称排序
        List<Directory> directories = directoryRepository.findByProjectIdAndStatusOrderByDirLevelAscDirNameAsc(
            projectId, Directory.Status.ACTIVE);
        
        // 获取项目下的所有文件
        List<File> files = fileRepository.findByProjectIdOrderByDirectoryIdAscCreatedAtDesc(projectId);
        
        // 构建目录映射
        Map<String, List<Directory>> childrenMap = new HashMap<>();
        Map<String, Directory> directoryMap = new HashMap<>();
        List<Directory> rootDirectories = new ArrayList<>();
        
        for (Directory dir : directories) {
            directoryMap.put(dir.getDirId(), dir);
            
            if (dir.getParentId() == null) {
                // 根目录
                rootDirectories.add(dir);
            } else {
                // 子目录
                childrenMap.computeIfAbsent(dir.getParentId(), k -> new ArrayList<>()).add(dir);
            }
        }
        
        // 构建文件映射
        Map<String, List<File>> fileMap = new HashMap<>();
        for (File file : files) {
            fileMap.computeIfAbsent(file.getDirectoryId(), k -> new ArrayList<>()).add(file);
        }
        
        // 构建文件树
        List<ProjectFileTreeResponse.TreeNode> result = new ArrayList<>();
        for (Directory rootDir : rootDirectories) {
            ProjectFileTreeResponse.TreeNode rootNode = buildDirectoryTree(rootDir, childrenMap, fileMap);
            result.add(rootNode);
        }
        
        // 计算总文件数
        int totalFileCount = files.size();
        
        return new ProjectFileTreeResult(result, totalFileCount);
    }
    
    /**
     * 递归构建目录树
     */
    private ProjectFileTreeResponse.TreeNode buildDirectoryTree(
            Directory directory, 
            Map<String, List<Directory>> childrenMap, 
            Map<String, List<File>> fileMap) {
        
        List<ProjectFileTreeResponse.TreeNode> children = new ArrayList<>();
        
        // 添加子目录
        List<Directory> subDirectories = childrenMap.get(directory.getDirId());
        if (subDirectories != null) {
            for (Directory subDir : subDirectories) {
                ProjectFileTreeResponse.TreeNode subDirNode = buildDirectoryTree(subDir, childrenMap, fileMap);
                children.add(subDirNode);
            }
        }
        
        // 添加文件
        List<File> dirFiles = fileMap.get(directory.getDirId());
        if (dirFiles != null) {
            for (File file : dirFiles) {
                ProjectFileTreeResponse.TreeNode fileNode = new ProjectFileTreeResponse.TreeNode(
                    file.getFileId(),
                    file.getOriginalName(),
                    file.getProjectId(),
                    file.getUserId(),
                    file.getMimeType(), // 使用 mimeType 而不是 fileExtension
                    String.valueOf(file.getFileSize()),
                    file.getCreatedAt().format(DATE_TIME_FORMATTER)
                );
                children.add(fileNode);
            }
        }
        
        // 创建目录节点
        ProjectFileTreeResponse.TreeNode directoryNode = new ProjectFileTreeResponse.TreeNode(
            directory.getDirId(),
            directory.getDirName(),
            directory.getProjectId(),
            directory.getUserId(),
            children
        );
        
        return directoryNode;
    }
} 