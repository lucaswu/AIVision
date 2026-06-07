package com.aivision.gateway.controller;

import com.aivision.gateway.model.ApiResponse;
import com.aivision.gateway.service.AiServiceClient;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/ocr")
@CrossOrigin(origins = "*")
@Tag(name = "OCR识别", description = "图像区域 OCR / 区域归一化信噪比 / 双丝分辨率接口")
public class OcrController {

    @Autowired
    private AiServiceClient aiServiceClient;

    @PostMapping("/recognize")
    @Operation(summary = "识别图像区域文字", description = "接收base64编码的图片，调用PaddleOCR识别文字并返回")
    public ResponseEntity<ApiResponse<Map<String, Object>>> recognizeRegion(
            @RequestBody Map<String, String> request) {
        try {
            String base64 = request.get("base64");
            if (base64 == null || base64.isBlank()) {
                return ResponseEntity.badRequest()
                    .body(ApiResponse.error(400, "base64参数不能为空"));
            }
            String taskId = request.get("task_id");       // 可选，用于调试图片命名
            String fieldName = request.get("field_name"); // 可选，用于调试图片命名
            Map<String, Object> result = aiServiceClient.recognizeImageRegion(base64, taskId, fieldName);
            return ResponseEntity.ok(ApiResponse.success("识别成功", result));
        } catch (Exception e) {
            return ResponseEntity.status(500)
                .body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/region-snr")
    @Operation(summary = "计算图像区域归一化信噪比", description = "接收base64编码的图片区域，调用区域归一化信噪比接口并返回")
    public ResponseEntity<ApiResponse<Map<String, Object>>> computeRegionSnr(
            @RequestBody Map<String, Object> request) {
        try {
            Object base64Value = request.get("base64");
            String base64 = base64Value instanceof String ? (String) base64Value : null;
            if (base64 == null || base64.isBlank()) {
                return ResponseEntity.badRequest()
                    .body(ApiResponse.error(400, "base64参数不能为空"));
            }
            String taskId = request.get("task_id") instanceof String ? (String) request.get("task_id") : null;
            String fieldName = request.get("field_name") instanceof String ? (String) request.get("field_name") : null;
            Double srBUm = parseOptionalDouble(request.get("sr_b_um"));
            Map<String, Object> result = aiServiceClient.computeImageRegionSnr(base64, taskId, fieldName, srBUm);
            return ResponseEntity.ok(ApiResponse.success("计算成功", result));
        } catch (Exception e) {
            return ResponseEntity.status(500)
                .body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/double-wire")
    @Operation(summary = "分析双丝分辨率", description = "接收base64编码的双丝像质计strip图片，调用双丝分辨率分析接口并返回")
    public ResponseEntity<ApiResponse<Map<String, Object>>> computeDoubleWire(
            @RequestBody Map<String, String> request) {
        try {
            String base64 = request.get("base64");
            if (base64 == null || base64.isBlank()) {
                return ResponseEntity.badRequest()
                    .body(ApiResponse.error(400, "base64参数不能为空"));
            }
            String taskId = request.get("task_id");
            String fieldName = request.get("field_name");
            Map<String, Object> result = aiServiceClient.computeDoubleWire(base64, taskId, fieldName);
            return ResponseEntity.ok(ApiResponse.success("分析成功", result));
        } catch (Exception e) {
            return ResponseEntity.status(500)
                .body(ApiResponse.error(500, e.getMessage()));
        }
    }

    private Double parseOptionalDouble(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number) {
            return ((Number) value).doubleValue();
        }
        if (value instanceof String) {
            String text = ((String) value).trim();
            if (text.isEmpty()) {
                return null;
            }
            return Double.parseDouble(text);
        }
        throw new IllegalArgumentException("sr_b_um参数格式无效");
    }
}
