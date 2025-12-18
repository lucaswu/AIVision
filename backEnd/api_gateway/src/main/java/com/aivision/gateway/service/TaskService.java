package com.aivision.gateway.service;

import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Service
@Transactional
public class TaskService {
    
    private static final Logger logger = LoggerFactory.getLogger(TaskService.class);
    
    @Autowired
    private TaskRepository taskRepository;
    
    @Autowired
    private TaskFileRepository taskFileRepository;
    
    @Autowired
    private FileRepository fileRepository;
    
    @Autowired
    private DirectoryRepository directoryRepository;
    
    @Autowired
    private ProjectRepository projectRepository;
    
    @Autowired
    private TaskProcessService taskProcessService;
    
    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    
    /**
     * 获取状态的中文描述
     */
    private String getStatusText(String status) {
        switch (status.toLowerCase()) {
            case "pending": return "等待中";
            case "processing": return "处理中";
            case "completed": return "已完成";
            case "failed": return "失败";
            case "cancelled": return "已取消";
            default: return status;
        }
    }
    
    /**
     * 提交检测任务
     * @param projectId 项目ID
     * @param userId 用户ID
     * @param request 任务提交请求
     * @return 任务提交响应
     */
    @Transactional
    public TaskSubmitResponse submitTask(String projectId, String userId, TaskSubmitRequest request) {
        // 1. 验证输入参数
        validateTaskSubmitRequest(request);
        
        // 2. 验证项目和用户权限
        validateProjectAndUser(projectId, userId);
        
        // 3. 验证并构建文件信息
        List<TaskFileInfo> taskFileInfos = validateAndBuildFileInfos(request.getSelectedFiles(), projectId, userId);
        
        // 4. 生成任务ID
        String taskId = UUID.randomUUID().toString();
        
        // 5. 创建任务记录
        Task task = createTaskRecord(taskId, projectId, userId, request, taskFileInfos.size());
        
        // 6. 创建任务文件记录
        List<TaskFile> taskFiles = createTaskFileRecords(taskId, taskFileInfos);
        
        // 7. 保存到数据库
        taskRepository.save(task);
        taskFileRepository.saveAll(taskFiles);
        
        // 8. 创建响应对象
        TaskSubmitResponse response = new TaskSubmitResponse(
            taskId,
            task.getStatus().name().toLowerCase(),
            taskFileInfos.size(),
            task.getCreatedAt().format(DATE_TIME_FORMATTER)
        );
        
        // 9. 延迟启动异步处理（确保事务已提交）
        scheduleAsyncProcessing(taskId);
        
        return response;
    }
    
