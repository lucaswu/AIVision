package com.aivision.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class AiServiceClient {
    
    private static final Logger logger = LoggerFactory.getLogger(AiServiceClient.class);
    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    @Value("${ai-services.vision-ai.url}")
    private String visionAiUrl;
    
    @Value("${storage.external-base-dir:/data/files}")
    private String externalBaseDir;

    /**
     * 批量调用视觉AI检测服务
     * @param relativeStoredPaths 一批文件的逻辑/相对路径列表
     * @param taskId 任务ID
     * @return Map (relativePath -> visionResultJson)
     */
    public Map<String, String> callBatchVisionAi(List<String> relativeStoredPaths, String taskId) {
        logger.info("批量调用 Vision AI 服务: count={}, taskId={}", relativeStoredPaths.size(), taskId);
        
        Map<String, String> results = new HashMap<>();
        
        // 模拟批量算法处理 (实际生产中这里是一次 HTTP POST 传列表)
        for (String path : relativeStoredPaths) {
            String mockResult = "{" +
                "\"metadata\": {" +
                    "\"image_path\": \"" + path + "\"," +
                    "\"total_defects\": \"2\"," +
                    "\"suggested_quality_level\": \"II\"" +
                "}," +
                "\"results\": [" +
                    "{" +
                        "\"strName\": \"porosity\"," +
                        "\"score\": 0.95," +
                        "\"vvContour\": [[100, 100], [120, 100], [120, 120], [100, 120]]" +
                    "}," +
                    "{" +
                        "\"strName\": \"crack\"," +
                        "\"score\": 0.88," +
                        "\"vvContour\": [[200, 200], [250, 210], [240, 220]]" +
                    "}" +
                "]" +
            "}";
            results.put(path, postProcessVisionResult(mockResult, taskId));
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
    
    private String mapToRadiographicStandard(String originalType) {
        switch (originalType.toLowerCase()) {
            case "crack": return "A_crack";
            case "porosity": return "E_round_defect";
            case "inclusion": return "D_linear_defect";
            case "lack_of_fusion": return "B_unfused";
            case "undercut": return "F_undercut";
            case "slag_inclusion": return "D_linear_defect";
            case "incomplete_penetration": return "C_incomplete_penetration";
            case "concave": return "G_concave";
            case "normal": return "normal";
            default: return "H_other";
        }
    }
    
    // ================== Deprecated calls for single file if needed ==================
    public String callVisionAi(String relativeStoredPath, String taskId) {
         Map<String, String> res = callBatchVisionAi(List.of(relativeStoredPath), taskId);
         return res.get(relativeStoredPath);
    }
}
