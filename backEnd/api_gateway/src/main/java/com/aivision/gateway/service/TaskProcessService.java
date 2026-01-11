package com.aivision.gateway.service;

import com.aivision.gateway.model.Task;
import com.aivision.gateway.model.TaskFile;
import com.aivision.gateway.repository.TaskFileRepository;
import com.aivision.gateway.repository.TaskRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;

import java.util.Map;
import java.util.stream.Collectors;

@Service
public class TaskProcessService {
    
    private static final Logger logger = LoggerFactory.getLogger(TaskProcessService.class);
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    @Autowired
    private TaskRepository taskRepository;
    
    @Autowired
    private TaskFileRepository taskFileRepository;
    
    @Autowired
    private ReportService reportService;
    
    @Autowired
    private AiServiceClient aiServiceClient;
    
    @Value("${storage.local.result-dir:/app/data/results}")
    private String resultBaseDir;
    
    // 修改为一次性处理所有文件，不再分批，以配合 Python 批量推理的高效性
    // private static final int BATCH_SIZE = 10;
    
    /**
     * 异步处理任务 (仅视觉 AI，结果追加到大的 JSON 文件中)
     */
    @Async("aiTaskExecutor")
    public void processTaskAsync(String taskId) {
        logger.info("开始处理任务 (全量 Python 批量处理): taskId={}", taskId);
        
        try {
            Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在: " + taskId));
            
            // 1. 初始化结果文件 (JSON 格式)
            String resultRelativePath = "result_" + taskId + ".json";
            Path resultFilePath = Paths.get(resultBaseDir, resultRelativePath);
            Files.createDirectories(resultFilePath.getParent());
            
            // 初始化为 JSON 数组开始
            Files.write(resultFilePath, "[".getBytes("UTF-8"));

            // 2. 更新数据库状态
            task.setStatus(Task.Status.PROCESSING);
            task.setUpdatedAt(LocalDateTime.now());
            task.setTaskReport(resultRelativePath); // 借用此字段存储 JSON 结果路径
            taskRepository.save(task);
            
            List<TaskFile> allTaskFiles = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId);
            if (allTaskFiles.isEmpty()) {
                handleTaskFailure(taskId, "任务文件列表为空");
                return;
            }

            // 更新所有文件状态为 PROCESSING
            for (TaskFile tf : allTaskFiles) {
                tf.setStatus(TaskFile.Status.PROCESSING);
                tf.setProcessingStartTime(LocalDateTime.now());
            }
            taskFileRepository.saveAll(allTaskFiles);

            // 3. 一次性调用 Python 进行全量推理
            // 收集所有文件的相对路径 (使用 minioFilePath，即物理存储路径，包含 Project/User 层级)
            List<String> paths = allTaskFiles.stream().map(TaskFile::getMinioFilePath).collect(Collectors.toList());
            
            // 3.1 准备进度更新的回调
            final int totalFiles = allTaskFiles.size();
            
            // 3.2 调用 Python (耗时操作)
            Map<String, String> visionResults = aiServiceClient.callBatchVisionAi(paths, taskId, 
                // 进度回调
                (processedCount) -> {
                    try {
                        Task currentTask = taskRepository.findById(taskId).orElse(null);
                        if (currentTask != null) {
                            currentTask.setProcessedFiles(processedCount);
                            // 估算成功数，准确数等结束后更新
                            currentTask.setSuccessFiles(processedCount); 
                            taskRepository.save(currentTask);
                        }
                    } catch (Exception e) {
                        logger.warn("更新进度失败: taskId={}", taskId);
                    }
                },
                // 错误日志回调
                (errorLogs) -> {
                    try {
                        Task currentTask = taskRepository.findById(taskId).orElse(null);
                        if (currentTask != null) {
                            String errorMsg = String.join("\n", errorLogs);
                            // 截断过长的日志
                            if (errorMsg.length() > 60000) { // 数据库字段限制预留
                                errorMsg = errorMsg.substring(errorMsg.length() - 60000);
                            }
                            currentTask.setErrorMessage(errorMsg);
                            taskRepository.save(currentTask);
                        }
                    } catch (Exception e) {
                        logger.error("保存错误日志失败: taskId={}", taskId);
                    }
                }
            );


            // 4. 处理结果并写回
            StringBuilder jsonBatch = new StringBuilder();
            int successCount = 0;
            int failedCount = 0;

            for (int j = 0; j < allTaskFiles.size(); j++) {
                TaskFile tf = allTaskFiles.get(j);
                // 使用 minioFilePath 从结果 map 中获取
                String res = visionResults.get(tf.getMinioFilePath());
                
                tf.setVisionResult(res);
                
                // 只要有结果返回就算成功完成处理，无论是否有缺陷
                tf.setStatus(res != null ? TaskFile.Status.COMPLETED : TaskFile.Status.FAILED);
                tf.setProcessingEndTime(LocalDateTime.now());
                
                if (res != null) {
                    successCount++;
                    // 构造当前文件的结果对象，用于追加到大 JSON
                    Map<String, Object> resultEntry = new HashMap<>();
                    resultEntry.put("fileId", tf.getFileId());
                    resultEntry.put("logicalPath", tf.getLogicalFilePath());
                    resultEntry.put("visionResult", objectMapper.readTree(res));
                    resultEntry.put("timestamp", LocalDateTime.now().toString());

                    if (j > 0) {
                        jsonBatch.append(",");
                    }
                    jsonBatch.append(objectMapper.writeValueAsString(resultEntry));
                } else {
                    failedCount++;
                }
            }
            taskFileRepository.saveAll(allTaskFiles);

            // 5. 写入 JSON 文件内容
            Files.write(resultFilePath, jsonBatch.toString().getBytes("UTF-8"), StandardOpenOption.APPEND);
            
            // 6. 结束 JSON 数组并完成任务
            Files.write(resultFilePath, "]".getBytes("UTF-8"), StandardOpenOption.APPEND);
            
            Task finalTask = taskRepository.findById(taskId).get();
            finalTask.setProcessedFiles(allTaskFiles.size());
            finalTask.setSuccessFiles(successCount);
            finalTask.setFailedFiles(failedCount);
            finalTask.setStatus(Task.Status.COMPLETED);
            finalTask.setEndTime(LocalDateTime.now());
            taskRepository.save(finalTask);
            
            // 任务完成，生成报告
            try {
                reportService.generateReportForTask(taskId);
            } catch (Exception e) {
                logger.error("生成报告失败: taskId={}, error={}", taskId, e.getMessage());
            }
            
            logger.info("任务处理完成: taskId={}, success={}, failed={}", taskId, successCount, failedCount);
            
        } catch (Exception e) {
            logger.error("任务处理异常: taskId={}, error={}", taskId, e.getMessage(), e);
            handleTaskFailure(taskId, e.getMessage());
        }
    }
    
    private void handleTaskFailure(String taskId, String errorMessage) {
        try {
            Task task = taskRepository.findById(taskId).orElse(null);
            if (task != null) {
                task.setStatus(Task.Status.FAILED);
                task.setErrorMessage(errorMessage);
                task.setEndTime(LocalDateTime.now());
                taskRepository.save(task);
            }
        } catch (Exception e) {
            logger.error("记录任务失败状态出错: taskId={}", taskId, e);
        }
    }
}
