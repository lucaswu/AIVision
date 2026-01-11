package com.aivision.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.function.Consumer;

@Service
public class AiServiceClient {
    
    private static final Logger logger = LoggerFactory.getLogger(AiServiceClient.class);
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);

    @Value("${ai-services.vision-ai.python-path:python3}")
    private String pythonPath;


    @Value("${ai-services.vision-ai.script-path:/app/model/run_inference_pipeline.py}")
    private String scriptPath;

    @Value("${ai-services.vision-ai.roi-weights}")
    private String roiWeights;

    @Value("${ai-services.vision-ai.primary-weights}")
    private String primaryWeights;

    @Value("${ai-services.vision-ai.inference-mode:det}")
    private String inferenceMode;
    
    @Value("${ai-services.vision-ai.engine:rfdet}")
    private String engineType;

    @Value("${ai-services.vision-ai.device:cpu}")
    private String device;
    
    @Value("${storage.external-base-dir:/data/files}")
    private String externalBaseDir;
    
    // 用于本地存储的基础路径，确保可以找到文件
    @Value("${storage.local.base-dir:/app/data/files}")
    private String localBaseDir;
    
    @Value("${storage.local.result-dir:/app/data/results}")
    private String localResultDir;

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
        if (relativeStoredPaths == null || relativeStoredPaths.isEmpty()) {
            return new HashMap<>();
        }

        logger.info("批量调用 Vision AI 服务 (Python): count={}, taskId={}", relativeStoredPaths.size(), taskId);
        
        // 1. 确定输入目录
        String firstFileRelativePath = relativeStoredPaths.get(0);
        // 如果以 / 开头，去除它以确保 Paths.get 正确拼接到 localBaseDir
        if (firstFileRelativePath.startsWith("/") || firstFileRelativePath.startsWith("\\")) {
            firstFileRelativePath = firstFileRelativePath.substring(1);
        }
        Path inputDir = Paths.get(localBaseDir, firstFileRelativePath).getParent();
        
        if (inputDir == null || !Files.exists(inputDir)) {
            logger.error("输入目录不存在: {}", inputDir);
            throw new RuntimeException("输入目录不存在: " + inputDir);
        }

        // 2. 准备输出目录
        Path outputDir = Paths.get(localResultDir, taskId);
        try {
            Files.createDirectories(outputDir);
        } catch (Exception e) {
            logger.error("无法创建输出目录: {}", outputDir, e);
            throw new RuntimeException("无法创建输出目录", e);
        }
        
        // 3. 构建 Python 命令
        List<String> command = new ArrayList<>();
        command.add(pythonPath);
        command.add(scriptPath);
        command.add("--image-dir");
        command.add(inputDir.toString());
        command.add("--output-dir");
        command.add(outputDir.toString());
        command.add("--roi-weights");
        command.add(roiWeights);
        command.add("--primary-weights");
        command.add(primaryWeights);
        command.add("--mode");
        command.add(inferenceMode);
        
        // 指定引擎 (支持 yolo, rfdet)
        command.add("--engine");
        command.add(engineType);
        
        command.add("--device");
        command.add(device);
        command.add("--results-json");
        command.add("inference_results.json");

        logger.info("==================================================");
        logger.info("执行 Python 命令: {}", String.join(" ", command));
        logger.info("==================================================");

        ConcurrentLinkedQueue<String> errorLogs = new ConcurrentLinkedQueue<>();
        Path progressFile = outputDir.resolve("progress.json");

        try {
            ProcessBuilder pb = new ProcessBuilder(command);
            pb.directory(new File(scriptPath).getParentFile());
            pb.redirectErrorStream(true);

            Process process = pb.start();
            
            // 启动进度监控线程
            Thread monitorThread = new Thread(() -> {
                while (process.isAlive()) {
                    try {
                        if (Files.exists(progressFile)) {
                            try {
                                JsonNode progressNode = objectMapper.readTree(progressFile.toFile());
                                int current = progressNode.path("current").asInt();
                                if (progressCallback != null) {
                                    progressCallback.accept(current);
                                }
                            } catch (Exception e) {
                                // Ignore read errors (file might be partial)
                            }
                        }
                        Thread.sleep(1000);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            });
            monitorThread.start();
            
            // 读取日志输出并保留最后 200 行
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    logger.debug("[Python]: {}", line);
                    errorLogs.add(line);
                    if (errorLogs.size() > 200) {
                        errorLogs.poll();
                    }
                }
            }

            // 等待进程结束
            boolean finished = process.waitFor(30, TimeUnit.MINUTES);
            if (!finished) {
                process.destroyForcibly();
                throw new RuntimeException("Python 推理进程超时 (30分钟)");
            }

            // 等待监控线程结束
            monitorThread.join(2000);

            int exitCode = process.exitValue();
            if (exitCode != 0) {
                logger.error("Python 进程异常退出, exitCode={}", exitCode);
                
                logger.error("----- Python 错误日志 (最后 {} 行) -----", errorLogs.size());
                for (String log : errorLogs) {
                    logger.error(log);
                }
                logger.error("----------------------------------------");
                
                List<String> logs = new ArrayList<>(errorLogs);
                if (errorLogCallback != null) {
                    errorLogCallback.accept(logs);
                }
                throw new RuntimeException("Python 推理失败，退出码: " + exitCode);
            }

            // 4. 解析结果 JSON
            Path resultJsonPath = outputDir.resolve("inference_results.json");
            if (!Files.exists(resultJsonPath)) {
                logger.error("未找到结果文件: {}", resultJsonPath);
                throw new RuntimeException("推理完成但未生成结果文件");
            }

            return parseInferenceResults(resultJsonPath, relativeStoredPaths, taskId);

        } catch (Exception e) {
            logger.error("调用 Python 推理失败: taskId={}", taskId, e);
            throw new RuntimeException("调用 Python 推理失败", e);
        } finally {
            // 清理临时文件
            try {
                Files.deleteIfExists(progressFile);
            } catch (Exception e) {
                logger.warn("清理进度文件失败: {}", progressFile);
            }
        }
    }
    
    private Map<String, String> parseInferenceResults(Path jsonPath, List<String> expectedPaths, String taskId) {
        Map<String, String> resultMap = new HashMap<>();
        try {
            JsonNode rootNode = objectMapper.readTree(jsonPath.toFile());
            JsonNode resultsArray = rootNode.path("results");
            
            if (resultsArray.isArray()) {
                for (JsonNode item : resultsArray) {
                    String fullPath = item.path("image_path").asText();
                    // Python 返回的是绝对路径，我们需要匹配回 relativeStoredPaths
                    // 简单的匹配策略：看文件名是否一致
                    String filename = Paths.get(fullPath).getFileName().toString();
                    
                    String matchedRelativePath = expectedPaths.stream()
                        .filter(p -> p.endsWith(filename)) // 假设文件名唯一
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
            logger.error("解析结果 JSON 失败: {}", jsonPath, e);
        }
        
        // 对于没返回结果的文件，填充空结果防止前端报错
        for (String path : expectedPaths) {
            if (!resultMap.containsKey(path)) {
                resultMap.put(path, createEmptyResult(path));
            }
        }
        
        return resultMap;
    }

    private String transformToAIVisionFormat(JsonNode pythonResult, String relativePath, String taskId) {
        try {
            // Python 格式: { "image_path": "...", "rois": [ { "defects": [ { "class_name": "crack", "bbox": [...], "polygon": [...] } ] } ] }
            // AIVision 格式: { "metadata": { ... }, "results": [ { "strName": "裂纹", "vvContour": [...] } ] }
            
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
     * 健康检查 - 视觉AI服务 (由于是本地调用，总是返回 true，或者检查文件是否存在)
     */
    public boolean checkVisionAiHealth() {
        return new File(scriptPath).exists();
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
}

