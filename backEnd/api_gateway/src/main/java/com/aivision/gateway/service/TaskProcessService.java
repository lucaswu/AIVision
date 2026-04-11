package com.aivision.gateway.service;

import com.aivision.gateway.model.DefectRecord;
import com.aivision.gateway.model.DefectType;
import com.aivision.gateway.model.Task;
import com.aivision.gateway.model.TaskFile;
import com.aivision.gateway.repository.DefectRecordRepository;
import com.aivision.gateway.repository.DefectTypeRepository;
import com.aivision.gateway.repository.TaskFileRepository;
import com.aivision.gateway.repository.TaskRepository;
import com.aivision.gateway.service.storage.StorageStrategy;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
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
    private DefectRecordRepository defectRecordRepository;
    
    @Autowired
    private DefectTypeRepository defectTypeRepository;
    
    @Autowired
    private ReportService reportService;
    
    @Autowired
    private AiServiceClient aiServiceClient;

    @Autowired
    private StorageStrategy storageStrategy;

    @Value("${storage.local.result-dir:/app/data/results}")
    private String resultBaseDir;

    @Value("${storage.external-base-dir:/app/data/files}")
    private String inferenceInputBaseDir;
    
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

            stageFilesForInference(taskId, allTaskFiles);

            // 3. 一次性调用 Python 进行全量推理
            // 收集所有文件的相对路径 (使用 minioFilePath，即物理存储路径，包含 Project/User 层级)
            List<String> paths = allTaskFiles.stream().map(TaskFile::getMinioFilePath).collect(Collectors.toList());
            
            // 构建 minioFilePath -> TaskFile 的映射，用于后续查找 taskFileId
            Map<String, TaskFile> pathToTaskFile = allTaskFiles.stream()
                .collect(Collectors.toMap(TaskFile::getMinioFilePath, tf -> tf));
            
            // 3.1 准备进度更新的回调 (OCR已合并到Vision AI流水线，以Vision AI进度为准)
            final int totalFiles = allTaskFiles.size();
            final AtomicInteger visionProgress = new AtomicInteger(0);

            Runnable updateCombinedProgress = () -> {
                try {
                    Task currentTask = taskRepository.findById(taskId).orElse(null);
                    if (currentTask != null) {
                        int progress = visionProgress.get();
                        currentTask.setProcessedFiles(progress);
                        currentTask.setSuccessFiles(progress);
                        // 如果推理全部完成（即达到 100%），强制设置为 99%，
                        // 这样只有在后续写入数据库完成后才会变为 100%
                        if (progress == totalFiles && totalFiles > 0) {
                            currentTask.setProgress(99);
                        }
                        taskRepository.save(currentTask);
                    }
                } catch (Exception e) {
                    logger.warn("更新进度失败: taskId={}", taskId);
                }
            };

            // 3.2 调用 Vision AI 服务 (OCR已合并到推理流水线中，结果通过metadata.ocr返回)
            Map<String, String> visionResults = aiServiceClient.callBatchVisionAi(paths, taskId,
                (processedCount) -> {
                    visionProgress.set(processedCount);
                    updateCombinedProgress.run();
                },
                (errorLogs) -> {
                    try {
                        Task currentTask = taskRepository.findById(taskId).orElse(null);
                        if (currentTask != null) {
                            String errorMsg = String.join("\n", errorLogs);
                            if (errorMsg.length() > 60000) {
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

            logger.info("AI 服务调用完成: taskId={}, visionResults={}", taskId, visionResults.size());


            // 4. 处理结果并写回
            StringBuilder jsonBatch = new StringBuilder();
            int successCount = 0;
            int failedCount = 0;

            for (int j = 0; j < allTaskFiles.size(); j++) {
                TaskFile tf = allTaskFiles.get(j);
                // 使用 minioFilePath 从结果 map 中获取
                String res = visionResults.get(tf.getMinioFilePath());
                
                tf.setVisionResult(res);
                
                // 解析 metadata 中的建议评级
                if (res != null) {
                    try {
                        JsonNode root = objectMapper.readTree(res);
                        if (root.has("metadata") && root.get("metadata").has("suggested_quality_level")) {
                            String qLevel = root.get("metadata").get("suggested_quality_level").asText();
                            tf.setPlateQuality(qLevel);
                        }
                        // 解析矫正信息（由 AiServiceClient.transformToAIVisionFormat() 嵌入到 metadata）
                        JsonNode corrMeta = root.path("metadata");
                        if (!corrMeta.isMissingNode()) {
                            tf.setCorrectionRotation(corrMeta.path("correction_rotation").asInt(0));
                            tf.setCorrectionFlip(corrMeta.path("correction_flip").asBoolean(false));
                            // 解析焊缝位置检测结果（B 路径）
                            JsonNode weldLocNode = corrMeta.path("weld_location");
                            if (!weldLocNode.isMissingNode() && weldLocNode.isArray()) {
                                tf.setWeldLocation(weldLocNode.toString());
                            }
                            // 解析缺陷位置检测2结果（D 路径，含 origin_text、detections 完整数据）
                            JsonNode defectPosNode = corrMeta.path("defect_position");
                            if (!defectPosNode.isMissingNode() && defectPosNode.isObject()) {
                                tf.setDefectPosition(defectPosNode.toString());
                            }
                            // 解析灰度密度值（底片黑度），任务执行时始终用最新计算结果覆盖
                            String grayscaleDensity = corrMeta.path("grayscale_density").asText(null);
                            if (grayscaleDensity != null && !grayscaleDensity.isBlank()) {
                                tf.setFilmDensity(grayscaleDensity);
                            }
                        }
                    } catch (Exception e) {
                        logger.warn("解析建议评级失败: {}", e.getMessage());
                    }
                }
                
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
                    
                    // 5. 解析推理结果并保存到 defect_record 表
                    try {
                        saveDefectRecordsFromVisionResult(tf.getTaskFileId(), res);
                    } catch (Exception e) {
                        logger.warn("保存缺陷记录失败: taskFileId={}, error={}", tf.getTaskFileId(), e.getMessage());
                    }
                    
                    // 6. 从 Vision AI 结果顶层 ocr 节点提取 IQI 数据
                    try {
                        JsonNode ocrNode = objectMapper.readTree(res).path("ocr");
                        if (!ocrNode.isMissingNode() && !ocrNode.isNull()) {
                            parseOcrResultAndUpdateTaskFile(tf, objectMapper.writeValueAsString(ocrNode));
                        }
                    } catch (Exception e) {
                        logger.warn("解析OCR结果失败: taskFileId={}, error={}", tf.getTaskFileId(), e.getMessage());
                    }
                } else {
                    failedCount++;
                }
            }
            taskFileRepository.saveAll(allTaskFiles);

            // 6. 写入 JSON 文件内容
            Files.write(resultFilePath, jsonBatch.toString().getBytes("UTF-8"), StandardOpenOption.APPEND);
            
            // 7. 结束 JSON 数组并完成任务
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
    
    /**
     * 从视觉推理结果中解析并保存缺陷记录到数据库
     * 
     * 推理结果格式 (inference_results.json per image):
     * {
     *   "mode": "det",
     *   "image_path": "...",
     *   "rois": [{
     *     "roi_index": 0,
     *     "detections": [{
     *       "class_id": 7,
     *       "class_name": "其他",
     *       "confidence": 0.84,
     *       "bbox": [x1, y1, x2, y2]  // 左上右下
     *     }]
     *   }]
     * }
     * 
     * @param taskFileId 任务文件ID
     * @param visionResultJson 推理结果JSON字符串
     */
    private void saveDefectRecordsFromVisionResult(String taskFileId, String visionResultJson) throws Exception {
        JsonNode rootNode = objectMapper.readTree(visionResultJson);
        
        // 首先删除该 taskFileId 的所有旧记录（支持重新执行任务）
        defectRecordRepository.deleteByTaskFileId(taskFileId);
        
        List<DefectRecord> defectRecords = new ArrayList<>();
        
        // 解析 rois 数组
        JsonNode roisNode = rootNode.path("rois");
        if (roisNode.isArray()) {
            for (JsonNode roiNode : roisNode) {
                // 每个 ROI 包含 detections 数组
                JsonNode detectionsNode = roiNode.path("detections");
                if (detectionsNode.isArray()) {
                    for (JsonNode detection : detectionsNode) {
                        // 提取 class_name 和 bbox
                        String className = detection.path("class_name").asText(null);
                        JsonNode bboxNode = detection.path("bbox");
                        
                        if (className != null && bboxNode.isArray() && bboxNode.size() >= 4) {
                            // 模糊匹配缺陷类型名称
                            String matchedDefectName = matchDefectTypeName(className);
                            
                            // 转换 bbox 为前端支持的 rect 格式
                            String geometryJson = convertBboxToGeometry(bboxNode);
                            
                            if (geometryJson != null) {
                                DefectRecord record = new DefectRecord();
                                record.setDefectRecordId(UUID.randomUUID().toString());
                                record.setTaskFileId(taskFileId);
                                record.setDefectName(matchedDefectName);
                                record.setGeometry(geometryJson);
                                record.setCreatedAt(LocalDateTime.now());
                                record.setUpdatedAt(LocalDateTime.now());
                                // 其他字段暂时置空
                                record.setPosition(null);
                                record.setSize(null);
                                record.setGrade(null);
                                record.setRemark(null);
                                
                                defectRecords.add(record);
                            }
                        }
                    }
                }
            }
        }
        
        // 如果上面的格式解析失败，尝试解析 AIVision 转换后的格式 (results -> strName, vvContour)
        if (defectRecords.isEmpty()) {
            defectRecords = parseInferenceResultFormat(taskFileId, visionResultJson);
        }
        
        if (!defectRecords.isEmpty()) {
            defectRecordRepository.saveAll(defectRecords);
            logger.info("保存缺陷记录: taskFileId={}, count={}", taskFileId, defectRecords.size());
        }
    }
    
    /**
     * 解析推理服务返回的原始格式 (mode, rois, detections)
     */
    private List<DefectRecord> parseInferenceResultFormat(String taskFileId, String visionResultJson) throws Exception {
        List<DefectRecord> records = new ArrayList<>();
        
        // 尝试从原始推理结果格式解析
        // 这个格式可能是嵌套在 AiServiceClient.transformToAIVisionFormat 转换后的结果中
        JsonNode rootNode = objectMapper.readTree(visionResultJson);
        
        // 检查 metadata 和 results 结构 (AIVision 前端格式)
        JsonNode resultsArray = rootNode.path("results");
        if (resultsArray.isArray()) {
            for (JsonNode defectItem : resultsArray) {
                String strName = defectItem.path("strName").asText(null);
                JsonNode vvContour = defectItem.path("vvContour");
                
                if (strName != null && vvContour.isArray() && vvContour.size() > 0) {
                    DefectRecord record = new DefectRecord();
                    record.setDefectRecordId(UUID.randomUUID().toString());
                    record.setTaskFileId(taskFileId);
                    
                    // 模糊匹配缺陷类型名称
                    String matchedDefectName = matchDefectTypeName(strName);
                    record.setDefectName(matchedDefectName);
                    
                    // 将 vvContour 转换为 bbox 格式的 geometry
                    // vvContour 是 [[x1,y1], [x2,y1], [x2,y2], [x1,y2]] 格式
                    // 转换为 [x1, y1, x2, y2] 格式
                    String geometryJson = convertContourToGeometry(vvContour);
                    record.setGeometry(geometryJson);
                    
                    record.setCreatedAt(LocalDateTime.now());
                    record.setUpdatedAt(LocalDateTime.now());
                    
                    records.add(record);
                }
            }
        }
        
        return records;
    }
    
    /**
     * 从 resultItem 中提取缺陷名称
     */
    private String extractDefectName(JsonNode resultItem) {
        String strName = resultItem.path("strName").asText(null);
        if (strName != null) {
            return matchDefectTypeName(strName);
        }
        return null;
    }
    
    /**
     * 从 resultItem 中提取几何坐标
     */
    private String extractGeometry(JsonNode resultItem) {
        JsonNode vvContour = resultItem.path("vvContour");
        if (vvContour.isArray() && vvContour.size() > 0) {
            return convertContourToGeometry(vvContour);
        }
        return null;
    }
    
    /**
     * 将 vvContour 转换为前端支持的 rect 几何坐标 JSON
     * 输入: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]] 
     * 输出: {"type": "rect", "x": x1, "y": y1, "w": width, "h": height}
     */
    private String convertContourToGeometry(JsonNode vvContour) {
        try {
            if (!vvContour.isArray() || vvContour.size() < 2) {
                return null;
            }
            
            double minX = Double.MAX_VALUE, minY = Double.MAX_VALUE;
            double maxX = Double.MIN_VALUE, maxY = Double.MIN_VALUE;
            
            for (JsonNode point : vvContour) {
                if (point.isArray() && point.size() >= 2) {
                    double x = point.get(0).asDouble();
                    double y = point.get(1).asDouble();
                    minX = Math.min(minX, x);
                    minY = Math.min(minY, y);
                    maxX = Math.max(maxX, x);
                    maxY = Math.max(maxY, y);
                }
            }
            
            // 使用前端支持的 rect 格式: {"type":"rect","x":x,"y":y,"w":width,"h":height}
            Map<String, Object> geometry = new HashMap<>();
            geometry.put("type", "rect");
            geometry.put("x", minX);
            geometry.put("y", minY);
            geometry.put("w", maxX - minX);
            geometry.put("h", maxY - minY);
            
            return objectMapper.writeValueAsString(geometry);
        } catch (Exception e) {
            logger.warn("转换几何坐标失败: {}", e.getMessage());
            return null;
        }
    }
    
    /**
     * 将推理结果 bbox [x1, y1, x2, y2] 转换为前端支持的 rect 格式
     * 输入: [x1, y1, x2, y2] (左上右下)
     * 输出: {"type": "rect", "x": x1, "y": y1, "w": width, "h": height}
     */
    private String convertBboxToGeometry(JsonNode bboxNode) {
        try {
            if (!bboxNode.isArray() || bboxNode.size() < 4) {
                return null;
            }
            
            double x1 = bboxNode.get(0).asDouble();
            double y1 = bboxNode.get(1).asDouble();
            double x2 = bboxNode.get(2).asDouble();
            double y2 = bboxNode.get(3).asDouble();
            
            // 使用前端支持的 rect 格式
            Map<String, Object> geometry = new HashMap<>();
            geometry.put("type", "rect");
            geometry.put("x", x1);
            geometry.put("y", y1);
            geometry.put("w", x2 - x1);
            geometry.put("h", y2 - y1);
            
            return objectMapper.writeValueAsString(geometry);
        } catch (Exception e) {
            logger.warn("转换 bbox 几何坐标失败: {}", e.getMessage());
            return null;
        }
    }
    
    /**
     * 模糊匹配缺陷类型名称
     */
    private String matchDefectTypeName(String className) {
        if (className == null || className.isEmpty()) {
            return className;
        }
        
        try {
            // 尝试从数据库模糊匹配
            Optional<DefectType> matchedType = defectTypeRepository.findByNameContaining(className);
            if (matchedType.isPresent()) {
                return matchedType.get().getName();
            }
        } catch (Exception e) {
            logger.debug("模糊匹配缺陷类型失败: className={}", className);
        }
        
        // 如果没找到匹配，返回原名称
        return className;
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

    private void stageFilesForInference(String taskId, List<TaskFile> taskFiles) {
        Path basePath = Paths.get(inferenceInputBaseDir).normalize().toAbsolutePath();
        List<String> stagedPaths = new ArrayList<>();

        for (TaskFile taskFile : taskFiles) {
            String relativePath = taskFile.getMinioFilePath();
            if (relativePath == null || relativePath.isBlank()) {
                throw new RuntimeException("任务文件缺少存储路径: taskFileId=" + taskFile.getTaskFileId());
            }

            String normalizedRelativePath = relativePath.startsWith("/")
                    ? relativePath.substring(1)
                    : relativePath;
            Path targetPath = basePath.resolve(normalizedRelativePath).normalize();
            if (!targetPath.startsWith(basePath)) {
                throw new RuntimeException("非法的文件路径: " + relativePath);
            }

            try {
                if (Files.exists(targetPath) && Files.isRegularFile(targetPath) && Files.size(targetPath) > 0) {
                    stagedPaths.add(relativePath);
                    continue;
                }

                if (!storageStrategy.exists(relativePath)) {
                    throw new RuntimeException("存储中不存在待推理文件: " + relativePath);
                }

                Files.createDirectories(targetPath.getParent());
                try (InputStream inputStream = storageStrategy.download(relativePath)) {
                    Files.copy(inputStream, targetPath, StandardCopyOption.REPLACE_EXISTING);
                }
                stagedPaths.add(relativePath);
                logger.info("已准备推理输入文件: taskId={}, path={}", taskId, relativePath);
            } catch (Exception e) {
                throw new RuntimeException("准备推理输入文件失败: " + relativePath + ", " + e.getMessage(), e);
            }
        }

        logger.info("推理输入文件准备完成: taskId={}, count={}, baseDir={}",
                taskId, stagedPaths.size(), basePath);
    }
    
    /**
     * 从 IQIdet ocr 节点提取底片信息并更新 TaskFile
     *
     * 读取路径：
     *   fields.pipe_specs[0].value              → specification
     *   fields.weld_film_pairs[0].weld_no  → weldId
     *   fields.weld_film_pairs[0].film_no  → filmNumber
     *   grade                              → sensitivity
     */
    private void parseOcrResultAndUpdateTaskFile(TaskFile tf, String ocrResultJson) throws Exception {
        JsonNode rootNode = objectMapper.readTree(ocrResultJson);

        JsonNode fieldsNode = rootNode.path("fields");
        if (!fieldsNode.isMissingNode() && !fieldsNode.isNull()) {
            JsonNode weldFilmPairs = fieldsNode.path("weld_film_pairs");
            if (weldFilmPairs.isArray() && weldFilmPairs.size() > 0) {
                JsonNode pair = weldFilmPairs.get(0);
                String weldNo = pair.path("weld_no").asText(null);
                String filmNo = pair.path("film_no").asText(null);
                if (weldNo != null && !weldNo.isEmpty()) tf.setWeldId(weldNo);
                if (filmNo != null && !filmNo.isEmpty()) tf.setFilmNumber(filmNo);
            }

            JsonNode pipeSpecs = fieldsNode.path("pipe_specs");
            if (pipeSpecs.isArray() && pipeSpecs.size() > 0) {
                String specification = pipeSpecs.get(0).path("value").asText(null);
                if (specification != null && !specification.isEmpty()) tf.setSpecification(specification);
            }
        }

        JsonNode gradeNode = rootNode.path("grade");
        if (!gradeNode.isMissingNode() && !gradeNode.isNull()) {
            tf.setSensitivity(gradeNode.asText());
        }

        logger.debug("OCR解析完成: taskFileId={}, weldId={}, filmNumber={}, specification={}, sensitivity={}",
                     tf.getTaskFileId(), tf.getWeldId(), tf.getFilmNumber(), tf.getSpecification(), tf.getSensitivity());
    }
    
}