    /**
     * 验证任务提交请求
     */
    private void validateTaskSubmitRequest(TaskSubmitRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("任务提交请求不能为空");
        }
        if (request.getName() == null || request.getName().trim().isEmpty()) {
            throw new IllegalArgumentException("任务名称不能为空");
        }
        // ProjectId和UserId现在从参数传入，不需要从request中获取
        if (request.getSelectedFiles() == null || request.getSelectedFiles().isEmpty()) {
            throw new IllegalArgumentException("选择的文件列表不能为空");
        }
        if (request.getSelectedFiles().size() > 100) {
            throw new IllegalArgumentException("单次任务最多支持100个文件");
        }
    }
    
    /**
     * 验证项目和用户权限
     */
    private void validateProjectAndUser(String projectId, String userId) {
        Optional<Project> project = projectRepository.findById(projectId);
        if (!project.isPresent()) {
            throw new RuntimeException("项目不存在: " + projectId);
        }
        
        // 验证项目是否属于当前用户
        if (!project.get().getOwnerId().equals(userId)) {
            throw new RuntimeException("无权限访问该项目: " + projectId);
        }
    }
    
    /**
     * 验证并构建文件信息
     */
    private List<TaskFileInfo> validateAndBuildFileInfos(List<TaskSubmitRequest.SelectedFile> selectedFiles, String projectId, String userId) {
        List<TaskFileInfo> taskFileInfos = new ArrayList<>();
        
        for (TaskSubmitRequest.SelectedFile selectedFile : selectedFiles) {
            // 验证文件是否存在
            Optional<File> fileOpt = fileRepository.findByFileIdAndProjectIdAndUserId(
                selectedFile.getFileId(), projectId, userId);
            
            if (!fileOpt.isPresent()) {
                throw new RuntimeException("文件不存在或无权限访问: " + selectedFile.getFileId());
            }
            
            File file = fileOpt.get();
            
            // 自动构建逻辑路径
            String logicalPath = buildLogicalFilePath(file);
            
            TaskFileInfo taskFileInfo = new TaskFileInfo(
                selectedFile.getFileId(),
                logicalPath,
                file.getFilePath() // MinIO实际路径
            );
            taskFileInfos.add(taskFileInfo);
        }
        
        return taskFileInfos;
    }
    
    /**
     * 构建逻辑文件路径
     */
    private String buildLogicalFilePath(File file) {
        // 递归构建目录路径
        String directoryPath = buildDirectoryPath(file.getDirectoryId());
        return directoryPath + "/" + file.getOriginalName();
    }
    
    /**
     * 递归构建目录路径
     */
    private String buildDirectoryPath(String directoryId) {
        Optional<Directory> dirOpt = directoryRepository.findById(directoryId);
        if (!dirOpt.isPresent()) {
            return "";
        }
        
        Directory directory = dirOpt.get();
        if (directory.getParentId() == null) {
            // 根目录
            return "/" + directory.getDirName();
        } else {
            // 递归构建父目录路径
            String parentPath = buildDirectoryPath(directory.getParentId());
            return parentPath + "/" + directory.getDirName();
        }
    }
    
    /**
     * 创建任务记录
     */
    private Task createTaskRecord(String taskId, String projectId, String userId, TaskSubmitRequest request, int totalFiles) {
        return new Task(
            taskId,
            projectId,
            userId,
            request.getName(),
            request.getDescription(),
            request.getAlgorithmType(),
            totalFiles
        );
    }
    
    /**
     * 创建任务文件记录
     */
    private List<TaskFile> createTaskFileRecords(String taskId, List<TaskFileInfo> taskFileInfos) {
        List<TaskFile> taskFiles = new ArrayList<>();
        
        for (TaskFileInfo taskFileInfo : taskFileInfos) {
            String taskFileId = UUID.randomUUID().toString();
            TaskFile taskFile = new TaskFile(
                taskFileId,
                taskId,
                taskFileInfo.getFileId(),
                taskFileInfo.getLogicalFilePath(),
                taskFileInfo.getMinioFilePath()
            );
            taskFiles.add(taskFile);
        }
        
        return taskFiles;
    }
    
    /**
     * 内部类：任务文件信息
     */
    private static class TaskFileInfo {
        private String fileId;
        private String logicalFilePath;
        private String minioFilePath;
        
        public TaskFileInfo(String fileId, String logicalFilePath, String minioFilePath) {
            this.fileId = fileId;
            this.logicalFilePath = logicalFilePath;
            this.minioFilePath = minioFilePath;
        }
        
        public String getFileId() {
            return fileId;
        }
        
        public String getLogicalFilePath() {
            return logicalFilePath;
        }
        
        public String getMinioFilePath() {
            return minioFilePath;
        }
    }
    
    /**
     * 延迟启动异步处理
     * 使用单独的事务确保主事务已提交
     */
    private void scheduleAsyncProcessing(String taskId) {
        // 使用CompletableFuture在新线程中延迟执行
        java.util.concurrent.CompletableFuture.runAsync(() -> {
            try {
                // 短暂延迟确保主事务已提交
                Thread.sleep(100);
                taskProcessService.processTaskAsync(taskId);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                logger.error("异步处理启动被中断: taskId={}", taskId);
            } catch (Exception e) {
                logger.error("启动异步处理失败: taskId={}, error={}", taskId, e.getMessage());
            }
        });
    }
    
    /**
     * 获取任务状态和结果
     * @param taskId 任务ID
     * @param projectId 项目ID
     * @param userId 用户ID
     * @return 任务状态响应
     */
    @Transactional(readOnly = true)
    public TaskStatusResponse getTaskStatus(String taskId, String projectId, String userId) {
        // 1. 验证任务是否存在且有权限访问
        Optional<Task> taskOpt = taskRepository.findByTaskIdAndProjectIdAndUserId(taskId, projectId, userId);
        if (!taskOpt.isPresent()) {
            throw new RuntimeException("任务不存在或无权限访问: " + taskId);
        }
        
        Task task = taskOpt.get();
        
        // 2. 获取任务文件列表（按创建时间排序）
        List<TaskFile> taskFiles = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId);
        
        // 3. 构建任务文件结果列表
        List<TaskStatusResponse.TaskFileResult> selectedFiles = new ArrayList<>();
        int processingFiles = 0;
        int inQueueFiles = 0;
        
        for (TaskFile taskFile : taskFiles) {
            // 统计不同状态的文件数量
            TaskFile.Status fileStatus = taskFile.getStatus();
            if (fileStatus == TaskFile.Status.PROCESSING) {
                processingFiles++;
            } else if (fileStatus == TaskFile.Status.PENDING) {
                inQueueFiles++;
            }
            
            // 获取原始文件信息以获取文件名
            Optional<File> fileOpt = fileRepository.findById(taskFile.getFileId());
            String fileName = fileOpt.isPresent() ? fileOpt.get().getOriginalName() : "unknown";
            
            TaskStatusResponse.TaskFileResult fileResult = new TaskStatusResponse.TaskFileResult(
                taskFile.getTaskFileId(),
                taskFile.getFileId(),
                fileName,
                taskFile.getLogicalFilePath(),
                taskFile.getStatus().name().toLowerCase(),
                taskFile.getVisionResult(),
                taskFile.getLlmResult(),
                taskFile.getReportPath(),
                taskFile.getErrorMessage(),
                taskFile.getProcessingStartTime() != null ? 
                    taskFile.getProcessingStartTime().format(DATE_TIME_FORMATTER) : null,
                taskFile.getProcessingEndTime() != null ? 
                    taskFile.getProcessingEndTime().format(DATE_TIME_FORMATTER) : null
            );
            selectedFiles.add(fileResult);
        }
        
        // 4. 构建响应对象
        TaskStatusResponse response = new TaskStatusResponse(
            task.getTaskId(),
            task.getTaskName(),
            task.getDescription(),
            task.getProjectId(),
            task.getUserId(),
            task.getAlgorithmType(),
            task.getTotalFiles(),
            task.getProcessedFiles(),
            task.getSuccessFiles(),
            task.getFailedFiles(),
            task.getCreatedAt().format(DATE_TIME_FORMATTER),
            task.getUpdatedAt().format(DATE_TIME_FORMATTER),
            task.getStatus().name().toLowerCase(),
            task.getProgress(),
            task.getErrorMessage(),
            selectedFiles,
            processingFiles,
            inQueueFiles
        );
        
        return response;
    }
    
    /**
     * 获取任务列表
     * @param projectId 项目ID
     * @param userId 用户ID
     * @return 任务列表响应
     */
    @Transactional(readOnly = true)
    public TaskListResponse getTaskList(String projectId, String userId) {
        // 1. 验证项目和用户权限
        validateProjectAndUser(projectId, userId);
        
        // 2. 获取用户在该项目下的所有任务（按创建时间倒序）
        List<Task> tasks = taskRepository.findByProjectIdAndUserIdOrderByCreatedAtDesc(projectId, userId);
        
        if (tasks.isEmpty()) {
            return new TaskListResponse(new ArrayList<>(), 0);
        }

        // 3. 批量查询优化 (解决 N+1 问题)
        List<String> taskIds = new ArrayList<>();
        for (Task task : tasks) {
            taskIds.add(task.getTaskId());
        }

        // 3.1 批量查询所有任务文件
        List<TaskFile> allTaskFiles = taskFileRepository.findByTaskIdInOrderByCreatedAtAsc(taskIds);
        
        // 按 taskId 分组
        Map<String, List<TaskFile>> taskFilesMap = new HashMap<>();
        List<String> fileIds = new ArrayList<>();
        
        for (TaskFile tf : allTaskFiles) {
            taskFilesMap.computeIfAbsent(tf.getTaskId(), k -> new ArrayList<>()).add(tf);
            fileIds.add(tf.getFileId());
        }

        // 3.2 批量查询所有文件详情
        List<File> allFiles = new ArrayList<>();
        if (!fileIds.isEmpty()) {
            allFiles = fileRepository.findByFileIdIn(fileIds);
        }
        
        // 按 fileId 映射
        Map<String, File> fileMap = new HashMap<>();
        for (File f : allFiles) {
            fileMap.put(f.getFileId(), f);
        }
        
        // 4. 构建任务列表项 (完全在内存中进行，不查询数据库)
        List<TaskListResponse.TaskListItem> taskListItems = new ArrayList<>();
        
        for (Task task : tasks) {
            // 从内存 Map 获取任务文件列表
            List<TaskFile> taskFiles = taskFilesMap.getOrDefault(task.getTaskId(), new ArrayList<>());
            
            // 构建任务文件项列表
            List<TaskListResponse.TaskFileItem> taskFileItems = new ArrayList<>();
            for (TaskFile taskFile : taskFiles) {
                // 从内存 Map 获取文件名
                File file = fileMap.get(taskFile.getFileId());
                String fileName = (file != null) ? file.getOriginalName() : "unknown";
                
                TaskListResponse.TaskFileItem taskFileItem = new TaskListResponse.TaskFileItem(
                    taskFile.getTaskFileId(),
                    taskFile.getFileId(),
                    fileName,
                    taskFile.getLogicalFilePath(),
                    taskFile.getStatus().name().toLowerCase(),
                    taskFile.getVisionResult(),
                    taskFile.getLlmResult(),
                    taskFile.getReportPath(),
                    taskFile.getErrorMessage(),
                    taskFile.getProcessingStartTime() != null ? 
                        taskFile.getProcessingStartTime().format(DATE_TIME_FORMATTER) : null,
                    taskFile.getProcessingEndTime() != null ? 
                        taskFile.getProcessingEndTime().format(DATE_TIME_FORMATTER) : null
                );
                taskFileItems.add(taskFileItem);
            }
            
            // 构建任务列表项
            TaskListResponse.TaskListItem taskListItem = new TaskListResponse.TaskListItem(
                task.getTaskId(),
                task.getTaskName(),
                task.getDescription(),
                task.getProjectId(),
                task.getUserId(),
                task.getAlgorithmType(),
                task.getStatus().name().toLowerCase(),
                task.getProgress(),
                task.getTotalFiles(),
                task.getProcessedFiles(),
                task.getSuccessFiles(),
                task.getFailedFiles(),
                task.getCreatedAt().format(DATE_TIME_FORMATTER),
                task.getUpdatedAt().format(DATE_TIME_FORMATTER),
                task.getErrorMessage()
            );
            
            // 设置任务文件列表
            taskListItem.setTaskFiles(taskFileItems);
            taskListItems.add(taskListItem);
        }
        
        // 5. 构建响应对象
        TaskListResponse response = new TaskListResponse(taskListItems, taskListItems.size());
        
        return response;
    }
    
    /**
     * 更新任务
     * @param taskId 任务ID
     * @param projectId 项目ID
     * @param userId 用户ID
     * @param request 任务更新请求
     * @return 更新后的任务信息
     */
    @Transactional
    public Task updateTask(String taskId, String projectId, String userId, TaskUpdateRequest request) {
        try {
            // 1. 验证任务是否存在并且用户有权限访问
            Optional<Task> taskOpt = taskRepository.findByTaskIdAndProjectIdAndUserId(taskId, projectId, userId);
            if (!taskOpt.isPresent()) {
                throw new IllegalArgumentException("任务不存在或无权限访问");
            }
            
            Task task = taskOpt.get();
            
            // 2. 检查任务状态，只有pending状态的任务可以编辑
            if (!Task.Status.PENDING.equals(task.getStatus())) {
                String statusText = getStatusText(task.getStatus().toString());
                throw new IllegalArgumentException("任务当前状态为「" + statusText + "」，只有等待中的任务可以编辑");
            }
            
            // 3. 更新任务信息
            task.setTaskName(request.getName());
            task.setDescription(request.getDescription());
            task.setAlgorithmType(request.getAlgorithmType());
            task.setUpdatedAt(LocalDateTime.now());
            
            // 4. 保存更新
            Task updatedTask = taskRepository.save(task);
            
            logger.info("成功更新任务: {} (用户: {}, 项目: {})", taskId, userId, projectId);
            
            return updatedTask;
            
        } catch (IllegalArgumentException e) {
            logger.warn("更新任务失败 - {}: {}", taskId, e.getMessage());
            throw e;
        } catch (Exception e) {
            logger.error("更新任务失败 - {}: {}", taskId, e.getMessage(), e);
            throw new RuntimeException("更新任务失败: " + e.getMessage(), e);
        }
    }

    /**
     * 删除任务
     * @param taskId 任务ID
     * @param projectId 项目ID
     * @param userId 用户ID
     * @return 删除是否成功
     */
    @Transactional
    public boolean deleteTask(String taskId, String projectId, String userId) {
        try {
            // 1. 验证任务是否存在并且用户有权限访问
            Optional<Task> taskOpt = taskRepository.findByTaskIdAndProjectIdAndUserId(taskId, projectId, userId);
            if (!taskOpt.isPresent()) {
                throw new IllegalArgumentException("任务不存在或无权限访问");
            }
            
            Task task = taskOpt.get();
            
            // 2. 删除关联的任务文件记录
            List<TaskFile> taskFiles = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId);
            if (!taskFiles.isEmpty()) {
                taskFileRepository.deleteByTaskId(taskId);
                logger.info("删除任务 {} 的 {} 个任务文件记录", taskId, taskFiles.size());
            }
            
            // 3. 删除任务记录
            taskRepository.delete(task);
            logger.info("成功删除任务: {}", taskId);
            
            return true;
            
        } catch (IllegalArgumentException e) {
            logger.warn("删除任务失败 - {}: {}", taskId, e.getMessage());
            throw e;
        } catch (Exception e) {
            logger.error("删除任务失败 - {}: {}", taskId, e.getMessage(), e);
            throw new RuntimeException("删除任务失败: " + e.getMessage(), e);
        }
    }
} 