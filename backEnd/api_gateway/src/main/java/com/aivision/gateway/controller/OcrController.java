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
@Tag(name = "OCR识别", description = "图像区域OCR识别接口")
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
            Map<String, Object> result = aiServiceClient.recognizeImageRegion(base64);
            return ResponseEntity.ok(ApiResponse.success("识别成功", result));
        } catch (Exception e) {
            return ResponseEntity.status(500)
                .body(ApiResponse.error(500, e.getMessage()));
        }
    }
}
