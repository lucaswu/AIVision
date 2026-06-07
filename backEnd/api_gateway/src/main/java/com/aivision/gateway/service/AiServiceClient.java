package com.aivision.gateway.service;

import com.aivision.gateway.repository.DefectTypeRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.function.Consumer;

/**
 * AI 推理服务客户端
 * 通过 HTTP 调用独立的 Python 推理服务
 */
@Service
public class AiServiceClient {
    
    private static final Logger logger = LoggerFactory.getLogger(AiServiceClient.class);
    private final ObjectMapper objectMapper = new ObjectMapper();

    // 连接超时短、读取超时大：推理服务不可达时快速失败，又不会打断耗时较长的正常推理
    @Value("${ai-services.http.connect-timeout-ms:10000}")
    private int httpConnectTimeoutMs;

    @Value("${ai-services.http.read-timeout-ms:1800000}")
    private int httpReadTimeoutMs;

    private RestTemplate restTemplate;

    @javax.annotation.PostConstruct
    void initRestTemplate() {
        org.springframework.http.client.SimpleClientHttpRequestFactory factory =
            new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(httpConnectTimeoutMs);
        factory.setReadTimeout(httpReadTimeoutMs);
        this.restTemplate = new RestTemplate(factory);
    }

    @Autowired
    private DefectTypeRepository defectTypeRepository;

    // 推理服务 URL
    @Value("${ai-services.inference-url:http://ai-inference:8000}")
    private String inferenceServiceUrl;

    // OCR 推理服务 URL
    @Value("${ai-services.ocr-inference-url:http://ai-inference-ocr:8000}")
    private String ocrInferenceServiceUrl;

    // 推理模式配置
    @Value("${ai-services.vision-ai.inference-mode:det}")
    private String inferenceMode;
    
    @Value("${ai-services.vision-ai.engine:rfdet}")
    private String engineType;

    @Value("${ai-services.vision-ai.device:cuda:0}")
    private String device;
    
    // 检测置信度
    @Value("${ai-services.vision-ai.det-confidence:0.25}")
    private double detConfidence;
    
    // 是否启用横切纵拼
    @Value("${ai-services.vision-ai.det-wide-slice:true}")
    private boolean detWideSlice;
    
    // 本地存储路径（用于读取结果）
    @Value("${storage.local.result-dir:/app/data/results}")
    private String localResultDir;

    // 超时配置
    @Value("${ai-services.vision-ai.timeout-minutes:1440}")
    private int timeoutMinutes;

    // 轮询间隔（毫秒）
    private static final long POLL_INTERVAL_MS = 500;
    
    // 缓存的类别名称
    private List<String> cachedClassNames = null;

    /**
     * 获取缺陷类型名称列表（从数据库读取，带缓存）
     */
    private List<String> getClassNames() {
        if (cachedClassNames == null) {
            try {
                cachedClassNames = defectTypeRepository.findAllEnabledDefectTypeNames();
                logger.info("从数据库加载缺陷类型名称: {}", cachedClassNames);
            } catch (Exception e) {
                logger.warn("无法从数据库加载缺陷类型名称，使用默认值: {}", e.getMessage());
                // 默认值
                cachedClassNames = Arrays.asList(
                    "裂纹", "未熔合", "未焊透", "条形缺陷", 
                    "圆形缺陷", "咬边", "内凹", "其他"
                );
            }
        }
        return cachedClassNames;
    }

    /**
     * 批量调用视觉AI检测服务，支持进度回调
     * @param relativeStoredPaths 一批文件的逻辑/相对路径列表
     * @param taskId 任务ID
     * @param progressCallback 进度回调函数，参数为已完成数量
     * @param errorLogCallback 错误日志回调函数，参数为日志内容
     * @return Map (relativePath -> visionResultJson)
     */
    public Map<String, String> callBatchVisionAi(List<String> relativeStoredPaths, String taskId, 
                                                Consumer<Integer> progressCallback, 
                                                Consumer<List<String>> errorLogCallback) {
        return callBatchVisionAi(relativeStoredPaths, taskId, progressCallback, errorLogCallback, null);
    }

