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
    private WeldJointRepository weldJointRepository;

    @Autowired
    private FileRepository fileRepository;
    
    @Autowired
    private DirectoryRepository directoryRepository;
    
    @Autowired
    private ProjectRepository projectRepository;
    
    @Autowired
    private UserProjectPermissionRepository permissionRepository;

    @Autowired
    private UserRepository userRepository;
    
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
        // 校验主项目权限
        validateProjectAndUser(projectId, userId);
        
        Set<String> allFileIds = new HashSet<>();
        // 1. 处理选中的单个文件
        if (request.getSelectedFiles() != null) {
            for (TaskSubmitRequest.SelectedFile sf : request.getSelectedFiles()) {
                allFileIds.add(sf.getFileId());
            }
        }
        // 2. 处理选中的目录
        if (request.getDirectoryIds() != null) {
            for (String dirId : request.getDirectoryIds()) {
                expandDirectoryWithPermissionCheck(dirId, userId, allFileIds);
            }
        }
        // 3. 处理选中的项目（选中项目下所有文件）
        if (request.getProjectIds() != null) {
            for (String pId : request.getProjectIds()) {
                expandProjectWithPermissionCheck(pId, userId, allFileIds);
            }
        }

        if (allFileIds.isEmpty()) {
            throw new IllegalArgumentException("未选择任何待检测文件");
        }

        List<TaskFileInfo> taskFileInfos = buildFileInfosWithPermissionCheck(allFileIds, userId);
        String taskId = UUID.randomUUID().toString();
        Task task = new Task(taskId, projectId, userId, request.getName(), request.getDescription(), request.getAlgorithmType(), taskFileInfos.size());
        
        List<TaskFile> taskFiles = createTaskFileRecords(taskId, taskFileInfos);
        taskRepository.save(task);
        taskFileRepository.saveAll(taskFiles);
        
        scheduleAsyncProcessing(taskId);
        
        return new TaskSubmitResponse(taskId, task.getStatus().name().toLowerCase(), taskFileInfos.size(), task.getCreatedAt().format(DATE_TIME_FORMATTER));
    }

    private void expandDirectoryWithPermissionCheck(String directoryId, String userId, Set<String> allFileIds) {
        Directory directory = directoryRepository.findById(directoryId)
            .orElseThrow(() -> new RuntimeException("目录不存在: " + directoryId));
        
        // 校验对该目录所属项目的访问权限
        validateProjectAccess(directory.getProjectId(), userId);

        List<File> files = fileRepository.findByDirectoryId(directoryId);
        for (File f : files) {
            allFileIds.add(f.getFileId());
        }

        List<Directory> subDirs = directoryRepository.findByParentIdAndStatus(directoryId, Directory.Status.ACTIVE);
        for (Directory d : subDirs) {
            expandDirectoryWithPermissionCheck(d.getDirId(), userId, allFileIds);
        }
    }

    private void expandProjectWithPermissionCheck(String projectId, String userId, Set<String> allFileIds) {
        // 校验权限
        validateProjectAccess(projectId, userId);

        List<File> files = fileRepository.findByProjectId(projectId);
        for (File f : files) {
            allFileIds.add(f.getFileId());
        }
    }

    private List<TaskFileInfo> buildFileInfosWithPermissionCheck(Set<String> fileIds, String userId) {
        List<TaskFileInfo> taskFileInfos = new ArrayList<>();
        for (String fileId : fileIds) {
            Optional<File> fileOpt = fileRepository.findById(fileId);
            if (fileOpt.isPresent()) {
                File file = fileOpt.get();
                // 校验权限
                validateProjectAccess(file.getProjectId(), userId);
                taskFileInfos.add(new TaskFileInfo(fileId, buildLogicalFilePath(file), file.getFilePath()));
            }
        }
        return taskFileInfos;
    }

    @Transactional(readOnly = true)
    public ReportResultResponse getTaskReportResult(String userId, ReportResultRequest request) {
        if (request == null || request.getProjectIds() == null || request.getProjectIds().isEmpty()) {
            throw new IllegalArgumentException("项目ID列表不能为空");
        }

        // 1. 权限校验：确保用户对所有请求的项目有访问权限
        for (String projectId : request.getProjectIds()) {
            validateProjectAccess(projectId, userId);
        }

        // 2. 组装结果：一张底片可能关联多个焊口，一个焊口对应一条结果
        List<ReportResultResponse.ReportItem> items = new ArrayList<>();

        if (request.getWeldNos() != null && !request.getWeldNos().isEmpty()) {
            // 按焊口编号精确过滤：直接从匹配的焊口出发，一个焊口一条结果
            List<WeldJoint> matchedJoints = weldJointRepository.findByProjectIdsAndWeldNos(
                request.getProjectIds(), request.getWeldNos());
            for (WeldJoint joint : matchedJoints) {
                taskFileRepository.findById(joint.getTaskFileId())
                    .ifPresent(tf -> items.add(buildReportItem(tf, joint)));
            }
        } else {
            // 不按焊口过滤：列出项目下所有底片，每张底片按其焊口列表展开
            List<TaskFile> taskFiles = taskFileRepository.findByProjectIds(request.getProjectIds());
            for (TaskFile tf : taskFiles) {
                List<WeldJoint> joints = tf.getWeldJoints();
                if (joints == null || joints.isEmpty()) {
                    // 该底片尚未配置焊口（旧数据或未迁移），保留整张底片一条结果、携带全部缺陷
                    items.add(buildReportItem(tf, null));
                } else {
                    for (WeldJoint joint : joints) {
                        items.add(buildReportItem(tf, joint));
                    }
                    // 未被分配到任何焊口的缺陷，单独归入一条"未分组"结果，避免遗漏
                    boolean hasUnassignedDefect = tf.getDefectRecords().stream()
                        .anyMatch(dr -> dr.getWeldJointId() == null || dr.getWeldJointId().isEmpty());
                    if (hasUnassignedDefect) {
                        items.add(buildReportItem(tf, null));
                    }
                }
            }
        }

        return new ReportResultResponse(items);
    }

    /**
     * 组装单条报告结果。joint 为 null 表示未按焊口分组（旧数据没有焊口记录，
     * 或该底片已有焊口但这条结果专门承载"未分配焊口"的缺陷）。
     */
    private ReportResultResponse.ReportItem buildReportItem(TaskFile tf, WeldJoint joint) {
        ReportResultResponse.ReportItem item = new ReportResultResponse.ReportItem();
        item.setFileId(tf.getFileId());

        // 尝试获取文件名
        Optional<File> fileOpt = fileRepository.findById(tf.getFileId());
        item.setFileName(fileOpt.map(File::getOriginalName).orElse("unknown"));

        item.setFilmPixelValue(tf.getFilmPixelValue());
        item.setResolution(tf.getResolution());
        item.setSpecification(tf.getSpecification());
        item.setInspectionDate(tf.getInspectionDate());
        item.setWeldNo(joint != null ? joint.getWeldNo() : null);
        item.setSliceNo(tf.getFilmNumber());
        item.setFilmDensity(tf.getFilmDensity());
        item.setIqiSensitivity(tf.getSensitivity());
        item.setNormalizedSnr(tf.getNormalizedSnr());
        item.setQualityLevel(tf.getPlateQuality());

        // 评定结果逻辑：优先取人工结果，没有则取 ReviewStatus，最后取 VisionStatus
        if (tf.getManualResult() != null && !tf.getManualResult().isEmpty()) {
            item.setEvaluationResult(tf.getManualResult());
        } else if (tf.getReviewStatus() == TaskFile.ReviewStatus.CONFIRMED) {
            item.setEvaluationResult("合格"); // 默认确认即合格，需根据业务调整
        } else {
            item.setEvaluationResult(tf.getStatus() == TaskFile.Status.COMPLETED ? "待评定" : "检测中");
        }

        // 备注：使用 ErrorMessage 作为备注，或者 ManualResult 的一部分
        item.setRemark(tf.getErrorMessage());

        // 缺陷列表：按所属焊口过滤
        List<WeldJoint> allJoints = tf.getWeldJoints();
        List<ReportResultResponse.DefectItem> defects = new ArrayList<>();
        for (DefectRecord dr : tf.getDefectRecords()) {
            boolean belongsToThisItem;
            if (joint != null) {
                belongsToThisItem = joint.getWeldJointId().equals(dr.getWeldJointId());
            } else if (allJoints == null || allJoints.isEmpty()) {
                belongsToThisItem = true; // 底片未配置焊口，所有缺陷都归入这一条结果
            } else {
                belongsToThisItem = dr.getWeldJointId() == null || dr.getWeldJointId().isEmpty();
            }
            if (!belongsToThisItem) continue;

            ReportResultResponse.DefectItem d = new ReportResultResponse.DefectItem();
            d.setDefectId(dr.getDefectRecordId());
            d.setDefectNature(dr.getDefectName());
            // 优先使用 position (语义描述)，如果没有则使用 geometry (坐标JSON)
            d.setDefectLocation(dr.getPosition() != null ? dr.getPosition() : dr.getGeometry());
            d.setDefectSize(dr.getSize());
            d.setDefectLevel(dr.getGrade());
            d.setRemark(dr.getRemark());
            defects.add(d);
        }
        item.setDefects(defects);

        return item;
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
            tf.setErrorMessage(null);
            tf.setProcessingStartTime(null);
            tf.setProcessingEndTime(null);
            tf.setReviewStatus(TaskFile.ReviewStatus.PENDING);
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

    private void validateTaskSubmitRequest(TaskSubmitRequest request) {
        if (request == null) throw new IllegalArgumentException("任务提交请求不能为空");
        if (request.getName() == null || request.getName().trim().isEmpty()) throw new IllegalArgumentException("任务名称不能为空");
    }

    private void validateProjectAndUser(String projectId, String userId) {
        Optional<Project> project = projectRepository.findById(projectId);
        if (!project.isPresent()) throw new RuntimeException("项目不存在: " + projectId);
        
        // 检查用户是否有权限（管理员或所有者或有读写权限的用户）
        Optional<User> userOpt = userRepository.findById(userId);
        if (userOpt.isPresent() && userOpt.get().getRole() == User.Role.ADMIN) {
            return;
        }

        if (project.get().getOwnerId().equals(userId)) {
            return;
        }

        Optional<UserProjectPermission> permission = permissionRepository.findByUserIdAndProjectId(userId, projectId);
        if (permission.isPresent() && permission.get().getPermission() == UserProjectPermission.Permission.READ_WRITE) {
            return;
        }

        throw new RuntimeException("无权限访问或操作该项目: " + projectId);
    }

    private void validateProjectAccess(String projectId, String userId) {
        Optional<Project> project = projectRepository.findById(projectId);
        if (!project.isPresent()) throw new RuntimeException("项目不存在: " + projectId);
        
        // 管理员、所有者、或有读权限（READ_ONLY 或 READ_WRITE）
        Optional<User> userOpt = userRepository.findById(userId);
        if (userOpt.isPresent() && userOpt.get().getRole() == User.Role.ADMIN) {
            return;
        }

        if (project.get().getOwnerId().equals(userId)) {
            return;
        }

        Optional<UserProjectPermission> permission = permissionRepository.findByUserIdAndProjectId(userId, projectId);
        if (permission.isPresent()) {
            return;
            }

        throw new RuntimeException("无权限访问该项目: " + projectId);
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
        Runnable trigger = () -> CompletableFuture.runAsync(() -> {
            // 移除 sleep，因为已经确保在 commit 后执行
            try { taskProcessService.processTaskAsync(taskId); }
            catch (Exception e) { logger.error("启动异步处理失败: taskId={}, error={}", taskId, e.getMessage()); }
        });

        if (org.springframework.transaction.support.TransactionSynchronizationManager.isActualTransactionActive()) {
            org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(
                new org.springframework.transaction.support.TransactionSynchronization() {
                    @Override
                    public void afterCommit() {
                        trigger.run();
                    }
                }
            );
        } else {
            trigger.run();
        }
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
                taskFile.getStatus().name().toLowerCase(), taskFile.getVisionResult(),
                taskFile.getReportPath(), taskFile.getErrorMessage(),
                taskFile.getProcessingStartTime() != null ? taskFile.getProcessingStartTime().format(DATE_TIME_FORMATTER) : null,
                taskFile.getProcessingEndTime() != null ? taskFile.getProcessingEndTime().format(DATE_TIME_FORMATTER) : null,
                taskFile.getDefectPosition()
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
