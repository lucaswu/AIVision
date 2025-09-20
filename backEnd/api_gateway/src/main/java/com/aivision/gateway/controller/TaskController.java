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
    
    /**
     * 提交检测任务
     * POST /api/v1/tasks/submit
     */
    @PostMapping("/submit")
    @Operation(
        summary = "提交检测任务",
        description = "提交新的AI检测任务，支持多文件批量检测，项目ID和用户ID从header获取"
    )
    @ApiResponses(value = {
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "200",
            description = "任务提交成功",
            content = @Content(
                mediaType = "application/json",
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"Code\": 200,\n" +
                           "    \"Message\": \"任务提交成功\",\n" +
                           "    \"Data\": {\n" +
                           "        \"TaskId\": \"f47ac10b-58cc-4372-a567-0e02b2c3d479\",\n" +
                           "        \"Status\": \"pending\",\n" +
                           "        \"FileCount\": 2,\n" +
                           "        \"Timestamp\": \"2025-06-24 15:40:00\"\n" +
                           "    }\n" +
                           "}"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "请求参数错误"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "项目或文件不存在"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    public ResponseEntity<ApiResponse<TaskSubmitResponse>> submitTask(
        @Parameter(description = "项目ID", required = true, example = "70072504-0da8-4638-8f53-4ca031da7604", in = ParameterIn.HEADER)
        @RequestHeader("project-id") String projectId,
        
        @Parameter(description = "用户ID", required = true, example = "user001", in = ParameterIn.HEADER)
        @RequestHeader("user-id") String userId,
        
        @io.swagger.v3.oas.annotations.parameters.RequestBody(
            description = "任务提交请求",
            required = true,
            content = @Content(
                schema = @Schema(implementation = TaskSubmitRequest.class),
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"Name\": \"PCB缺陷检测任务\",\n" +
                           "    \"Description\": \"检测PCB板上的焊接缺陷\",\n" +
                           "    \"AlgorithmType\": \"object-detection\",\n" +
                           "    \"SelectedFiles\": [\n" +
                           "        {\n" +
                           "            \"FileId\": \"ce2e7099-b02b-4fc1-a7c3-9af8bae836fb\"\n" +
                           "        },\n" +
                           "        {\n" +
                           "            \"FileId\": \"c0290917-5104-44dc-ab10-dbcf2c95582a\"\n" +
                           "        }\n" +
                           "    ]\n" +
                           "}"
                )
            )
        )
        @Valid @RequestBody TaskSubmitRequest request) {
        
        try {
            // 验证必要参数
            if (projectId == null || projectId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(ApiResponse.error(400, "项目ID不能为空"));
            }
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(ApiResponse.error(400, "用户ID不能为空"));
            }
            
            // 提交任务
            TaskSubmitResponse response = taskService.submitTask(projectId, userId, request);
            
            return ResponseEntity.ok(
                ApiResponse.success("任务提交成功", response)
            );
            
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(
                ApiResponse.error(400, e.getMessage())
            );
            
        } catch (RuntimeException e) {
            if (e.getMessage().contains("不存在")) {
                return ResponseEntity.status(404).body(
                    ApiResponse.error(404, e.getMessage())
                );
            }
            return ResponseEntity.status(500).body(
                ApiResponse.error(500, e.getMessage())
            );
            
        } catch (Exception e) {
            return ResponseEntity.status(500).body(
                ApiResponse.error(500, "服务器内部错误: " + e.getMessage())
            );
        }
    }
    
    /**
     * 获取任务状态和结果
     * GET /api/v1/tasks/{task_id}/status
     */
    @GetMapping("/{task_id}/status")
    @Operation(
        summary = "获取任务状态和结果",
        description = "根据任务ID获取任务的详细状态和每个文件的处理结果，项目ID和用户ID从header获取"
    )
    @ApiResponses(value = {
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "200",
            description = "获取成功",
            content = @Content(
                mediaType = "application/json",
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"Code\": 200,\n" +
                           "    \"Message\": \"获取成功\",\n" +
                           "    \"Data\": {\n" +
                           "        \"Id\": \"4ff0c9a1-2025-4c2e-9bee-cab39d78ea39\",\n" +
                           "        \"Name\": \"测试检测任务\",\n" +
                           "        \"Description\": \"测试图片缺陷检测\",\n" +
                           "        \"ProjectId\": \"398d6a89-21ad-4fde-b798-32436ab2d047\",\n" +
                           "        \"UserId\": \"user001\",\n" +
                           "        \"AlgorithmType\": \"object-detection\",\n" +
                           "        \"FileCount\": 2,\n" +
                           "        \"ProcessedFiles\": 2,\n" +
                           "        \"SuccessFiles\": 2,\n" +
                           "        \"FailedFiles\": 0,\n" +
                           "        \"CreateTime\": \"2025-06-25 12:31:45\",\n" +
                           "        \"UpdateTime\": \"2025-06-25 12:32:15\",\n" +
                           "        \"Status\": \"completed\",\n" +
                           "        \"Progress\": 100,\n" +
                           "        \"ErrorMessage\": null,\n" +
                           "        \"ProcessingFiles\": 0,\n" +
                           "        \"InQueueFiles\": 0,\n" +
                           "        \"SelectedFiles\": [\n" +
                           "            {\n" +
                           "                \"TaskFileId\": \"xxx-xxx-xxx\",\n" +
                           "                \"FileId\": \"4852273e-b64a-44a7-b676-94b533c3ac23\",\n" +
                           "                \"FileName\": \"001.jpg\",\n" +
                           "                \"LogicalPath\": \"/test-images/defective/001.jpg\",\n" +
                           "                \"Status\": \"completed\",\n" +
                           "                \"VisionResult\": \"{\\\"detections\\\": []}\",\n" +
                           "                \"LlmResult\": \"检测报告内容\",\n" +
                           "                \"ReportPath\": null,\n" +
                           "                \"ErrorMessage\": null,\n" +
                           "                \"ProcessingStartTime\": \"2025-06-25 12:31:50\",\n" +
                           "                \"ProcessingEndTime\": \"2025-06-25 12:32:10\"\n" +
                           "            }\n" +
                           "        ]\n" +
                           "    }\n" +
                           "}"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "请求参数错误"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "任务不存在或无权限访问"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    public ResponseEntity<ApiResponse<TaskStatusResponse>> getTaskStatus(
        @Parameter(description = "任务ID", required = true, example = "4ff0c9a1-2025-4c2e-9bee-cab39d78ea39", in = ParameterIn.PATH)
        @PathVariable("task_id") String taskId,
        
        @Parameter(description = "项目ID", required = true, example = "398d6a89-21ad-4fde-b798-32436ab2d047", in = ParameterIn.HEADER)
        @RequestHeader("project-id") String projectId,
        
        @Parameter(description = "用户ID", required = true, example = "user001", in = ParameterIn.HEADER)
        @RequestHeader("user-id") String userId) {
        
        try {
            // 验证必要参数
            if (taskId == null || taskId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(ApiResponse.error(400, "任务ID不能为空"));
            }
            if (projectId == null || projectId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(ApiResponse.error(400, "项目ID不能为空"));
            }
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(ApiResponse.error(400, "用户ID不能为空"));
            }
            
            // 获取任务状态
            TaskStatusResponse response = taskService.getTaskStatus(taskId, projectId, userId);
            
            return ResponseEntity.ok(
                ApiResponse.success("获取成功", response)
            );
            
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(
                ApiResponse.error(400, e.getMessage())
            );
            
        } catch (RuntimeException e) {
            if (e.getMessage().contains("不存在") || e.getMessage().contains("无权限")) {
                return ResponseEntity.status(404).body(
                    ApiResponse.error(404, e.getMessage())
                );
            }
            return ResponseEntity.status(500).body(
                ApiResponse.error(500, e.getMessage())
            );
            
        } catch (Exception e) {
            return ResponseEntity.status(500).body(
                ApiResponse.error(500, "服务器内部错误: " + e.getMessage())
            );
        }
    }
    
    /**
     * 获取任务列表
     * GET /api/v1/tasks/list
     */
    @GetMapping("/list")
    @Operation(
        summary = "获取任务列表",
        description = "获取用户在指定项目下的所有任务列表，包含每个任务下的任务文件信息，项目ID和用户ID从header获取"
    )
    @ApiResponses(value = {
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "200",
            description = "获取成功",
            content = @Content(
                mediaType = "application/json",
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"Code\": 200,\n" +
                           "    \"Message\": \"获取成功\",\n" +
                           "    \"Data\": {\n" +
                           "        \"TotalCount\": 2,\n" +
                           "        \"Tasks\": [\n" +
                           "            {\n" +
                           "                \"Id\": \"4ff0c9a1-2025-4c2e-9bee-cab39d78ea39\",\n" +
                           "                \"Name\": \"PCB缺陷检测任务\",\n" +
                           "                \"Description\": \"检测PCB板上的焊接缺陷\",\n" +
                           "                \"ProjectId\": \"398d6a89-21ad-4fde-b798-32436ab2d047\",\n" +
                           "                \"UserId\": \"user001\",\n" +
                           "                \"AlgorithmType\": \"object-detection\",\n" +
                           "                \"Status\": \"completed\",\n" +
                           "                \"Progress\": 100,\n" +
                           "                \"FileCount\": 2,\n" +
                           "                \"ProcessedFiles\": 2,\n" +
                           "                \"SuccessFiles\": 2,\n" +
                           "                \"FailedFiles\": 0,\n" +
                           "                \"CreateTime\": \"2025-06-25 12:31:45\",\n" +
                           "                \"UpdateTime\": \"2025-06-25 12:32:15\",\n" +
                           "                \"ErrorMessage\": null,\n" +
                           "                \"TaskFiles\": [\n" +
                           "                    {\n" +
                           "                        \"TaskFileId\": \"xxx-xxx-xxx\",\n" +
                           "                        \"FileId\": \"4852273e-b64a-44a7-b676-94b533c3ac23\",\n" +
                           "                        \"FileName\": \"001.jpg\",\n" +
                           "                        \"LogicalPath\": \"/test-images/defective/001.jpg\",\n" +
                           "                        \"Status\": \"completed\",\n" +
                           "                        \"VisionResult\": \"{\\\"detections\\\": []}\",\n" +
                           "                        \"LlmResult\": \"检测报告内容\",\n" +
                           "                        \"ReportPath\": null,\n" +
                           "                        \"ErrorMessage\": null,\n" +
                           "                        \"ProcessingStartTime\": \"2025-06-25 12:31:50\",\n" +
                           "                        \"ProcessingEndTime\": \"2025-06-25 12:32:10\"\n" +
                           "                    }\n" +
                           "                ]\n" +
                           "            }\n" +
                           "        ]\n" +
                           "    }\n" +
                           "}"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "请求参数错误"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "项目不存在或无权限访问"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    public ResponseEntity<ApiResponse<TaskListResponse>> getTaskList(
        @Parameter(description = "项目ID", required = true, example = "398d6a89-21ad-4fde-b798-32436ab2d047", in = ParameterIn.HEADER)
        @RequestHeader("project-id") String projectId,
        
        @Parameter(description = "用户ID", required = true, example = "user001", in = ParameterIn.HEADER)
        @RequestHeader("user-id") String userId) {
        
        try {
            // 验证必要参数
            if (projectId == null || projectId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(ApiResponse.error(400, "项目ID不能为空"));
            }
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(ApiResponse.error(400, "用户ID不能为空"));
            }
            
            // 获取任务列表
            TaskListResponse response = taskService.getTaskList(projectId, userId);
            
            return ResponseEntity.ok(
                ApiResponse.success("获取成功", response)
            );
            
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(
                ApiResponse.error(400, e.getMessage())
            );
            
        } catch (RuntimeException e) {
            if (e.getMessage().contains("不存在") || e.getMessage().contains("无权限")) {
                return ResponseEntity.status(404).body(
                    ApiResponse.error(404, e.getMessage())
                );
            }
            return ResponseEntity.status(500).body(
                ApiResponse.error(500, e.getMessage())
            );
            
        } catch (Exception e) {
            return ResponseEntity.status(500).body(
                ApiResponse.error(500, "服务器内部错误: " + e.getMessage())
            );
        }
    }
    
    /**
     * 更新任务
     * PUT /api/v1/tasks/{taskId}
     */
    @PutMapping("/{taskId}")
    @Operation(
        summary = "更新任务",
        description = "根据任务ID更新任务信息，只能更新任务名称、描述和算法类型"
    )
    @ApiResponses(value = {
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "200",
            description = "任务更新成功",
            content = @Content(
                mediaType = "application/json",
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"Code\": 200,\n" +
                           "    \"Message\": \"任务更新成功\",\n" +
                           "    \"Data\": {\n" +
                           "        \"Id\": \"34e86f73-099e-486d-abf7-a49a7ebb7e78\",\n" +
                           "        \"Name\": \"更新后的任务名称\",\n" +
                           "        \"Description\": \"更新后的任务描述\",\n" +
                           "        \"AlgorithmType\": \"object-detection\",\n" +
                           "        \"Status\": \"pending\"\n" +
                           "    }\n" +
                           "}"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "400", 
            description = "请求参数错误"
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "404", 
            description = "任务不存在或无权限访问"
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "500", 
            description = "服务器内部错误"
        )
    })
    public ResponseEntity<ApiResponse<Task>> updateTask(
        @Parameter(description = "任务ID", required = true, example = "34e86f73-099e-486d-abf7-a49a7ebb7e78")
        @PathVariable String taskId,
        
        @Parameter(description = "项目ID", required = true, example = "c6f4c9b9-a12e-4b11-9792-24993a69497a")
        @RequestHeader("project-id") String projectId,
        
        @Parameter(description = "用户ID", required = true, example = "user001")
        @RequestHeader("user-id") String userId,
        
        @Parameter(description = "任务更新信息", required = true)
        @Valid @RequestBody TaskUpdateRequest request) {
        
        try {
            // 基础验证
            if (taskId == null || taskId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "任务ID不能为空"));
            }
            
            if (projectId == null || projectId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "项目ID不能为空"));
            }
            
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "用户ID不能为空"));
            }
            
            // 调用服务更新任务
            Task updatedTask = taskService.updateTask(taskId, projectId, userId, request);
            
            return ResponseEntity.ok(ApiResponse.success("任务更新成功", updatedTask));
            
        } catch (IllegalArgumentException e) {
            // 区分不同类型的错误
            if (e.getMessage().contains("不存在") || e.getMessage().contains("无权限访问")) {
                return ResponseEntity.status(404).body(
                    ApiResponse.error(404, e.getMessage()));
            } else {
                // 业务规则验证失败（如状态不允许编辑）
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, e.getMessage()));
            }
                
        } catch (Exception e) {
            return ResponseEntity.status(500).body(
                ApiResponse.error(500, "服务器内部错误: " + e.getMessage()));
        }
    }

    /**
     * 删除任务
     * DELETE /api/v1/tasks/{taskId}
     */
    @DeleteMapping("/{taskId}")
    @Operation(
        summary = "删除任务",
        description = "根据任务ID删除指定任务，需要提供项目ID和用户ID用于权限验证"
    )
    @ApiResponses(value = {
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "200",
            description = "任务删除成功",
            content = @Content(
                mediaType = "application/json",
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"Code\": 200,\n" +
                           "    \"Message\": \"任务删除成功\",\n" +
                           "    \"Data\": null\n" +
                           "}"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "400", 
            description = "请求参数错误"
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "404", 
            description = "任务不存在或无权限访问"
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "500", 
            description = "服务器内部错误"
        )
    })
    public ResponseEntity<ApiResponse<Void>> deleteTask(
        @Parameter(description = "任务ID", required = true, example = "16548faa-43d2-4a9d-975b-50a36af9cbac")
        @PathVariable String taskId,
        
        @Parameter(description = "项目ID", required = true, example = "398d6a89-21ad-4fde-b798-32436ab2d047")
        @RequestHeader("project-id") String projectId,
        
        @Parameter(description = "用户ID", required = true, example = "user001")
        @RequestHeader("user-id") String userId) {
        
        try {
            // 基础验证
            if (taskId == null || taskId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "任务ID不能为空"));
            }
            
            if (projectId == null || projectId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "项目ID不能为空"));
            }
            
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "用户ID不能为空"));
            }
            
            // 调用服务删除任务
            boolean deleted = taskService.deleteTask(taskId, projectId, userId);
            
            if (deleted) {
                return ResponseEntity.ok(ApiResponse.success("任务删除成功", null));
            } else {
                return ResponseEntity.status(404).body(
                    ApiResponse.error(404, "任务不存在或无权限访问"));
            }
            
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(404).body(
                ApiResponse.error(404, e.getMessage()));
                
        } catch (Exception e) {
            return ResponseEntity.status(500).body(
                ApiResponse.error(500, "服务器内部错误: " + e.getMessage()));
        }
    }
} 