    public Map<String, String> callBatchVisionAi(List<String> relativeStoredPaths, String taskId,
                                                Consumer<Integer> progressCallback,
                                                Consumer<List<String>> errorLogCallback,
                                                StatusCallback statusCallback) {
        if (relativeStoredPaths == null || relativeStoredPaths.isEmpty()) {
            return new HashMap<>();
        }

        logger.info("批量调用 Vision AI 服务 (HTTP): count={}, taskId={}", relativeStoredPaths.size(), taskId);
        
        try {
            // 1. 提交推理任务
            submitInferenceTask(taskId, relativeStoredPaths);
            
            // 2. 轮询等待完成
            waitForCompletion(taskId, relativeStoredPaths.size(), progressCallback, errorLogCallback, statusCallback);
            
            // 3. 获取并解析结果
            return fetchAndParseResults(taskId, relativeStoredPaths);
            
        } catch (Exception e) {
            logger.error("调用推理服务失败: taskId={}", taskId, e);
            if (errorLogCallback != null) {
                errorLogCallback.accept(List.of("推理服务调用失败: " + e.getMessage()));
            }
            throw new RuntimeException("调用推理服务失败", e);
        }
    }

    @FunctionalInterface
    interface StatusCallback {
        void accept(String status, String stage, int progress, int total, String currentFile);
    }

    /**
     * 提交推理任务到 Python 服务
     */
    private void submitInferenceTask(String taskId, List<String> filePaths) {
        String url = inferenceServiceUrl + "/inference/submit";
        
        Map<String, Object> request = new HashMap<>();
        request.put("task_id", taskId);
        request.put("file_paths", filePaths);
        request.put("mode", inferenceMode);
        request.put("engine", engineType);
        request.put("device", device);
        // 新增参数
        request.put("class_names", getClassNames());
        request.put("primary_conf", detConfidence);
        request.put("wide_slice", detWideSlice);
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);
        
        logger.info("提交推理任务: url={}, taskId={}, fileCount={}, classNames={}", 
                    url, taskId, filePaths.size(), getClassNames());
        
        try {
            ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
            
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("提交推理任务失败: " + response.getStatusCode());
            }
            
