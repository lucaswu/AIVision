package com.aivision.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class AiServiceClient {
    
    private static final Logger logger = LoggerFactory.getLogger(AiServiceClient.class);
    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    @Value("${ai-services.vision-ai.url}")
    private String visionAiUrl;
    
    @Value("${ai-services.llm-ai.url}")
    private String llmAiUrl;
    
    @Value("${ai-services.llm-ai.model}")
    private String llmModel;

    @Value("${storage.external-base-dir:/data/files}")
    private String externalBaseDir;

    private static final Pattern CLASS_LETTER_PATTERN = Pattern.compile("^([A-H])[_-].*$");

    // ================= Radiographic report helpers =================
    private String mapToClassLetter(String originalType) {
        if (originalType == null) return "/";
        String lower = originalType.toLowerCase();
        // If already like D_linear_defect, pick the letter
        Matcher m = CLASS_LETTER_PATTERN.matcher(originalType);
        if (m.matches()) {
            return m.group(1);
        }
        switch (lower) {
            case "crack": return "A"; // 裂纹
            case "lack_of_fusion": return "B"; // 未熔合
            case "incomplete_penetration": return "C"; // 未焊透
            case "inclusion": return "D"; // 条状缺陷（夹渣等）
            case "slag_inclusion": return "D";
            case "porosity": return "E"; // 圆形缺陷
            case "undercut": return "F"; // 咬边
            case "concave": return "G"; // 内凹
            case "normal": return "/";
            default: return "H"; // 其它
        }
    }

    private static class ReportRow {
        public int index;
        public String weldNo = "/";              // 焊口编号
        public String sheetNo = "/";             // 片号
        public String filmDensity = "/";         // 底片黑度
        public String iqiSensitivity = "/";      // 像质计灵敏度
        public String defectClass = "/";         // 缺陷性质 (A-H 或 /)
        public String defectPosition = "/";      // 缺陷位置（钟点位或方位）
        public String defectSize = "/";          // 缺陷尺寸（px）
        public String qualityLevel = "/";        // 质量等级（I/II/III）
        public String remark = "/";              // 备注
    }

    private List<ReportRow> buildReportRowsFromVision(JsonNode vision) {
        List<ReportRow> rows = new ArrayList<>();
        if (vision == null || !vision.has("results") || !vision.get("results").isArray()) {
            return rows;
        }
        // read suggested quality if any
        String suggestedLevel = "/";
        if (vision.has("metadata") && vision.get("metadata").has("suggested_quality_level")) {
            suggestedLevel = vision.get("metadata").get("suggested_quality_level").asText("/");
        }
        int idx = 1;
        for (JsonNode item : vision.get("results")) {
            String name = item.has("strName") ? item.get("strName").asText() : null;
            String letter = mapToClassLetter(name);
            if ("/".equals(letter)) {
                // skip normal items
                continue;
            }
            ReportRow row = new ReportRow();
            row.index = idx++;
            row.defectClass = letter;
            row.qualityLevel = suggestedLevel;

            // compute bounding width/height from vvContour[0]
            if (item.has("vvContour") && item.get("vvContour").isArray() && item.get("vvContour").size() > 0) {
                JsonNode outer = item.get("vvContour").get(0);
                double minX = Double.POSITIVE_INFINITY, minY = Double.POSITIVE_INFINITY;
                double maxX = Double.NEGATIVE_INFINITY, maxY = Double.NEGATIVE_INFINITY;
                if (outer.isArray()) {
                    for (JsonNode pt : outer) {
                        if (pt.isArray() && pt.size() >= 2) {
                            double x = pt.get(0).asDouble();
                            double y = pt.get(1).asDouble();
                            if (x < minX) minX = x;
                            if (x > maxX) maxX = x;
                            if (y < minY) minY = y;
                            if (y > maxY) maxY = y;
                        }
                    }
                }
                if (minX != Double.POSITIVE_INFINITY && minY != Double.POSITIVE_INFINITY) {
                    int w = (int)Math.round(maxX - minX);
                    int h = (int)Math.round(maxY - minY);
                    if ("E".equals(letter)) {
                        int d = (int)Math.round((w + h) / 2.0);
                        row.defectSize = "Φ" + d + "(px)";
                    } else {
                        row.defectSize = Math.max(w, h) + "×" + Math.min(w, h) + "(px)";
                    }
                }
            }
            rows.add(row);
        }
        return rows;
    }

    private String buildRowsJsonForPrompt(List<ReportRow> rows) {
        try {
            return objectMapper.writeValueAsString(rows);
        } catch (Exception e) {
            return "[]";
        }
    }

    private String buildHtmlTable(List<ReportRow> rows) {
        StringBuilder sb = new StringBuilder();
        sb.append("<table>");
        sb.append("<tr>")
          .append("<th>序号</th>")
          .append("<th>焊口编号</th>")
          .append("<th>片号</th>")
          .append("<th>底片黑度</th>")
          .append("<th>像质计灵敏度</th>")
          .append("<th>缺陷性质</th>")
          .append("<th>缺陷位置</th>")
          .append("<th>缺陷尺寸</th>")
          .append("<th>质量等级</th>")
          .append("<th>备注</th>")
          .append("</tr>");
        for (ReportRow r : rows) {
            sb.append("<tr>")
              .append("<td>").append(r.index).append("</td>")
              .append("<td>").append(r.weldNo).append("</td>")
              .append("<td>").append(r.sheetNo).append("</td>")
              .append("<td>").append(r.filmDensity).append("</td>")
              .append("<td>").append(r.iqiSensitivity).append("</td>")
              .append("<td>").append(r.defectClass).append("</td>")
              .append("<td>").append(r.defectPosition).append("</td>")
              .append("<td>").append(r.defectSize).append("</td>")
              .append("<td>").append(r.qualityLevel).append("</td>")
              .append("<td>").append(r.remark).append("</td>")
              .append("</tr>");
        }
        sb.append("</table>");
        return sb.toString();
    }

    private String buildSummaryPrompt(String rowsJson, String suggestedLevel) {
        return String.format(
            "你是一名无损检测工程师。下面是已结构化的缺陷行(rows, JSON数组)，每个元素代表一条缺陷记录，字段含义与射线检测表格一致。\n" +
            "请基于 rows 生成不超过6行的中文'报告解读'（纯文本，无标题、无需Markdown代码块），内容包括：总缺陷数、主要缺陷性质分布、尺寸概况与质量等级结论(若提供: %s)。\n" +
            "不得输出与rows无关的信息。\n\nrows: %s\n",
            suggestedLevel == null ? "/" : suggestedLevel,
            rowsJson
        );
    }
    
    /**
     * 调用视觉AI检测服务
     * @param minioFilePath MinIO中的文件路径
     * @param taskId 任务ID
     * @return 检测结果JSON
     */
    public String callVisionAi(String relativeStoredPath, String taskId) {
        try {
            String url = visionAiUrl + "/detect_file";
            String cleanPath = buildExternalAbsolutePath(relativeStoredPath);
            
            // 构建请求体（按照vision ai服务要求的格式）
            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("task_id", taskId);                    // 必填：任务ID
            requestBody.put("file_path", cleanPath);               // 必填：本地文件绝对路径（huodian_ai 可访问）
            requestBody.put("detection_type", "defect_detection"); // 必填：检测类型
            
            // 设置请求头
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            
            HttpEntity<Map<String, Object>> request = new HttpEntity<>(requestBody, headers);
            
            logger.info("调用视觉AI服务: url={}, taskId={}, file_path={}, detectionType={}", 
                       url, taskId, cleanPath, "defect_detection");
            
            // 发送请求
            ResponseEntity<String> response = restTemplate.postForEntity(url, request, String.class);
            
            if (response.getStatusCode() == HttpStatus.OK) {
                String result = response.getBody();
                logger.info("视觉AI检测成功: taskId={}, cleanPath={}, result={}", taskId, cleanPath, result);
                
                // 后处理检测结果，修复已知问题
                String processedResult = postProcessVisionResult(result, taskId);
                logger.debug("视觉AI结果后处理完成: taskId={}, processedResult={}", taskId, processedResult);
                
                return processedResult;
            } else {
                throw new RuntimeException("视觉AI服务调用失败: " + response.getStatusCode());
            }
            
        } catch (Exception e) {
            logger.error("调用视觉AI服务失败: taskId={}, file_path(rel)={}, error={}", taskId, relativeStoredPath, e.getMessage(), e);
            throw new RuntimeException("视觉AI服务调用失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 清理MinIO路径格式
     * 移除bucket名称前缀，确保路径格式正确
     */
    private String buildExternalAbsolutePath(String relativePath) {
        if (relativePath == null || relativePath.isEmpty()) return relativePath;
        String rel = relativePath.startsWith("/") ? relativePath.substring(1) : relativePath;
        // 简单拼接，避免双分隔符
        String base = externalBaseDir;
        if (base.endsWith("/") || base.endsWith("\\")) {
            return base + rel;
        }
        return base + "/" + rel;
    }
    
    /**
     * 调用LLM AI生成报告
     * @param visionResult 视觉检测结果
     * @param fileName 文件名
     * @return LLM生成的报告
     */
    public String callLlmAi(String visionResult, String fileName) {
        try {
            String url = llmAiUrl + "/api/generate";

            // 预处理：生成表格行与HTML表格
            JsonNode vision = objectMapper.readTree(visionResult);
            List<ReportRow> rows = buildReportRowsFromVision(vision);
            String tableHtml = buildHtmlTable(rows);
            String rowsJson = buildRowsJsonForPrompt(rows);
            String suggestedLevel = "/";
            if (vision.has("metadata") && vision.get("metadata").has("suggested_quality_level")) {
                suggestedLevel = vision.get("metadata").get("suggested_quality_level").asText("/");
            }

            // 只让LLM生成简短解读（纯文本）
            String prompt = buildSummaryPrompt(rowsJson, suggestedLevel);

            // 构建请求体（Ollama API格式）
            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("model", llmModel);
            requestBody.put("prompt", prompt);
            requestBody.put("stream", false);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Map<String, Object>> request = new HttpEntity<>(requestBody, headers);

            logger.info("调用LLM AI服务: url={}, fileName={}", url, fileName);
            ResponseEntity<String> response = restTemplate.postForEntity(url, request, String.class);

            if (response.getStatusCode() == HttpStatus.OK) {
                JsonNode resp = objectMapper.readTree(response.getBody());
                String generatedText = resp.get("response").asText("");
                // 清理潜在的Markdown围栏
                generatedText = generatedText.replace("```", "").trim();
                // 拼接表格与解读
                return tableHtml + "\n" + generatedText;
            } else {
                // 即使LLM失败，也返回表格
                return tableHtml;
            }
        } catch (Exception e) {
            logger.error("调用LLM AI服务失败: fileName={}, error={}", fileName, e.getMessage(), e);
            // 失败退化为仅表格或原始文本
            try {
                JsonNode vision = objectMapper.readTree(visionResult);
                List<ReportRow> rows = buildReportRowsFromVision(vision);
                return buildHtmlTable(rows);
            } catch (Exception ignore) {
                return "生成报告失败";
            }
        }
    }
    
    /**
     * 构建LLM提示词
     */
    private String buildLlmPrompt(String visionResult, String fileName) {
        // Deprecated by table+summary flow, kept for compatibility if needed.
        String rowsJson = "[]";
        String suggestedLevel = "/";
        try {
            JsonNode vision = objectMapper.readTree(visionResult);
            List<ReportRow> rows = buildReportRowsFromVision(vision);
            rowsJson = buildRowsJsonForPrompt(rows);
            if (vision.has("metadata") && vision.get("metadata").has("suggested_quality_level")) {
                suggestedLevel = vision.get("metadata").get("suggested_quality_level").asText("/");
            }
        } catch (Exception ignore) { }
        return String.format(
            "你是一名严格遵循GB/T 3323 射线检测报告规范的无损检测工程师。\n文件名: %s\n建议质量等级: %s\nrows(JSON): %s\n",
            fileName, suggestedLevel, rowsJson
        );
    }
    
    /**
     * 健康检查 - 视觉AI服务
     */
    public boolean checkVisionAiHealth() {
        try {
            String url = visionAiUrl + "/health";
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            return response.getStatusCode() == HttpStatus.OK;
        } catch (Exception e) {
            logger.warn("视觉AI服务健康检查失败: {}", e.getMessage());
            return false;
        }
    }
    
    /**
     * 健康检查 - LLM AI服务
     */
    public boolean checkLlmAiHealth() {
        try {
            String url = llmAiUrl + "/api/tags";
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            return response.getStatusCode() == HttpStatus.OK;
        } catch (Exception e) {
            logger.warn("LLM AI服务健康检查失败: {}", e.getMessage());
            return false;
        }
    }
    
    /**
     * 后处理视觉AI检测结果，修复已知问题
     * @param originalResult 原始检测结果JSON
     * @param taskId 任务ID
     * @return 修复后的检测结果JSON
     */
    private String postProcessVisionResult(String originalResult, String taskId) {
        try {
            JsonNode resultNode = objectMapper.readTree(originalResult);
            
            // 检查是否有metadata节点
            if (resultNode.has("metadata")) {
                JsonNode metadata = resultNode.get("metadata");
                
                // 修复total_defects负数问题
                if (metadata.has("total_defects")) {
                    String totalDefectsStr = metadata.get("total_defects").asText();
                    try {
                        long totalDefects = Long.parseLong(totalDefectsStr);
                        if (totalDefects < 0) {
                            // 如果是负数，根据检测结果重新计算
                            int actualDefects = calculateActualDefects(resultNode);
                            ((com.fasterxml.jackson.databind.node.ObjectNode) metadata)
                                .put("total_defects", String.valueOf(actualDefects));
                            logger.info("修复total_defects: 原值={}, 修正值={}, taskId={}", 
                                      totalDefectsStr, actualDefects, taskId);
                        }
                    } catch (NumberFormatException e) {
                        logger.warn("total_defects格式异常: {}, taskId={}", totalDefectsStr, taskId);
                    }
                }
                
                // 改善缺陷类型映射到GB/T 3323标准
                enhanceDefectTypeMapping(resultNode, taskId);
            }
            
            return objectMapper.writeValueAsString(resultNode);
            
        } catch (Exception e) {
            logger.error("后处理视觉AI结果失败: taskId={}, error={}", taskId, e.getMessage(), e);
            // 如果后处理失败，返回原始结果
            return originalResult;
        }
    }
    
    /**
     * 计算实际缺陷数量
     */
    private int calculateActualDefects(JsonNode resultNode) {
        int defectCount = 0;
        
        if (resultNode.has("results") && resultNode.get("results").isArray()) {
            for (JsonNode result : resultNode.get("results")) {
                if (result.has("strName")) {
                    String defectType = result.get("strName").asText();
                    // 如果不是normal，则计为缺陷
                    if (!"normal".equals(defectType)) {
                        defectCount++;
                    }
                }
            }
        }
        
        return defectCount;
    }
    
    /**
     * 增强缺陷类型映射到GB/T 3323标准
     */
    private void enhanceDefectTypeMapping(JsonNode resultNode, String taskId) {
        try {
            if (resultNode.has("results") && resultNode.get("results").isArray()) {
                for (JsonNode result : resultNode.get("results")) {
                    if (result.has("strName")) {
                        String originalType = result.get("strName").asText();
                        String mappedType = mapToRadiographicStandard(originalType);
                        
                        if (!originalType.equals(mappedType)) {
                            ((com.fasterxml.jackson.databind.node.ObjectNode) result)
                                .put("strName", mappedType);
                            logger.debug("缺陷类型映射: {} -> {}, taskId={}", 
                                       originalType, mappedType, taskId);
                        }
                    }
                }
            }
        } catch (Exception e) {
            logger.warn("缺陷类型映射失败: taskId={}, error={}", taskId, e.getMessage());
        }
    }
    
    /**
     * 将缺陷类型映射到GB/T 3323射线检测标准
     */
    private String mapToRadiographicStandard(String originalType) {
        switch (originalType.toLowerCase()) {
            case "crack":
                return "A_crack";           // A类：裂纹
            case "porosity":
                return "E_round_defect";    // E类：圆形缺陷（气孔）
            case "inclusion":
                return "D_linear_defect";   // D类：条状缺陷（夹渣）
            case "lack_of_fusion":
                return "B_unfused";         // B类：未熔合
            case "undercut":
                return "F_undercut";        // F类：咬边
            case "slag_inclusion":
                return "D_linear_defect";   // D类：条状缺陷（夹渣）
            case "incomplete_penetration":
                return "C_incomplete_penetration"; // C类：未焊透
            case "concave":
                return "G_concave";         // G类：内凹
            case "normal":
                return "normal";            // 正常，不变
            default:
                return "H_other";           // H类：其他缺陷
        }
    }
} 