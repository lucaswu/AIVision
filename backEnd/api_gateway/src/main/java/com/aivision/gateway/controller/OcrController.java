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
@Tag(name = "OCR识别", description = "图像区域 OCR / 区域归一化信噪比接口")
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
            @RequestBody Map<String, String> request) {
        try {
            String base64 = request.get("base64");
            if (base64 == null || base64.isBlank()) {
                return ResponseEntity.badRequest()
                    .body(ApiResponse.error(400, "base64参数不能为空"));
            }
            String taskId = request.get("task_id");
            String fieldName = request.get("field_name");
            Map<String, Object> result = aiServiceClient.computeImageRegionSnr(base64, taskId, fieldName);
            return ResponseEntity.ok(ApiResponse.success("计算成功", result));
        } catch (Exception e) {
            return ResponseEntity.status(500)
                .body(ApiResponse.error(500, e.getMessage()));
        }
    }
}
