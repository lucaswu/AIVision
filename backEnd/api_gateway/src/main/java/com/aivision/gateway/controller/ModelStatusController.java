package com.aivision.gateway.controller;

import com.aivision.gateway.model.ApiResponse;
import com.aivision.gateway.service.AiServiceClient;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 推理服务当前加载模型状态查询 API
 */
@RestController
@RequestMapping("/api/v1/models")
@CrossOrigin(origins = "*")
@Tag(name = "模型状态查询", description = "查询推理服务当前激活的模型信息")
public class ModelStatusController {

    @Autowired
    private AiServiceClient aiServiceClient;

    @GetMapping("/status")
    @Operation(summary = "获取推理服务当前激活的模型信息")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getModelsStatus() {
        try {
            Map<String, Object> status = aiServiceClient.getModelsStatus();
            return ResponseEntity.ok(ApiResponse.success("获取成功", status));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }
}
