package com.aivision.gateway.service;

import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.CompletableFuture;

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

    @Value("${storage.local.result-dir:/app/data/results}")
    private String resultBaseDir;
    
    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    
    /**
     * 提交检测任务
     */
    @Transactional
    public TaskSubmitResponse submitTask(String projectId, String userId, TaskSubmitRequest request) {
        validateTaskSubmitRequest(request);
        validateProjectAndUser(projectId, userId);
        
        Set<String> allFileIds = new HashSet<>();
        if (request.getSelectedFiles() != null) {
            for (TaskSubmitRequest.SelectedFile sf : request.getSelectedFiles()) {
                allFileIds.add(sf.getFileId());
            }
        }
        if (request.getDirectoryIds() != null) {
            for (String dirId : request.getDirectoryIds()) {
                expandDirectory(dirId, projectId, userId, allFileIds);
            }
        }

        if (allFileIds.isEmpty()) {
            throw new IllegalArgumentException("未选择任何待检测文件");
        }

        List<TaskFileInfo> taskFileInfos = buildFileInfos(allFileIds, projectId, userId);
        String taskId = UUID.randomUUID().toString();
        Task task = new Task(taskId, projectId, userId, request.getName(), request.getDescription(), request.getAlgorithmType(), taskFileInfos.size());
        
        List<TaskFile> taskFiles = createTaskFileRecords(taskId, taskFileInfos);
        taskRepository.save(task);
        taskFileRepository.saveAll(taskFiles);
        
        scheduleAsyncProcessing(taskId);
        
        return new TaskSubmitResponse(taskId, task.getStatus().name().toLowerCase(), taskFileInfos.size(), task.getCreatedAt().format(DATE_TIME_FORMATTER));
    }

    @Transactional
    public void restartTask(String taskId, String projectId, String userId) {
        Task task = taskRepository.findById(taskId).orElseThrow(() -> new RuntimeException("任务不存在: " + taskId));
        if (!task.getProjectId().equals(projectId) || !task.getUserId().equals(userId)) throw new RuntimeException("无权限操作此任务");
        if (task.getIsArchived() != null && task.getIsArchived()) throw new RuntimeException("任务已归档，无法重启");

        // 删除旧结果文件
        if (task.getTaskReport() != null) {
            try {
                Files.deleteIfExists(Paths.get(resultBaseDir, task.getTaskReport()));
            } catch (IOException e) {
                logger.warn("删除旧结果文件失败: {}", e.getMessage());
            }
        }

        task.setStatus(Task.Status.PENDING);
        task.setProgress(0);
        task.setProcessedFiles(0);
        task.setSuccessFiles(0);
        task.setFailedFiles(0);
        task.setTaskReport(null);
        task.setErrorMessage(null);
        task.setEndTime(null);
        task.setUpdatedAt(LocalDateTime.now());
        taskRepository.save(task);

        List<TaskFile> taskFiles = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId);
        for (TaskFile tf : taskFiles) {
            tf.setStatus(TaskFile.Status.PENDING);
            tf.setVisionResult(null);
            tf.setLlmResult(null);
            tf.setErrorMessage(null);
            tf.setProcessingStartTime(null);
            tf.setProcessingEndTime(null);
        }
        taskFileRepository.saveAll(taskFiles);

        scheduleAsyncProcessing(taskId);
    }

    @Transactional
    public void archiveTask(String taskId, String projectId, String userId, boolean archived) {
        Task task = taskRepository.findById(taskId).orElseThrow(() -> new RuntimeException("任务不存在: " + taskId));
        if (!task.getProjectId().equals(projectId) || !task.getUserId().equals(userId)) throw new RuntimeException("无权限操作此任务");
        task.setIsArchived(archived);
        taskRepository.save(task);
    }

    @Transactional
    public String duplicateTask(String taskId, String projectId, String userId) {
        Task sourceTask = taskRepository.findById(taskId).orElseThrow(() -> new RuntimeException("原任务不存在: " + taskId));
        String newTaskId = UUID.randomUUID().toString();
        Task newTask = new Task(newTaskId, projectId, userId, sourceTask.getTaskName() + " (副本)", sourceTask.getDescription(), sourceTask.getAlgorithmType(), sourceTask.getTotalFiles());
        taskRepository.save(newTask);

        List<TaskFile> sourceFiles = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId);
        List<TaskFile> newFiles = new ArrayList<>();
        for (TaskFile sf : sourceFiles) {
            newFiles.add(new TaskFile(UUID.randomUUID().toString(), newTaskId, sf.getFileId(), sf.getLogicalFilePath(), sf.getMinioFilePath()));
        }
        taskFileRepository.saveAll(newFiles);
        return newTaskId;
    }

    private void expandDirectory(String directoryId, String projectId, String userId, Set<String> allFileIds) {
        List<File> files = fileRepository.findByProjectIdAndUserIdAndDirectoryIdOrderByCreatedAtDesc(projectId, userId, directoryId);
        for (File f : files) allFileIds.add(f.getFileId());
        List<Directory> subDirs = directoryRepository.findByProjectIdAndUserIdAndParentIdAndStatus(projectId, userId, directoryId, Directory.Status.ACTIVE);
        for (Directory d : subDirs) expandDirectory(d.getDirId(), projectId, userId, allFileIds);
    }

    private void validateTaskSubmitRequest(TaskSubmitRequest request) {
        if (request == null) throw new IllegalArgumentException("任务提交请求不能为空");
        if (request.getName() == null || request.getName().trim().isEmpty()) throw new IllegalArgumentException("任务名称不能为空");
    }

    private void validateProjectAndUser(String projectId, String userId) {
        Optional<Project> project = projectRepository.findById(projectId);
        if (!project.isPresent()) throw new RuntimeException("项目不存在: " + projectId);
        if (!project.get().getOwnerId().equals(userId)) throw new RuntimeException("无权限访问该项目: " + projectId);
    }

    private List<TaskFileInfo> buildFileInfos(Set<String> fileIds, String projectId, String userId) {
        List<TaskFileInfo> taskFileInfos = new ArrayList<>();
        for (String fileId : fileIds) {
            Optional<File> fileOpt = fileRepository.findByFileIdAndProjectIdAndUserId(fileId, projectId, userId);
            if (fileOpt.isPresent()) {
                File file = fileOpt.get();
                taskFileInfos.add(new TaskFileInfo(fileId, buildLogicalFilePath(file), file.getFilePath()));
            }
        }
        return taskFileInfos;
    }

    private String buildLogicalFilePath(File file) {
        return buildDirectoryPath(file.getDirectoryId()) + "/" + file.getOriginalName();
    }

    private String buildDirectoryPath(String directoryId) {
        Optional<Directory> dirOpt = directoryRepository.findById(directoryId);
        if (!dirOpt.isPresent()) return "";
        Directory directory = dirOpt.get();
        if (directory.getParentId() == null) return "/" + directory.getDirName();
        else return buildDirectoryPath(directory.getParentId()) + "/" + directory.getDirName();
    }

    private List<TaskFile> createTaskFileRecords(String taskId, List<TaskFileInfo> taskFileInfos) {
        List<TaskFile> taskFiles = new ArrayList<>();
        for (TaskFileInfo info : taskFileInfos) {
            taskFiles.add(new TaskFile(UUID.randomUUID().toString(), taskId, info.getFileId(), info.getLogicalFilePath(), info.getMinioFilePath()));
        }
        return taskFiles;
    }

    private void scheduleAsyncProcessing(String taskId) {
        CompletableFuture.runAsync(() -> {
            try { Thread.sleep(200); taskProcessService.processTaskAsync(taskId); }
            catch (Exception e) { logger.error("启动异步处理失败: taskId={}, error={}", taskId, e.getMessage()); }
        });
    }

    @Transactional(readOnly = true)
    public TaskStatusResponse getTaskStatus(String taskId, String projectId, String userId) {
        Task task = taskRepository.findByTaskIdAndProjectIdAndUserId(taskId, projectId, userId)
            .orElseThrow(() -> new RuntimeException("任务不存在: " + taskId));
        
        List<TaskFile> taskFiles = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId);
        List<TaskStatusResponse.TaskFileResult> selectedFiles = new ArrayList<>();
        int processingFiles = 0;
        int inQueueFiles = 0;
        
        for (TaskFile taskFile : taskFiles) {
            if (taskFile.getStatus() == TaskFile.Status.PROCESSING) processingFiles++;
            else if (taskFile.getStatus() == TaskFile.Status.PENDING) inQueueFiles++;
            Optional<File> fileOpt = fileRepository.findById(taskFile.getFileId());
            String fileName = fileOpt.isPresent() ? fileOpt.get().getOriginalName() : "unknown";
            selectedFiles.add(new TaskStatusResponse.TaskFileResult(
                taskFile.getTaskFileId(), taskFile.getFileId(), fileName, taskFile.getLogicalFilePath(),
                taskFile.getStatus().name().toLowerCase(), taskFile.getVisionResult(), taskFile.getLlmResult(),
                taskFile.getReportPath(), taskFile.getErrorMessage(),
                taskFile.getProcessingStartTime() != null ? taskFile.getProcessingStartTime().format(DATE_TIME_FORMATTER) : null,
                taskFile.getProcessingEndTime() != null ? taskFile.getProcessingEndTime().format(DATE_TIME_FORMATTER) : null
            ));
        }
        
        TaskStatusResponse resp = new TaskStatusResponse(
            task.getTaskId(), task.getTaskName(), task.getDescription(), task.getProjectId(), task.getUserId(),
            task.getAlgorithmType(), task.getTotalFiles(), task.getProcessedFiles(), task.getSuccessFiles(), task.getFailedFiles(),
            task.getCreatedAt().format(DATE_TIME_FORMATTER), task.getUpdatedAt().format(DATE_TIME_FORMATTER),
            task.getStatus().name().toLowerCase(), task.getProgress(), task.getErrorMessage(), selectedFiles,
            processingFiles, inQueueFiles
        );
        resp.setIsArchived(task.getIsArchived());
        if (task.getEndTime() != null) resp.setEndTime(task.getEndTime().format(DATE_TIME_FORMATTER));
        
        // 从磁盘加载结果 JSON 内容
        resp.setTaskReport(loadResultContentFromDisk(task.getTaskReport()));
        
        return resp;
    }

    private String loadResultContentFromDisk(String relativePath) {
        if (relativePath == null || relativePath.isEmpty()) return null;
        try {
            Path path = Paths.get(resultBaseDir, relativePath);
            if (Files.exists(path)) {
                return new String(Files.readAllBytes(path), "UTF-8");
            }
        } catch (IOException e) {
            logger.warn("读取结果文件失败: {}, error={}", relativePath, e.getMessage());
        }
        return null;
    }

    @Transactional(readOnly = true)
    public TaskListResponse getTaskList(String projectId, String userId) {
        validateProjectAndUser(projectId, userId);
        List<Task> tasks = taskRepository.findByProjectIdAndUserIdOrderByCreatedAtDesc(projectId, userId);
        List<TaskListResponse.TaskListItem> items = new ArrayList<>();
        for (Task task : tasks) {
            TaskListResponse.TaskListItem item = new TaskListItemBuilder(task).build();
            items.add(item);
        }
        return new TaskListResponse(items, items.size());
    }

    private class TaskListItemBuilder {
        private Task task;
        public TaskListItemBuilder(Task task) { this.task = task; }
        public TaskListResponse.TaskListItem build() {
            TaskListResponse.TaskListItem item = new TaskListResponse.TaskListItem(
                task.getTaskId(), task.getTaskName(), task.getDescription(), task.getProjectId(), task.getUserId(),
                task.getAlgorithmType(), task.getStatus().name().toLowerCase(), task.getProgress(),
                task.getTotalFiles(), task.getProcessedFiles(), task.getSuccessFiles(), task.getFailedFiles(),
                task.getCreatedAt().format(DATE_TIME_FORMATTER), task.getUpdatedAt().format(DATE_TIME_FORMATTER),
                task.getErrorMessage()
            );
            item.setIsArchived(task.getIsArchived());
            if (task.getEndTime() != null) item.setEndTime(task.getEndTime().format(DATE_TIME_FORMATTER));
            return item;
        }
    }

    @Transactional
    public Task updateTask(String taskId, String projectId, String userId, TaskUpdateRequest request) {
        Task task = taskRepository.findByTaskIdAndProjectIdAndUserId(taskId, projectId, userId).orElseThrow(() -> new IllegalArgumentException("任务不存在或无权限访问"));
        if (task.getIsArchived() != null && task.getIsArchived()) throw new IllegalArgumentException("任务已归档，不可修改");
        task.setTaskName(request.getName());
        task.setDescription(request.getDescription());
        task.setAlgorithmType(request.getAlgorithmType());
        task.setUpdatedAt(LocalDateTime.now());
        return taskRepository.save(task);
    }

    @Transactional
    public boolean deleteTask(String taskId, String projectId, String userId) {
        Task task = taskRepository.findByTaskIdAndProjectIdAndUserId(taskId, projectId, userId).orElseThrow(() -> new IllegalArgumentException("任务不存在或无权限访问"));
        if (task.getIsArchived() != null && task.getIsArchived()) throw new IllegalArgumentException("任务已归档，不可删除");
        
        // 删除磁盘上的结果文件
        if (task.getTaskReport() != null) {
            try { Files.deleteIfExists(Paths.get(resultBaseDir, task.getTaskReport())); }
            catch (IOException e) { logger.warn("删除结果文件失败: {}", e.getMessage()); }
        }

        taskFileRepository.deleteByTaskId(taskId);
        taskRepository.delete(task);
        return true;
    }

    private static class TaskFileInfo {
        private String fileId; private String logicalFilePath; private String minioFilePath;
        public TaskFileInfo(String fileId, String logicalFilePath, String minioFilePath) {
            this.fileId = fileId; this.logicalFilePath = logicalFilePath; this.minioFilePath = minioFilePath;
        }
        public String getFileId() { return fileId; }
        public String getLogicalFilePath() { return logicalFilePath; }
        public String getMinioFilePath() { return minioFilePath; }
    }
}
