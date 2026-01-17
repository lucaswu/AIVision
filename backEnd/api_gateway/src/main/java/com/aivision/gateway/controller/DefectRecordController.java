package com.aivision.gateway.controller;

import com.aivision.gateway.model.ApiResponse;
import com.aivision.gateway.model.DefectRecord;
import com.aivision.gateway.service.DefectRecordService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 缺陷记录管理 API
 */
@RestController
@RequestMapping("/api/v1/defect-records")
@CrossOrigin(origins = "*")
@Tag(name = "缺陷记录管理", description = "管理单张图片的缺陷标注记录")
public class DefectRecordController {

    @Autowired
    private DefectRecordService defectRecordService;

    @GetMapping("/by-task-file/{taskFileId}")
    @Operation(summary = "获取指定文件的所有缺陷记录")
    public ResponseEntity<ApiResponse<List<DefectRecord>>> getByTaskFileId(
            @PathVariable String taskFileId) {
        try {
            List<DefectRecord> records = defectRecordService.getDefectRecordsByTaskFileId(taskFileId);
            return ResponseEntity.ok(ApiResponse.success("获取成功", records));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @GetMapping("/{defectRecordId}")
    @Operation(summary = "获取单个缺陷记录详情")
    public ResponseEntity<ApiResponse<DefectRecord>> getById(
            @PathVariable String defectRecordId) {
        try {
            return defectRecordService.getDefectRecordById(defectRecordId)
                .map(r -> ResponseEntity.ok(ApiResponse.success("获取成功", r)))
                .orElse(ResponseEntity.status(404).body(ApiResponse.error(404, "缺陷记录不存在")));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping
    @Operation(summary = "创建单个缺陷记录")
    public ResponseEntity<ApiResponse<DefectRecord>> create(
            @RequestBody DefectRecord defectRecord) {
        try {
            DefectRecord created = defectRecordService.createDefectRecord(defectRecord);
            return ResponseEntity.ok(ApiResponse.success("创建成功", created));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/batch")
    @Operation(summary = "批量创建缺陷记录")
    public ResponseEntity<ApiResponse<List<DefectRecord>>> createBatch(
            @RequestBody List<DefectRecord> defectRecords) {
        try {
            List<DefectRecord> created = defectRecordService.createDefectRecords(defectRecords);
            return ResponseEntity.ok(ApiResponse.success("批量创建成功", created));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PutMapping("/{defectRecordId}")
    @Operation(summary = "更新缺陷记录")
    public ResponseEntity<ApiResponse<DefectRecord>> update(
            @PathVariable String defectRecordId,
            @RequestBody DefectRecord defectRecord) {
        try {
            DefectRecord updated = defectRecordService.updateDefectRecord(defectRecordId, defectRecord);
            return ResponseEntity.ok(ApiResponse.success("更新成功", updated));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PutMapping("/replace/{taskFileId}")
    @Operation(summary = "替换指定文件的所有缺陷记录（先删除旧的，再创建新的）")
    public ResponseEntity<ApiResponse<List<DefectRecord>>> replace(
            @PathVariable String taskFileId,
            @RequestBody List<DefectRecord> defectRecords) {
        try {
            List<DefectRecord> replaced = defectRecordService.replaceDefectRecords(taskFileId, defectRecords);
            return ResponseEntity.ok(ApiResponse.success("替换成功", replaced));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @DeleteMapping("/{defectRecordId}")
    @Operation(summary = "删除单个缺陷记录")
    public ResponseEntity<ApiResponse<Void>> delete(
            @PathVariable String defectRecordId) {
        try {
            defectRecordService.deleteDefectRecord(defectRecordId);
            return ResponseEntity.ok(ApiResponse.success("删除成功", null));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @DeleteMapping("/by-task-file/{taskFileId}")
    @Operation(summary = "删除指定文件的所有缺陷记录")
    public ResponseEntity<ApiResponse<Void>> deleteByTaskFileId(
            @PathVariable String taskFileId) {
        try {
            defectRecordService.deleteDefectRecordsByTaskFileId(taskFileId);
            return ResponseEntity.ok(ApiResponse.success("删除成功", null));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @GetMapping("/count/{taskFileId}")
    @Operation(summary = "获取指定文件的缺陷数量统计")
    public ResponseEntity<ApiResponse<Long>> countByTaskFileId(
            @PathVariable String taskFileId) {
        try {
            long count = defectRecordService.countDefectsByTaskFileId(taskFileId);
            return ResponseEntity.ok(ApiResponse.success("统计成功", count));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }
}
