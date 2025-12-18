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

import java.io.IOException;
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
    private AiServiceClient aiServiceClient;
    
    @Value("${storage.local.result-dir:/app/data/results}")
    private String resultBaseDir;
    
    private static final int BATCH_SIZE = 10;
    
    /**
     * 异步处理任务 (仅视觉 AI，结果追加到大的 JSON 文件中)
     */
    @Async("aiTaskExecutor")
    public void processTaskAsync(String taskId) {
        logger.info("开始处理任务 (仅视觉AI + JSON追加): taskId={}", taskId);
        
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

            int totalFiles = allTaskFiles.size();
            boolean isFirstBatch = true;

            // 3. 分批处理 (串行)
            for (int i = 0; i < totalFiles; i += BATCH_SIZE) {
                int endIndex = Math.min(i + BATCH_SIZE, totalFiles);
                List<TaskFile> batch = allTaskFiles.subList(i, endIndex);
                int batchIndex = (i / BATCH_SIZE) + 1;

                logger.info("处理批次 {}: taskId={}, range=[{}, {}]", batchIndex, taskId, i, endIndex);

                // 更新状态
                for (TaskFile tf : batch) {
                    tf.setStatus(TaskFile.Status.PROCESSING);
                    tf.setProcessingStartTime(LocalDateTime.now());
                }
                taskFileRepository.saveAll(batch);

                // a. 批量 Vision AI
                List<String> paths = batch.stream().map(TaskFile::getLogicalFilePath).collect(Collectors.toList());
                Map<String, String> visionResults = aiServiceClient.callBatchVisionAi(paths, taskId);

                // b. 写回 TaskFile 并准备追加到 JSON
                StringBuilder jsonBatch = new StringBuilder();
                for (int j = 0; j < batch.size(); j++) {
                    TaskFile tf = batch.get(j);
                    String res = visionResults.get(tf.getLogicalFilePath());
                    tf.setVisionResult(res);
                    tf.setStatus(res != null ? TaskFile.Status.COMPLETED : TaskFile.Status.FAILED);
                    tf.setProcessingEndTime(LocalDateTime.now());
                    
                    if (res != null) {
                        // 构造当前文件的结果对象
                        Map<String, Object> resultEntry = new HashMap<>();
                        resultEntry.put("fileId", tf.getFileId());
                        resultEntry.put("logicalPath", tf.getLogicalFilePath());
                        resultEntry.put("visionResult", objectMapper.readTree(res));
                        resultEntry.put("timestamp", LocalDateTime.now().toString());

                        if (!isFirstBatch || j > 0) {
                            jsonBatch.append(",");
                        }
                        jsonBatch.append(objectMapper.writeValueAsString(resultEntry));
                    }
                }
                taskFileRepository.saveAll(batch);

                // c. 追加写入 JSON 文件
                Files.write(resultFilePath, jsonBatch.toString().getBytes("UTF-8"), StandardOpenOption.APPEND);
                isFirstBatch = false;

                // d. 更新进度
                Task currentTask = taskRepository.findById(taskId).get();
                currentTask.setProcessedFiles(endIndex);
                int batchSuccess = (int) batch.stream().filter(tf -> tf.getStatus() == TaskFile.Status.COMPLETED).count();
                currentTask.setSuccessFiles(currentTask.getSuccessFiles() + batchSuccess);
                currentTask.setFailedFiles(currentTask.getFailedFiles() + (batch.size() - batchSuccess));
                taskRepository.save(currentTask);
            }

            // 4. 结束 JSON 数组并完成任务
            Files.write(resultFilePath, "]".getBytes("UTF-8"), StandardOpenOption.APPEND);
            
            Task finalTask = taskRepository.findById(taskId).get();
            finalTask.setStatus(Task.Status.COMPLETED);
            finalTask.setEndTime(LocalDateTime.now());
            taskRepository.save(finalTask);
            
            logger.info("任务处理完成 (结果已存入 JSON): taskId={}", taskId);
            
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
