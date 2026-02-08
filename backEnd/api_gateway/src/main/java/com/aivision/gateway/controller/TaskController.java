package com.aivision.gateway.controller;

import com.aivision.gateway.model.*;
import com.aivision.gateway.service.TaskService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;

@RestController
@RequestMapping("/api/v1/tasks")
@CrossOrigin(origins = "*")
@Tag(name = "任务管理", description = "AI Vision 检测任务管理相关接口")
public class TaskController {
    
    @Autowired
    private TaskService taskService;
    
    @PostMapping("/submit")
    @Operation(summary = "提交检测任务", description = "支持文件和文件夹批量提交")
    public ResponseEntity<ApiResponse<TaskSubmitResponse>> submitTask(
        @RequestHeader("project-id") String projectId,
        @RequestHeader("user-id") String userId,
        @Valid @RequestBody TaskSubmitRequest request) {
        try {
            TaskSubmitResponse response = taskService.submitTask(projectId, userId, request);
            return ResponseEntity.ok(ApiResponse.success("任务提交成功", response));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @GetMapping("/{task_id}/status")
    @Operation(summary = "获取任务状态和结果")
    public ResponseEntity<ApiResponse<TaskStatusResponse>> getTaskStatus(
        @PathVariable("task_id") String taskId,
        @RequestHeader("project-id") String projectId,
        @RequestHeader("user-id") String userId) {
        try {
            TaskStatusResponse response = taskService.getTaskStatus(taskId, projectId, userId);
            return ResponseEntity.ok(ApiResponse.success("获取成功", response));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @GetMapping("/list")
    @Operation(summary = "获取任务列表")
    public ResponseEntity<ApiResponse<TaskListResponse>> getTaskList(
        @RequestHeader("project-id") String projectId,
        @RequestHeader("user-id") String userId) {
        try {
            TaskListResponse response = taskService.getTaskList(projectId, userId);
            return ResponseEntity.ok(ApiResponse.success("获取成功", response));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/report-result")
    @Operation(summary = "获取详细报告结果（跨任务查询）", description = "根据项目ID列表和工件编号列表查询详细的检测报告数据")
    public ResponseEntity<ApiResponse<ReportResultResponse>> getTaskReportResult(
            @RequestHeader("user-id") String userId,
            @RequestBody ReportResultRequest request) {
        try {
            ReportResultResponse response = taskService.getTaskReportResult(userId, request);
            return ResponseEntity.ok(ApiResponse.success("获取成功", response));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/{task_id}/restart")
    @Operation(summary = "重跑任务", description = "重置任务进度并重新开始检测")
    public ResponseEntity<ApiResponse<Void>> restartTask(
        @PathVariable("task_id") String taskId,
        @RequestHeader("project-id") String projectId,
        @RequestHeader("user-id") String userId) {
        try {
            taskService.restartTask(taskId, projectId, userId);
            return ResponseEntity.ok(ApiResponse.success("任务已重新启动", null));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PutMapping("/{task_id}/archive")
    @Operation(summary = "归档/取消归档任务")
    public ResponseEntity<ApiResponse<Void>> archiveTask(
        @PathVariable("task_id") String taskId,
        @RequestHeader("project-id") String projectId,
        @RequestHeader("user-id") String userId,
        @RequestParam("archived") boolean archived) {
        try {
            taskService.archiveTask(taskId, projectId, userId, archived);
            return ResponseEntity.ok(ApiResponse.success(archived ? "任务已归档" : "任务已取消归档", null));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/{task_id}/duplicate")
    @Operation(summary = "复制任务")
    public ResponseEntity<ApiResponse<String>> duplicateTask(
        @PathVariable("task_id") String taskId,
        @RequestHeader("project-id") String projectId,
        @RequestHeader("user-id") String userId) {
        try {
            String newTaskId = taskService.duplicateTask(taskId, projectId, userId);
            return ResponseEntity.ok(ApiResponse.success("任务复制成功", newTaskId));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PutMapping("/{taskId}")
    @Operation(summary = "更新任务信息")
    public ResponseEntity<ApiResponse<Task>> updateTask(
        @PathVariable String taskId,
        @RequestHeader("project-id") String projectId,
        @RequestHeader("user-id") String userId,
        @Valid @RequestBody TaskUpdateRequest request) {
        try {
            Task updatedTask = taskService.updateTask(taskId, projectId, userId, request);
            return ResponseEntity.ok(ApiResponse.success("任务更新成功", updatedTask));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @DeleteMapping("/{taskId}")
    @Operation(summary = "删除任务")
    public ResponseEntity<ApiResponse<Void>> deleteTask(
        @PathVariable String taskId,
        @RequestHeader("project-id") String projectId,
        @RequestHeader("user-id") String userId) {
        try {
            taskService.deleteTask(taskId, projectId, userId);
            return ResponseEntity.ok(ApiResponse.success("任务删除成功", null));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }
}
