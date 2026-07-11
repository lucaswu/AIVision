package com.aivision.gateway.controller;

import com.aivision.gateway.model.ApiResponse;
import com.aivision.gateway.model.WeldJoint;
import com.aivision.gateway.service.WeldJointService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 焊口记录管理 API
 */
@RestController
@RequestMapping("/api/v1/weld-joints")
@CrossOrigin(origins = "*")
@Tag(name = "焊口记录管理", description = "管理单张底片关联的多个焊口编号")
public class WeldJointController {

    @Autowired
    private WeldJointService weldJointService;

    @GetMapping("/task-file/{taskFileId}")
    @Operation(summary = "获取指定文件的所有焊口记录")
    public ResponseEntity<ApiResponse<List<WeldJoint>>> getByTaskFileId(
            @PathVariable String taskFileId) {
        try {
            List<WeldJoint> joints = weldJointService.getWeldJointsByTaskFileId(taskFileId);
            return ResponseEntity.ok(ApiResponse.success("获取成功", joints));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/task-file/{taskFileId}/replace")
    @Operation(summary = "替换指定文件的焊口列表（新增/更新/删除）")
    public ResponseEntity<ApiResponse<List<WeldJoint>>> replace(
            @PathVariable String taskFileId,
            @RequestBody List<WeldJoint> weldJoints) {
        try {
            List<WeldJoint> replaced = weldJointService.replaceWeldJoints(taskFileId, weldJoints);
            return ResponseEntity.ok(ApiResponse.success("保存成功", replaced));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @DeleteMapping("/task-file/{taskFileId}")
    @Operation(summary = "删除指定文件的所有焊口记录")
    public ResponseEntity<ApiResponse<Void>> deleteByTaskFileId(
            @PathVariable String taskFileId) {
        try {
            weldJointService.deleteWeldJointsByTaskFileId(taskFileId);
            return ResponseEntity.ok(ApiResponse.success("删除成功", null));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }
}