            logger.info("推理任务已提交: taskId={}", taskId);
            
        } catch (Exception e) {
            logger.error("提交推理任务失败: taskId={}", taskId, e);
            throw new RuntimeException("提交推理任务失败: " + e.getMessage(), e);
        }
    }

    /**
     * 轮询等待任务完成
     */
    private void waitForCompletion(String taskId, int totalFiles, 
                                   Consumer<Integer> progressCallback, 
                                   Consumer<List<String>> errorLogCallback) {
        waitForCompletion(taskId, totalFiles, progressCallback, errorLogCallback, null);
    }

    private void waitForCompletion(String taskId, int totalFiles,
                                   Consumer<Integer> progressCallback,
                                   Consumer<List<String>> errorLogCallback,
                                   StatusCallback statusCallback) {
        String statusUrl = inferenceServiceUrl + "/inference/" + taskId + "/status";
        long startTime = System.currentTimeMillis();
        long timeoutMs = timeoutMinutes * 60 * 1000L;
        
        int lastProgress = 0;
        
        while (true) {
            // 检查超时
            if (System.currentTimeMillis() - startTime > timeoutMs) {
                throw new RuntimeException("推理任务超时: " + timeoutMinutes + "分钟");
            }
            
            try {
                ResponseEntity<String> response = restTemplate.getForEntity(statusUrl, String.class);
                
                if (!response.getStatusCode().is2xxSuccessful()) {
                    Thread.sleep(POLL_INTERVAL_MS);
                    continue;
                }
                
                JsonNode statusNode = objectMapper.readTree(response.getBody());
                String status = statusNode.path("status").asText();
                int progress = statusNode.path("progress").asInt();
                int total = statusNode.path("total").asInt(totalFiles);
                String currentFile = statusNode.path("current_file").asText(null);
                String stage = statusNode.path("stage").asText("");
                logger.info("推理任务状态: taskId={}, status={}, progress={}/{}, stage={}, currentFile={}",
                    taskId, status, progress, total, stage, currentFile);
                if (statusCallback != null) {
                    statusCallback.accept(status, stage, progress, total, currentFile);
                }
                
                // 更新进度
                if (progress > lastProgress && progressCallback != null) {
                    progressCallback.accept(progress);
                    lastProgress = progress;
                }
                
                // 检查状态
                if ("completed".equals(status)) {
                    logger.info("推理任务完成: taskId={}", taskId);
                    return;
                } else if ("failed".equals(status)) {
                    String errorMsg = statusNode.path("error_message").asText("未知错误");
                    logger.error("推理任务失败: taskId={}, error={}", taskId, errorMsg);
                    if (errorLogCallback != null) {
                        errorLogCallback.accept(List.of(errorMsg));
                    }
                    throw new RuntimeException("推理任务失败: " + errorMsg);
                }
                
                // 等待后继续轮询
                Thread.sleep(POLL_INTERVAL_MS);
                
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException("推理任务被中断", e);
            } catch (Exception e) {
                if (e instanceof RuntimeException) {
                    throw (RuntimeException) e;
                }
                logger.warn("查询推理状态失败，将重试: taskId={}, error={}", taskId, e.getMessage());
                try {
                    Thread.sleep(POLL_INTERVAL_MS);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new RuntimeException("推理任务被中断", ie);
                }
            }
        }
    }

    /**
     * 获取并解析推理结果
     */
    private Map<String, String> fetchAndParseResults(String taskId, List<String> expectedPaths) {
        String resultUrl = inferenceServiceUrl + "/inference/" + taskId + "/result";
        
        try {
            ResponseEntity<String> response = restTemplate.getForEntity(resultUrl, String.class);
            
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("获取推理结果失败: " + response.getStatusCode());
            }
            
            JsonNode rootNode = objectMapper.readTree(response.getBody());
            return parseInferenceResults(rootNode, expectedPaths, taskId);
            
        } catch (Exception e) {
            logger.error("获取推理结果失败: taskId={}", taskId, e);
            throw new RuntimeException("获取推理结果失败", e);
        }
    }

    /**
     * 解析推理结果
     */
    private Map<String, String> parseInferenceResults(JsonNode rootNode, List<String> expectedPaths, String taskId) {
        Map<String, String> resultMap = new HashMap<>();
        
        try {
            JsonNode resultsArray = rootNode.path("results");
            
            if (resultsArray.isArray()) {
                for (JsonNode item : resultsArray) {
                    String imagePath = item.path("image_path").asText();
                    // 从完整路径中提取相对路径进行匹配
                    String filename = Paths.get(imagePath).getFileName().toString();
                    
                    String matchedRelativePath = expectedPaths.stream()
                        .filter(p -> p.endsWith(filename))
                        .findFirst()
                        .orElse(null);
                        
                    if (matchedRelativePath != null) {
                        // 转换格式适配 AIVision 前端
                        String transformedJson = transformToAIVisionFormat(item, matchedRelativePath, taskId);
                        resultMap.put(matchedRelativePath, transformedJson);
                    }
                }
            }
        } catch (Exception e) {
            logger.error("解析推理结果失败: taskId={}", taskId, e);
        }
        
        // 对于没返回结果的文件，填充空结果防止前端报错
        for (String path : expectedPaths) {
            if (!resultMap.containsKey(path)) {
                resultMap.put(path, createEmptyResult(path));
            }
        }
        
        return resultMap;
    }

    /**
     * 转换为 AIVision 前端所需格式
     */
    private String transformToAIVisionFormat(JsonNode pythonResult, String relativePath, String taskId) {
        try {
            Map<String, Object> finalResult = new HashMap<>();
            Map<String, Object> metadata = new HashMap<>();
            List<Map<String, Object>> defectResults = new ArrayList<>();
            
            metadata.put("image_path", relativePath);
            metadata.put("width", pythonResult.path("width").asInt(1920));
            metadata.put("height", pythonResult.path("height").asInt(1080));
            
            int totalDefects = 0;
            JsonNode rois = pythonResult.path("rois");
            if (rois.isArray()) {
                for (JsonNode roi : rois) {
                    // 兼容两种模式：defects (seg模式) 或 detections (det模式)
                    JsonNode defects = roi.has("defects") ? roi.path("defects") : roi.path("detections");
                    
                    if (defects.isArray()) {
                        for (JsonNode defect : defects) {
                            totalDefects++;
                            Map<String, Object> defectMap = new HashMap<>();
                            String className = defect.path("class_name").asText();
                            String mappedName = mapToRadiographicStandard(className);
                            
                            defectMap.put("strName", mappedName);
                            defectMap.put("score", String.format("%.4f", defect.path("confidence").asDouble()));
                            
                            // 优先使用 polygon (vvContour)，如果没有则用 bbox 转换
                            JsonNode polygon = defect.path("polygon");
                            if (polygon.isArray() && polygon.size() > 0) {
                                defectMap.put("vvContour", polygon);
                            } else {
                                JsonNode bbox = defect.path("bbox");
                                if (bbox.isArray() && bbox.size() == 4) {
                                    defectMap.put("vvContour", bboxToContour(bbox));
                                }
                            }
                            
                            defectResults.add(defectMap);
                        }
                    }
                }
            }
            
            metadata.put("total_defects", String.valueOf(totalDefects));
            metadata.put("suggested_quality_level", totalDefects > 0 ? "III" : "I");
            
            // 提取矫正信息（如果 Python 结果包含 correction 字段）
            JsonNode correction = pythonResult.path("correction");
            if (!correction.isMissingNode() && correction.isObject()) {
                metadata.put("correction_rotation", correction.path("rotation").asInt(0));
                metadata.put("correction_flip", correction.path("flip").asBoolean(false));
            } else {
                metadata.put("correction_rotation", 0);
                metadata.put("correction_flip", false);
            }

            // 提取焊缝位置检测结果（B 路径，由 WeldSeamLocator 生成）
            JsonNode weldLocation = pythonResult.path("weld_location");
            if (weldLocation.isArray() && weldLocation.size() > 0) {
                metadata.put("weld_location", weldLocation);
            }

            // 提取缺陷位置检测2结果（D 路径，由 WeldDefectPositionDetector 生成）
            // positioning_type=0: center_mark 十字架; positioning_type=1: 字母/数字边缘标记（B/C 等）
            // 保留完整的 defect_position 对象（含 origin_text、detections），供前端使用
            JsonNode defectPos = pythonResult.path("defect_position");
            if (!defectPos.isMissingNode() && !defectPos.isNull()) {
                boolean detected = defectPos.path("detected").asBoolean(false);
                if (detected) {
                    metadata.put("defect_position", defectPos);
                }
            }

            // 提取OCR结果（由合并后的推理流水线生成，OCR已集成到Vision AI中）
            JsonNode ocrData = pythonResult.path("ocr");
            if (!ocrData.isMissingNode() && !ocrData.isNull()) {
                metadata.put("ocr", ocrData);
                // 同时保留在顶层，供 TaskProcessService 和前端直接读取
                finalResult.put("ocr", ocrData);
            }

            // 提取灰度密度值（底片黑度，由推理流水线计算得出）
            JsonNode grayscaleDensityNode = pythonResult.path("grayscale_density");
            if (!grayscaleDensityNode.isMissingNode() && !grayscaleDensityNode.isNull()) {
                String grayscaleDensity = grayscaleDensityNode.asText(null);
                if (grayscaleDensity != null && !grayscaleDensity.isBlank()) {
                    metadata.put("grayscale_density", grayscaleDensity);
                }
            }
            JsonNode grayscaleDensityRegions = pythonResult.path("grayscale_density_regions");
            if (grayscaleDensityRegions.isArray() && grayscaleDensityRegions.size() > 0) {
                metadata.put("grayscale_density_regions", grayscaleDensityRegions);
            }

            finalResult.put("metadata", metadata);
            finalResult.put("results", defectResults);
            
            return objectMapper.writeValueAsString(finalResult);
            
        } catch (Exception e) {
            logger.error("格式转换失败", e);
            return createEmptyResult(relativePath);
        }
    }
    
    private List<List<Double>> bboxToContour(JsonNode bbox) {
        double x1 = bbox.get(0).asDouble();
        double y1 = bbox.get(1).asDouble();
        double x2 = bbox.get(2).asDouble();
        double y2 = bbox.get(3).asDouble();
        
        List<List<Double>> contour = new ArrayList<>();
        contour.add(List.of(x1, y1));
        contour.add(List.of(x2, y1));
        contour.add(List.of(x2, y2));
        contour.add(List.of(x1, y2));
        return contour;
    }

    private String createEmptyResult(String path) {
        return String.format("{\"metadata\": {\"image_path\": \"%s\", \"total_defects\": \"0\", \"suggested_quality_level\": \"I\"}, \"results\": []}", path);
    }

    /**
     * 健康检查 - 视觉AI服务
     */
    public boolean checkVisionAiHealth() {
        try {
            String url = inferenceServiceUrl + "/health";
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            return response.getStatusCode().is2xxSuccessful();
        } catch (Exception e) {
            logger.warn("AI 推理服务健康检查失败: {}", e.getMessage());
            return false;
        }
    }
    
    /**
     * 刷新类别名称缓存（可由外部调用）
     */
    public void refreshClassNamesCache() {
        cachedClassNames = null;
        getClassNames();
    }
    
    private String mapToRadiographicStandard(String originalType) {
        switch (originalType.toLowerCase()) {
            case "crack": 
            case "a_crack": return "裂纹";
            case "porosity": 
            case "e_round_defect": return "气孔";
            case "inclusion": 
            case "d_linear_defect": return "夹渣";
            case "lack_of_fusion": 
            case "b_unfused": return "未熔合";
            case "undercut": 
            case "f_undercut": return "咬边";
            case "slag_inclusion": return "夹渣";
            case "incomplete_penetration": 
            case "c_incomplete_penetration": return "未焊透";
            case "concave": 
            case "g_concave": return "凹坑";
            case "tungsten_inclusion": return "夹钨";
            case "normal": return "normal";
            default: return originalType;
        }
    }
    
    // ================== Deprecated calls for single file if needed ==================
    public String callVisionAi(String relativeStoredPath, String taskId) {
         Map<String, String> res = callBatchVisionAi(List.of(relativeStoredPath), taskId, null, null);
         return res.get(relativeStoredPath);
    }

    // ================== OCR 服务调用 ==================
    
    /**
     * 批量调用 OCR 服务，支持进度回调
     * @param relativeStoredPaths 一批文件的逻辑/相对路径列表
     * @param taskId 任务ID (使用不同的任务ID前缀以区分)
     * @param progressCallback 进度回调函数，参数为已完成数量
     * @param errorLogCallback 错误日志回调函数
     * @return Map (relativePath -> ocrResultJson)
     */
    public Map<String, String> callBatchOcrAi(List<String> relativeStoredPaths, String taskId, 
                                              Consumer<Integer> progressCallback, 
                                              Consumer<List<String>> errorLogCallback) {
        if (relativeStoredPaths == null || relativeStoredPaths.isEmpty()) {
            return new HashMap<>();
        }

        logger.info("批量调用 OCR AI 服务 (HTTP): count={}, taskId={}", relativeStoredPaths.size(), taskId);
        
        try {
            // 1. 提交 OCR 任务
            submitOcrTask(taskId, relativeStoredPaths);
            
            // 2. 轮询等待完成
            waitForOcrCompletion(taskId, relativeStoredPaths.size(), progressCallback, errorLogCallback);
            
            // 3. 获取并解析结果
            return fetchOcrResults(taskId, relativeStoredPaths);
            
        } catch (Exception e) {
            logger.error("调用 OCR 服务失败: taskId={}", taskId, e);
            if (errorLogCallback != null) {
                errorLogCallback.accept(List.of("OCR 服务调用失败: " + e.getMessage()));
            }
            // OCR 失败不抛异常，返回空结果
            Map<String, String> emptyResults = new HashMap<>();
            for (String path : relativeStoredPaths) {
                emptyResults.put(path, createEmptyOcrResult(path));
            }
            return emptyResults;
        }
    }

    /**
     * 提交 OCR 任务到 Python 服务
     */
    private void submitOcrTask(String taskId, List<String> filePaths) {
        String url = ocrInferenceServiceUrl + "/inference/submit";
        
        Map<String, Object> request = new HashMap<>();
        request.put("task_id", taskId);
        request.put("file_paths", filePaths);
        request.put("max_size", 1920);
        request.put("save_annotations", true);
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);
        
        logger.info("提交 OCR 任务: url={}, taskId={}, fileCount={}", url, taskId, filePaths.size());
        
        try {
            ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
            
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("提交 OCR 任务失败: " + response.getStatusCode());
            }
            
            logger.info("OCR 任务已提交: taskId={}", taskId);
            
        } catch (Exception e) {
            logger.error("提交 OCR 任务失败: taskId={}", taskId, e);
            throw new RuntimeException("提交 OCR 任务失败: " + e.getMessage(), e);
        }
    }

    /**
     * 轮询等待 OCR 任务完成
     */
    private void waitForOcrCompletion(String taskId, int totalFiles, 
                                      Consumer<Integer> progressCallback, 
                                      Consumer<List<String>> errorLogCallback) {
        String statusUrl = ocrInferenceServiceUrl + "/inference/" + taskId + "/status";
        long startTime = System.currentTimeMillis();
        long timeoutMs = timeoutMinutes * 60 * 1000L;
        
        int lastProgress = 0;
        
        while (true) {
            if (System.currentTimeMillis() - startTime > timeoutMs) {
                throw new RuntimeException("OCR 任务超时: " + timeoutMinutes + "分钟");
            }
            
            try {
                ResponseEntity<String> response = restTemplate.getForEntity(statusUrl, String.class);
                
                if (!response.getStatusCode().is2xxSuccessful()) {
                    Thread.sleep(POLL_INTERVAL_MS);
                    continue;
                }
                
                JsonNode statusNode = objectMapper.readTree(response.getBody());
                String status = statusNode.path("status").asText();
                int progress = statusNode.path("progress").asInt();
                
                if (progress > lastProgress && progressCallback != null) {
                    progressCallback.accept(progress);
                    lastProgress = progress;
                }
                
                if ("completed".equals(status)) {
                    logger.info("OCR 任务完成: taskId={}", taskId);
                    return;
                } else if ("failed".equals(status)) {
                    String errorMsg = statusNode.path("error_message").asText("未知错误");
                    logger.error("OCR 任务失败: taskId={}, error={}", taskId, errorMsg);
                    if (errorLogCallback != null) {
                        errorLogCallback.accept(List.of(errorMsg));
                    }
                    throw new RuntimeException("OCR 任务失败: " + errorMsg);
                }
                
                Thread.sleep(POLL_INTERVAL_MS);
                
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException("OCR 任务被中断", e);
            } catch (Exception e) {
                if (e instanceof RuntimeException) {
                    throw (RuntimeException) e;
                }
                logger.warn("查询 OCR 状态失败，将重试: taskId={}, error={}", taskId, e.getMessage());
                try {
                    Thread.sleep(POLL_INTERVAL_MS);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new RuntimeException("OCR 任务被中断", ie);
                }
            }
        }
    }

    /**
     * 获取 OCR 结果
     */
    private Map<String, String> fetchOcrResults(String taskId, List<String> expectedPaths) {
        String resultUrl = ocrInferenceServiceUrl + "/inference/" + taskId + "/result";
        Map<String, String> resultMap = new HashMap<>();
        
        try {
            ResponseEntity<String> response = restTemplate.getForEntity(resultUrl, String.class);
            
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("获取 OCR 结果失败: " + response.getStatusCode());
            }
            
            JsonNode rootNode = objectMapper.readTree(response.getBody());
            JsonNode resultsArray = rootNode.path("results");
            
            if (resultsArray.isArray()) {
                for (JsonNode item : resultsArray) {
                    String imagePath = item.path("image_path").asText();
                    String filename = Paths.get(imagePath).getFileName().toString();
                    
                    String matchedPath = expectedPaths.stream()
                        .filter(p -> p.endsWith(filename))
                        .findFirst()
                        .orElse(null);
                        
                    if (matchedPath != null) {
                        resultMap.put(matchedPath, objectMapper.writeValueAsString(item));
                    }
                }
            }
            
        } catch (Exception e) {
            logger.error("获取 OCR 结果失败: taskId={}", taskId, e);
        }
        
        // 填充空结果
        for (String path : expectedPaths) {
            if (!resultMap.containsKey(path)) {
                resultMap.put(path, createEmptyOcrResult(path));
            }
        }
        
        return resultMap;
    }

    private String createEmptyOcrResult(String path) {
        return String.format("{\"image_path\": \"%s\", \"recognized_texts\": [], \"field_statistics\": {}, \"error\": null}", path);
    }

    /**
     * 同步识别单张图片区域（base64输入），用于前端实时OCR框选功能
     * @param base64Image base64编码的图片
     * @param taskId      可选，任务ID，用于调试图片文件命名
     * @param fieldName   可选，字段名称（如 weldId、filmNumber），用于调试图片文件命名
     */
    public Map<String, Object> recognizeImageRegion(String base64Image, String taskId, String fieldName) {
        String url = ocrInferenceServiceUrl + "/inference/recognize";

        Map<String, Object> body = new HashMap<>();
        body.put("image_base64", base64Image);
        if (taskId != null && !taskId.isBlank()) {
            body.put("task_id", taskId);
        }
        if (fieldName != null && !fieldName.isBlank()) {
            body.put("field_name", fieldName);
        }

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);

        logger.info("调用OCR区域识别接口: taskId={}, fieldName={}", taskId, fieldName);
        try {
            ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("OCR识别失败: " + response.getStatusCode());
            }
            return objectMapper.readValue(response.getBody(), Map.class);
        } catch (Exception e) {
            logger.error("OCR区域识别失败: {}", e.getMessage());
            throw new RuntimeException("OCR识别失败: " + e.getMessage(), e);
        }
    }

    /**
     * 兼容旧签名：无 taskId/fieldName 的调用
     */
    public Map<String, Object> recognizeImageRegion(String base64Image) {
        return recognizeImageRegion(base64Image, null, null);
    }

    /**
     * 同步计算单张图片区域的归一化信噪比（base64输入），用于前端实时框选功能
     * @param base64Image base64编码的图片
     * @param taskId      可选，任务ID，用于调试图片文件命名
     * @param fieldName   可选，字段名称，用于调试图片文件命名
     * @param srBUm       可选，基本空间分辨力，单位微米
     */
    public Map<String, Object> computeImageRegionSnr(String base64Image, String taskId, String fieldName, Double srBUm) {
        String url = ocrInferenceServiceUrl + "/inference/region-snr";

        Map<String, Object> body = new HashMap<>();
        body.put("image_base64", base64Image);
        if (taskId != null && !taskId.isBlank()) {
            body.put("task_id", taskId);
        }
        if (fieldName != null && !fieldName.isBlank()) {
            body.put("field_name", fieldName);
        }
        if (srBUm != null && Double.isFinite(srBUm)) {
            body.put("sr_b_um", srBUm);
        }

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);

        logger.info("调用区域归一化信噪比接口: taskId={}, fieldName={}, srBUm={}", taskId, fieldName, srBUm);
        try {
            ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("区域归一化信噪比计算失败: " + response.getStatusCode());
            }
            return objectMapper.readValue(response.getBody(), Map.class);
        } catch (Exception e) {
            logger.error("区域归一化信噪比计算失败: {}", e.getMessage());
            throw new RuntimeException("区域归一化信噪比计算失败: " + e.getMessage(), e);
        }
    }

    /**
     * 兼容旧签名：无 taskId/fieldName 的调用
     */
    public Map<String, Object> computeImageRegionSnr(String base64Image, String taskId, String fieldName) {
        return computeImageRegionSnr(base64Image, taskId, fieldName, null);
    }

    /**
     * 兼容旧签名：无 taskId/fieldName 的调用
     */
    public Map<String, Object> computeImageRegionSnr(String base64Image) {
        return computeImageRegionSnr(base64Image, null, null, null);
    }

    /**
     * 同步分析双丝像质计 strip 图像（base64输入），用于前端双丝分辨率手动选择
     * @param base64Image base64编码的图片
     * @param taskId      可选，任务ID，用于调试图片文件命名
     * @param fieldName   可选，字段名称，用于调试图片文件命名
     */
    public Map<String, Object> computeDoubleWire(String base64Image, String taskId, String fieldName) {
        String url = ocrInferenceServiceUrl + "/inference/double-wire";

        Map<String, Object> body = new HashMap<>();
        body.put("image_base64", base64Image);
        if (taskId != null && !taskId.isBlank()) {
            body.put("task_id", taskId);
        }
        if (fieldName != null && !fieldName.isBlank()) {
            body.put("field_name", fieldName);
        }

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);

        logger.info("调用双丝分辨率分析接口: taskId={}, fieldName={}", taskId, fieldName);
        try {
            ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("双丝分辨率分析失败: " + response.getStatusCode());
            }
            return objectMapper.readValue(response.getBody(), Map.class);
        } catch (Exception e) {
            logger.error("双丝分辨率分析失败: {}", e.getMessage());
            throw new RuntimeException("双丝分辨率分析失败: " + e.getMessage(), e);
        }
    }

    /**
     * 兼容旧签名：无 taskId/fieldName 的调用
     */
    public Map<String, Object> computeDoubleWire(String base64Image) {
        return computeDoubleWire(base64Image, null, null);
    }

    /**
     * 健康检查 - OCR AI 服务
     */
    public boolean checkOcrAiHealth() {
        try {
            String url = ocrInferenceServiceUrl + "/health";
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            return response.getStatusCode().is2xxSuccessful();
        } catch (Exception e) {
            logger.warn("OCR 推理服务健康检查失败: {}", e.getMessage());
            return false;
        }
    }
}
