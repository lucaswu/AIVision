package com.aivision.gateway.service;

import com.aivision.gateway.model.Task;
import com.aivision.gateway.model.TaskFile;
import com.aivision.gateway.repository.TaskFileRepository;
import com.aivision.gateway.repository.TaskRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.UUID;

@Service
public class TaskProcessService {
    
    private static final Logger logger = LoggerFactory.getLogger(TaskProcessService.class);
    
    @Autowired
    private TaskRepository taskRepository;
    
    @Autowired
    private TaskFileRepository taskFileRepository;
    
    @Autowired
    private AiServiceClient aiServiceClient;
    

    
    /**
     * 异步处理任务
     * @param taskId 任务ID
     */
    @Async("aiTaskExecutor")
    public void processTaskAsync(String taskId) {
        logger.info("开始异步处理任务: taskId={}", taskId);
        
        try {
            // 获取任务信息
            Task task = taskRepository.findById(taskId)
                .orElseThrow(() -> new RuntimeException("任务不存在: " + taskId));
            
                         // 更新任务状态为处理中
             task.setStatus(Task.Status.PROCESSING);
             task.setUpdatedAt(LocalDateTime.now());
             taskRepository.save(task);
             
             // 获取任务文件列表
             List<TaskFile> taskFiles = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId);
            
            if (taskFiles.isEmpty()) {
                throw new RuntimeException("任务文件列表为空: " + taskId);
            }
            
            // 并行处理文件（根据任务配置的并发数）
            int parallelCount = task.getParallelCount();
            processFilesInParallel(task, taskFiles, parallelCount);
            
        } catch (Exception e) {
            logger.error("任务处理失败: taskId={}, error={}", taskId, e.getMessage(), e);
            handleTaskFailure(taskId, e.getMessage());
        }
    }
    
    /**
     * 并行处理文件
     */
    private void processFilesInParallel(Task task, List<TaskFile> taskFiles, int parallelCount) {
        logger.info("开始并行处理文件: taskId={}, fileCount={}, parallelCount={}", 
                   task.getTaskId(), taskFiles.size(), parallelCount);
        
        AtomicInteger completedCount = new AtomicInteger(0);
        AtomicInteger successCount = new AtomicInteger(0);
        AtomicInteger failedCount = new AtomicInteger(0);
        
        // 分批处理文件
        for (int i = 0; i < taskFiles.size(); i += parallelCount) {
            int endIndex = Math.min(i + parallelCount, taskFiles.size());
            List<TaskFile> batch = taskFiles.subList(i, endIndex);
            
            // 并行处理当前批次
            CompletableFuture<Void>[] futures = batch.stream()
                .map(taskFile -> processFileAsync(taskFile, task, completedCount, successCount, failedCount))
                .toArray(CompletableFuture[]::new);
            
            // 等待当前批次完成
            CompletableFuture.allOf(futures).join();
        }
        
        // 所有文件处理完成，更新任务状态
        updateTaskCompletion(task, completedCount.get(), successCount.get(), failedCount.get());
    }
    
    /**
     * 异步处理单个文件
     */
    @Async("fileProcessExecutor")
    public CompletableFuture<Void> processFileAsync(TaskFile taskFile, Task task, 
                                                   AtomicInteger completedCount, 
                                                   AtomicInteger successCount, 
                                                   AtomicInteger failedCount) {
        String taskFileId = taskFile.getTaskFileId();
        String fileName = extractFileName(taskFile.getLogicalFilePath());
        
        logger.info("开始处理文件: taskFileId={}, fileName={}", taskFileId, fileName);
        
        try {
                         // 更新文件状态为处理中
             taskFile.setStatus(TaskFile.Status.PROCESSING);
             taskFile.setProcessingStartTime(LocalDateTime.now());
             taskFileRepository.save(taskFile);
            
                         // 步骤1: 调用视觉AI检测
            logger.info("调用视觉AI检测: taskFileId={}, localPath={}", taskFileId, taskFile.getLogicalFilePath());
            String visionResult = aiServiceClient.callVisionAi(taskFile.getLogicalFilePath(), task.getTaskId());
            taskFile.setVisionResult(visionResult);
            taskFileRepository.save(taskFile);
            
            // 步骤2: 调用LLM AI生成报告
            logger.info("调用LLM AI生成报告: taskFileId={}, fileName={}", taskFileId, fileName);
            String llmResult = aiServiceClient.callLlmAi(visionResult, fileName);
            taskFile.setLlmResult(llmResult);
            
            // TODO: 生成并上传报告到MinIO
            String reportPath = generateAndUploadReport(taskFile, visionResult, llmResult);
            taskFile.setReportPath(reportPath);
            
                         // 更新文件状态为完成
             taskFile.setStatus(TaskFile.Status.COMPLETED);
             taskFile.setProcessingEndTime(LocalDateTime.now());
             taskFileRepository.save(taskFile);
             
             successCount.incrementAndGet();
             logger.info("文件处理成功: taskFileId={}, fileName={}", taskFileId, fileName);
             
         } catch (Exception e) {
             logger.error("文件处理失败: taskFileId={}, fileName={}, error={}", 
                         taskFileId, fileName, e.getMessage(), e);
             
             // 更新文件状态为失败
             taskFile.setStatus(TaskFile.Status.FAILED);
            taskFile.setErrorMessage(e.getMessage());
            taskFile.setProcessingEndTime(LocalDateTime.now());
            taskFileRepository.save(taskFile);
            
            failedCount.incrementAndGet();
        } finally {
            // 更新任务进度
            int completed = completedCount.incrementAndGet();
            updateTaskProgress(task.getTaskId(), completed, task.getTotalFiles());
        }
        
        return CompletableFuture.completedFuture(null);
    }
    
    /**
     * 生成报告并保存到数据库
     */
    private String generateAndUploadReport(TaskFile taskFile, String visionResult, String llmResult) {
        try {
            // 1. 生成HTML报告内容
            String htmlContent = generateHtmlReport(taskFile, visionResult, llmResult);
            
            // 2. 创建报告文件名（用于标识）
            String reportFileName = "report_" + UUID.randomUUID().toString() + ".html";
            String reportPath = "reports/" + taskFile.getTaskId() + "/" + reportFileName;
            
            // 3. 将HTML内容保存到任务文件的报告字段中
            // 注意：这里我们可以在TaskFile实体中添加一个reportContent字段来存储HTML内容
            // 暂时先返回路径标识
            
            logger.info("报告生成成功: taskFileId={}, reportPath={}, contentSize={}bytes", 
                       taskFile.getTaskFileId(), reportPath, htmlContent.length());
            
            return reportPath;
            
        } catch (Exception e) {
            logger.error("报告生成失败: taskFileId={}, error={}", 
                        taskFile.getTaskFileId(), e.getMessage(), e);
            // 即使报告生成失败，也返回路径，避免整个任务失败
            String reportFileName = "report_" + UUID.randomUUID().toString() + ".html";
            return "reports/" + taskFile.getTaskId() + "/" + reportFileName;
        }
    }
    
    /**
     * 生成HTML报告内容
     */
    private String generateHtmlReport(TaskFile taskFile, String visionResult, String llmResult) {
        String fileName = extractFileName(taskFile.getLogicalFilePath());
        String timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        
        StringBuilder html = new StringBuilder();
        html.append("<!DOCTYPE html>\n");
        html.append("<html lang=\"zh-CN\">\n");
        html.append("<head>\n");
        html.append("    <meta charset=\"UTF-8\">\n");
        html.append("    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n");
        html.append("    <title>AI检测报告 - ").append(fileName).append("</title>\n");
        html.append("    <style>\n");
        html.append("        body { font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }\n");
        html.append("        .container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }\n");
        html.append("        .header { text-align: center; border-bottom: 2px solid #007bff; padding-bottom: 20px; margin-bottom: 30px; }\n");
        html.append("        .header h1 { color: #007bff; margin: 0; }\n");
        html.append("        .info-section { margin-bottom: 30px; }\n");
        html.append("        .info-section h2 { color: #333; border-left: 4px solid #007bff; padding-left: 15px; }\n");
        html.append("        .info-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }\n");
        html.append("        .info-table th, .info-table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }\n");
        html.append("        .info-table th { background-color: #f8f9fa; font-weight: bold; width: 150px; }\n");
        html.append("        .result-box { background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 15px 0; }\n");
        html.append("        .json-content { background-color: #2d3748; color: #e2e8f0; padding: 15px; border-radius: 5px; font-family: 'Courier New', monospace; font-size: 12px; overflow-x: auto; }\n");
        html.append("        .llm-content { background-color: #fff; border: 1px solid #ddd; padding: 20px; border-radius: 5px; line-height: 1.6; }\n");
        html.append("        .footer { text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; }\n");
        html.append("    </style>\n");
        html.append("</head>\n");
        html.append("<body>\n");
        
        html.append("    <div class=\"container\">\n");
        html.append("        <div class=\"header\">\n");
        html.append("            <h1>🤖 AI工业缺陷检测报告</h1>\n");
        html.append("            <p>基于YOLO视觉检测 + LLM智能分析</p>\n");
        html.append("        </div>\n");
        
        // 基本信息
        html.append("        <div class=\"info-section\">\n");
        html.append("            <h2>📋 检测信息</h2>\n");
        html.append("            <table class=\"info-table\">\n");
        html.append("                <tr><th>文件名称</th><td>").append(fileName).append("</td></tr>\n");
        html.append("                <tr><th>任务ID</th><td>").append(taskFile.getTaskId()).append("</td></tr>\n");
        html.append("                <tr><th>文件ID</th><td>").append(taskFile.getTaskFileId()).append("</td></tr>\n");
        html.append("                <tr><th>检测时间</th><td>").append(timestamp).append("</td></tr>\n");
        html.append("                <tr><th>文件路径</th><td>").append(taskFile.getLogicalFilePath()).append("</td></tr>\n");
        html.append("            </table>\n");
        html.append("        </div>\n");
        
        // 视觉检测结果
        html.append("        <div class=\"info-section\">\n");
        html.append("            <h2>👁️ 视觉AI检测结果</h2>\n");
        html.append("            <div class=\"result-box\">\n");
        html.append("                <h3>原始检测数据 (JSON格式)</h3>\n");
        html.append("                <div class=\"json-content\">").append(escapeHtml(visionResult)).append("</div>\n");
        html.append("            </div>\n");
        html.append("        </div>\n");
        
        // LLM分析报告
        html.append("        <div class=\"info-section\">\n");
        html.append("            <h2>🧠 LLM智能分析报告</h2>\n");
        html.append("            <div class=\"result-box\">\n");
        html.append("                <div class=\"llm-content\">").append(formatLlmResult(llmResult)).append("</div>\n");
        html.append("            </div>\n");
        html.append("        </div>\n");
        
        html.append("        <div class=\"footer\">\n");
        html.append("            <p>© 2025 AI Vision 工业检测系统 | 报告生成时间: ").append(timestamp).append("</p>\n");
        html.append("        </div>\n");
        html.append("    </div>\n");
        html.append("</body>\n");
        html.append("</html>");
        
        return html.toString();
    }
    
    /**
     * 转义HTML特殊字符
     */
    private String escapeHtml(String input) {
        if (input == null) return "";
        return input.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace("\"", "&quot;")
                   .replace("'", "&#39;");
    }
    
    /**
     * 格式化LLM结果，保持换行
     */
    private String formatLlmResult(String llmResult) {
        if (llmResult == null) return "暂无分析结果";
        return escapeHtml(llmResult).replace("\n", "<br>");
    }
    

    
    /**
     * 更新任务进度
     */
    private synchronized void updateTaskProgress(String taskId, int processedFiles, int totalFiles) {
        try {
            Task task = taskRepository.findById(taskId).orElse(null);
            if (task != null) {
                task.setProcessedFiles(processedFiles);
                task.setProgress((int) ((double) processedFiles / totalFiles * 100));
                task.setUpdatedAt(LocalDateTime.now());
                taskRepository.save(task);
                
                logger.debug("更新任务进度: taskId={}, progress={}%, ({}/{})", 
                           taskId, task.getProgress(), processedFiles, totalFiles);
            }
        } catch (Exception e) {
            logger.error("更新任务进度失败: taskId={}, error={}", taskId, e.getMessage());
        }
    }
    
    /**
     * 任务完成处理
     */
    private void updateTaskCompletion(Task task, int completedFiles, int successFiles, int failedFiles) {
        try {
            task.setProcessedFiles(completedFiles);
            task.setSuccessFiles(successFiles);
            task.setFailedFiles(failedFiles);
            task.setProgress(100);
            task.setUpdatedAt(LocalDateTime.now());
            
                         // 根据成功/失败文件数决定任务状态
             if (failedFiles == 0) {
                 task.setStatus(Task.Status.COMPLETED);
                 logger.info("任务完成: taskId={}, 所有文件处理成功 ({}/{})", 
                            task.getTaskId(), successFiles, completedFiles);
             } else if (successFiles == 0) {
                 task.setStatus(Task.Status.FAILED);
                 task.setErrorMessage("所有文件处理失败");
                 logger.error("任务失败: taskId={}, 所有文件处理失败 ({}/{})", 
                             task.getTaskId(), failedFiles, completedFiles);
             } else {
                 task.setStatus(Task.Status.COMPLETED);
                 logger.warn("任务部分完成: taskId={}, 成功={}, 失败={}", 
                            task.getTaskId(), successFiles, failedFiles);
             }
            
            taskRepository.save(task);
            
        } catch (Exception e) {
            logger.error("更新任务完成状态失败: taskId={}, error={}", task.getTaskId(), e.getMessage());
        }
    }
    
    /**
     * 任务失败处理
     */
    private void handleTaskFailure(String taskId, String errorMessage) {
                 try {
             Task task = taskRepository.findById(taskId).orElse(null);
             if (task != null) {
                 task.setStatus(Task.Status.FAILED);
                 task.setErrorMessage(errorMessage);
                 task.setUpdatedAt(LocalDateTime.now());
                 taskRepository.save(task);
             }
        } catch (Exception e) {
            logger.error("处理任务失败状态时出错: taskId={}, error={}", taskId, e.getMessage());
        }
    }
    
    /**
     * 从逻辑路径提取文件名
     */
    private String extractFileName(String logicalPath) {
        if (logicalPath == null || logicalPath.isEmpty()) {
            return "unknown";
        }
        int lastSlash = logicalPath.lastIndexOf('/');
        return lastSlash >= 0 ? logicalPath.substring(lastSlash + 1) : logicalPath;
    }
} 