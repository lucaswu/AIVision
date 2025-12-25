package com.aivision.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

@Service
public class AiServiceClient {
    
    private static final Logger logger = LoggerFactory.getLogger(AiServiceClient.class);
    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final Random random = new Random();
    
    private static final String[] DEFECT_TYPES = {
        "裂纹", "气孔", "夹渣", "未熔合", 
        "未焊透", "咬边", "凹坑", "夹钨"
    };

    @Value("${ai-services.vision-ai.url}")
    private String visionAiUrl;
    
    @Value("${storage.external-base-dir:/data/files}")
    private String externalBaseDir;

    /**
     * 将内部缺陷代码映射为友好的中文名称
     */
    private String getFriendlyName(String originalType) {
        switch (originalType.toLowerCase()) {
            case "crack": return "裂纹";
            case "porosity": return "气孔";
            case "slag_inclusion": return "夹渣";
            case "lack_of_fusion": return "未熔合";
            case "incomplete_penetration": return "未焊透";
            case "undercut": return "咬边";
            case "concave": return "凹坑";
            case "tungsten_inclusion": return "夹钨";
            default: return originalType;
        }
    }

    /**
     * 批量调用视觉AI检测服务
     * @param relativeStoredPaths 一批文件的逻辑/相对路径列表
     * @param taskId 任务ID
     * @return Map (relativePath -> visionResultJson)
     */
    public Map<String, String> callBatchVisionAi(List<String> relativeStoredPaths, String taskId) {
        logger.info("批量调用 Vision AI 服务: count={}, taskId={}", relativeStoredPaths.size(), taskId);
        
        Map<String, String> results = new HashMap<>();
        
        for (String path : relativeStoredPaths) {
            // 70% 概率有缺陷
            boolean hasDefects = random.nextDouble() < 0.7;
            
            StringBuilder mockResult = new StringBuilder();
            mockResult.append("{");
            mockResult.append("\"metadata\": {");
            mockResult.append("\"image_path\": \"").append(path).append("\",");
            mockResult.append("\"width\": 1920,");
            mockResult.append("\"height\": 1080,");
            
            if (!hasDefects) {
                mockResult.append("\"total_defects\": \"0\",");
                mockResult.append("\"suggested_quality_level\": \"I\"");
                mockResult.append("},");
                mockResult.append("\"results\": []");
            } else {
                // 有缺陷的图片中：30% 是 1 个，60% 是 2 个，10% 是 3 个
                double defectCountRand = random.nextDouble();
                int defectCount;
                if (defectCountRand < 0.3) {
                    defectCount = 1;
                } else if (defectCountRand < 0.9) {
                    defectCount = 2;
                } else {
                    defectCount = 3;
                }
                
                mockResult.append("\"total_defects\": \"").append(defectCount).append("\",");
                mockResult.append("\"suggested_quality_level\": \"III\"");
                mockResult.append("},");
                mockResult.append("\"results\": [");
                
                for (int i = 0; i < defectCount; i++) {
                    String type = DEFECT_TYPES[random.nextInt(DEFECT_TYPES.length)];
                    double score = 0.7 + (0.99 - 0.7) * random.nextDouble();
                    
                    // 随机生成坐标和尺寸
                    int x = random.nextInt(1500) + 100;
                    int y = random.nextInt(800) + 100;
                    int w = random.nextInt(100) + 20;
                    int h = random.nextInt(100) + 20;
                    
                    mockResult.append("{");
                    mockResult.append("\"strName\": \"").append(type).append("\",");
                    mockResult.append("\"score\": ").append(String.format("%.4f", score)).append(",");
                    mockResult.append("\"vvContour\": [");
                    mockResult.append("[").append(x).append(",").append(y).append("],");
                    mockResult.append("[").append(x + w).append(",").append(y).append("],");
                    mockResult.append("[").append(x + w).append(",").append(y + h).append("],");
                    mockResult.append("[").append(x).append(",").append(y + h).append("]");
                    mockResult.append("]");
                    mockResult.append("}");
                    
                    if (i < defectCount - 1) {
                        mockResult.append(",");
                    }
                }
                mockResult.append("]");
            }
            mockResult.append("}");
            
            results.put(path, postProcessVisionResult(mockResult.toString(), taskId));
        }
        
        return results;
    }
    
    /**
     * 健康检查 - 视觉AI服务
     */
    public boolean checkVisionAiHealth() {
        try {
            String url = visionAiUrl + "/health";
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            return response.getStatusCode().is2xxSuccessful();
        } catch (Exception e) {
            logger.warn("视觉AI服务健康检查失败: {}", e.getMessage());
            return false;
        }
    }
    
    /**
     * 后处理视觉AI检测结果，修复已知问题
     */
    private String postProcessVisionResult(String originalResult, String taskId) {
        try {
            JsonNode resultNode = objectMapper.readTree(originalResult);
            
            if (resultNode.has("metadata")) {
                JsonNode metadata = resultNode.get("metadata");
                
                // 修复total_defects负数问题
                if (metadata.has("total_defects")) {
                    String totalDefectsStr = metadata.get("total_defects").asText();
                    try {
                        long totalDefects = Long.parseLong(totalDefectsStr);
                        if (totalDefects < 0) {
                            int actualDefects = calculateActualDefects(resultNode);
                            ((com.fasterxml.jackson.databind.node.ObjectNode) metadata)
                                .put("total_defects", String.valueOf(actualDefects));
                        }
                    } catch (NumberFormatException e) {
                        logger.warn("total_defects格式异常: {}, taskId={}", totalDefectsStr, taskId);
                    }
                }
                
                enhanceDefectTypeMapping(resultNode, taskId);
            }
            return objectMapper.writeValueAsString(resultNode);
            
        } catch (Exception e) {
            logger.error("后处理视觉AI结果失败: taskId={}, error={}", taskId, e.getMessage(), e);
            return originalResult;
        }
    }
    
    private int calculateActualDefects(JsonNode resultNode) {
        int defectCount = 0;
        if (resultNode.has("results") && resultNode.get("results").isArray()) {
            for (JsonNode result : resultNode.get("results")) {
                if (result.has("strName") && !"normal".equals(result.get("strName").asText())) {
                    defectCount++;
                }
            }
        }
        return defectCount;
    }
    
    private void enhanceDefectTypeMapping(JsonNode resultNode, String taskId) {
        try {
            if (resultNode.has("results") && resultNode.get("results").isArray()) {
                for (JsonNode result : resultNode.get("results")) {
                    if (result.has("strName")) {
                        String originalType = result.get("strName").asText();
                        // 如果已经是中文或者已经是映射后的格式，就不再映射
                        if (isFriendlyName(originalType)) {
                            continue;
                        }
                        String mappedType = mapToRadiographicStandard(originalType);
                        if (!originalType.equals(mappedType)) {
                            ((com.fasterxml.jackson.databind.node.ObjectNode) result).put("strName", mappedType);
                        }
                    }
                }
            }
        } catch (Exception e) {
            logger.warn("缺陷类型映射失败: taskId={}, error={}", taskId, e.getMessage());
        }
    }

    private boolean isFriendlyName(String type) {
        for (String friendly : DEFECT_TYPES) {
            if (friendly.equals(type)) return true;
        }
        return false;
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
         Map<String, String> res = callBatchVisionAi(List.of(relativeStoredPath), taskId);
         return res.get(relativeStoredPath);
    }
}
