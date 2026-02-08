package com.aivision.gateway.controller;

import com.aivision.gateway.model.ApiResponse;
import com.aivision.gateway.model.CreateTrainingDataSourceRequest;
import com.aivision.gateway.model.CreateTrainingDatasetRequest;
import com.aivision.gateway.model.TrainingDataSourceItem;
import com.aivision.gateway.model.TrainingDataSummary;
import com.aivision.gateway.model.TrainingDatasetItem;
import com.aivision.gateway.service.TrainingDataService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api/v1/training/projects")
@CrossOrigin(origins = "*")
@Tag(name = "训练平台-数据管理", description = "训练平台数据管理相关接口 V1")
public class TrainingDataController {

    @Autowired
    private TrainingDataService trainingDataService;

    @GetMapping("/{projectId}/data/summary")
    @Operation(summary = "获取数据管理统计", description = "获取原始数据/已标注数据/数据集/数据源统计")
    public ResponseEntity<ApiResponse<TrainingDataSummary>> getSummary(
            @Parameter(description = "项目ID", required = true)
            @PathVariable("projectId") String projectId,
            @Parameter(description = "用户ID", required = true, in = ParameterIn.HEADER)
            @RequestHeader("user-id") String userId) {
        try {
            TrainingDataSummary summary = trainingDataService.getSummary(projectId, userId);
            return ResponseEntity.ok(ApiResponse.success("获取成功", summary));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        } catch (RuntimeException e) {
            if (e.getMessage().contains("无权限")) {
                return ResponseEntity.status(403).body(ApiResponse.error(403, e.getMessage()));
            }
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @GetMapping("/{projectId}/data-sources")
    @Operation(summary = "获取数据源列表", description = "获取训练项目下的数据源列表")
    public ResponseEntity<ApiResponse<List<TrainingDataSourceItem>>> getDataSources(
            @Parameter(description = "项目ID", required = true)
            @PathVariable("projectId") String projectId,
            @Parameter(description = "用户ID", required = true, in = ParameterIn.HEADER)
            @RequestHeader("user-id") String userId) {
        try {
            List<TrainingDataSourceItem> items = trainingDataService.getDataSources(projectId, userId);
            return ResponseEntity.ok(ApiResponse.success("获取成功", items, items.size()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        } catch (RuntimeException e) {
            if (e.getMessage().contains("无权限")) {
                return ResponseEntity.status(403).body(ApiResponse.error(403, e.getMessage()));
            }
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/{projectId}/data-sources")
    @Operation(summary = "创建数据源", description = "为训练项目添加数据源")
    public ResponseEntity<ApiResponse<TrainingDataSourceItem>> createDataSource(
            @Parameter(description = "项目ID", required = true)
            @PathVariable("projectId") String projectId,
            @Parameter(description = "用户ID", required = true, in = ParameterIn.HEADER)
            @RequestHeader("user-id") String userId,
            @RequestBody CreateTrainingDataSourceRequest request) {
        try {
            TrainingDataSourceItem item = trainingDataService.createDataSource(projectId, userId, request);
            return ResponseEntity.ok(ApiResponse.success("创建成功", item));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        } catch (RuntimeException e) {
            if (e.getMessage().contains("无权限")) {
                return ResponseEntity.status(403).body(ApiResponse.error(403, e.getMessage()));
            }
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/{projectId}/data-sources/upload")
    @Operation(summary = "上传数据源", description = "选择本地文件夹批量上传为数据源")
    public ResponseEntity<ApiResponse<TrainingDataSourceItem>> uploadDataSource(
            @Parameter(description = "项目ID", required = true)
            @PathVariable("projectId") String projectId,
            @Parameter(description = "用户ID", required = true, in = ParameterIn.HEADER)
            @RequestHeader("user-id") String userId,
            @RequestParam(value = "Name", required = false) String name,
            @RequestPart("File") MultipartFile[] files) {
        try {
            TrainingDataSourceItem item = trainingDataService.uploadDataSource(projectId, userId, name, files);
            return ResponseEntity.ok(ApiResponse.success("上传成功", item));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        } catch (RuntimeException e) {
            if (e.getMessage().contains("无权限")) {
                return ResponseEntity.status(403).body(ApiResponse.error(403, e.getMessage()));
            }
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @DeleteMapping("/{projectId}/data-sources/{sourceId}")
    @Operation(summary = "删除数据源", description = "删除训练数据源")
    public ResponseEntity<ApiResponse<Void>> deleteDataSource(
            @Parameter(description = "项目ID", required = true)
            @PathVariable("projectId") String projectId,
            @Parameter(description = "数据源ID", required = true)
            @PathVariable("sourceId") String sourceId,
            @Parameter(description = "用户ID", required = true, in = ParameterIn.HEADER)
            @RequestHeader("user-id") String userId) {
        try {
            trainingDataService.deleteDataSource(projectId, userId, sourceId);
            return ResponseEntity.ok(ApiResponse.success("删除成功", null));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        } catch (RuntimeException e) {
            if (e.getMessage().contains("无权限")) {
                return ResponseEntity.status(403).body(ApiResponse.error(403, e.getMessage()));
            }
            if (e.getMessage().contains("多个数据集")) {
                return ResponseEntity.status(409).body(ApiResponse.error(409, e.getMessage()));
            }
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @GetMapping("/{projectId}/datasets")
    @Operation(summary = "获取数据集列表", description = "获取训练项目下的数据集列表")
    public ResponseEntity<ApiResponse<List<TrainingDatasetItem>>> getDatasets(
            @Parameter(description = "项目ID", required = true)
            @PathVariable("projectId") String projectId,
            @Parameter(description = "用户ID", required = true, in = ParameterIn.HEADER)
            @RequestHeader("user-id") String userId) {
        try {
            List<TrainingDatasetItem> items = trainingDataService.getDatasets(projectId, userId);
            return ResponseEntity.ok(ApiResponse.success("获取成功", items, items.size()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        } catch (RuntimeException e) {
            if (e.getMessage().contains("无权限")) {
                return ResponseEntity.status(403).body(ApiResponse.error(403, e.getMessage()));
            }
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/{projectId}/datasets")
    @Operation(summary = "创建数据集", description = "基于数据源创建训练数据集")
    public ResponseEntity<ApiResponse<TrainingDatasetItem>> createDataset(
            @Parameter(description = "项目ID", required = true)
            @PathVariable("projectId") String projectId,
            @Parameter(description = "用户ID", required = true, in = ParameterIn.HEADER)
            @RequestHeader("user-id") String userId,
            @RequestBody CreateTrainingDatasetRequest request) {
        try {
            TrainingDatasetItem item = trainingDataService.createDataset(projectId, userId, request);
            return ResponseEntity.ok(ApiResponse.success("创建成功", item));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        } catch (RuntimeException e) {
            if (e.getMessage().contains("无权限")) {
                return ResponseEntity.status(403).body(ApiResponse.error(403, e.getMessage()));
            }
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @DeleteMapping("/{projectId}/datasets/{datasetId}")
    @Operation(summary = "删除数据集", description = "删除训练数据集")
    public ResponseEntity<ApiResponse<Void>> deleteDataset(
            @Parameter(description = "项目ID", required = true)
            @PathVariable("projectId") String projectId,
            @Parameter(description = "数据集ID", required = true)
            @PathVariable("datasetId") String datasetId,
            @Parameter(description = "用户ID", required = true, in = ParameterIn.HEADER)
            @RequestHeader("user-id") String userId) {
        try {
            trainingDataService.deleteDataset(projectId, userId, datasetId);
            return ResponseEntity.ok(ApiResponse.success("删除成功", null));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        } catch (RuntimeException e) {
            if (e.getMessage().contains("无权限")) {
                return ResponseEntity.status(403).body(ApiResponse.error(403, e.getMessage()));
            }
            if (e.getMessage().contains("训练任务")) {
                return ResponseEntity.status(409).body(ApiResponse.error(409, e.getMessage()));
            }
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }
}
