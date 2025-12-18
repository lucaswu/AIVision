package com.aivision.gateway.controller;

import com.aivision.gateway.model.*;
import com.aivision.gateway.service.DirectoryService;
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
@RequestMapping("/api/v1/directories")
@CrossOrigin(origins = "*")
@Tag(name = "目录管理", description = "AI Vision 项目目录管理相关接口 V1")
public class DirectoryController {
    
    @Autowired
    private DirectoryService directoryService;
    
    /**
     * 创建目录
     * POST /api/v1/directories/create
     */
    @PostMapping("/create")
    @Operation(
        summary = "创建目录",
        description = "在指定项目下创建新目录，支持嵌套结构（最多5层），项目ID和用户ID从header获取"
    )
    @ApiResponses(value = {
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "200",
            description = "目录创建成功",
            content = @Content(
                mediaType = "application/json",
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"Code\": 200,\n" +
                           "    \"Message\": \"目录创建成功\",\n" +
                           "    \"Data\": {\n" +
                           "        \"DirId\": \"550e8400-e29b-41d4-a716-446655440000\",\n" +
                           "        \"DirPath\": \"/dir-1\"\n" +
                           "    }\n" +
                           "}"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "请求参数错误"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "项目或父目录不存在"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "409", description = "目录名称已存在或嵌套层级超限"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    public ResponseEntity<ApiResponse<CreateDirectoryResponse>> createDirectory(
        @Parameter(description = "项目ID", required = true, example = "70072504-0da8-4638-8f53-4ca031da7604", in = ParameterIn.HEADER)
        @RequestHeader("project-id") String projectId,
        
        @Parameter(description = "用户ID", required = true, example = "user001", in = ParameterIn.HEADER)
        @RequestHeader("user-id") String userId,
        
        @io.swagger.v3.oas.annotations.parameters.RequestBody(
            description = "创建目录请求",
            required = true,
            content = @Content(
                schema = @Schema(implementation = CreateDirectoryRequest.class),
                                 examples = @ExampleObject(
                     value = "{\n" +
                            "    \"Name\": \"dir-1\",\n" +
                            "    \"ParentDirectoryId\": null\n" +
                            "}"
                 )
            )
        )
        @Valid @RequestBody CreateDirectoryRequest request) {
        
        try {
            // 验证必要参数
            if (projectId == null || projectId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(ApiResponse.error(400, "项目ID不能为空"));
            }
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(ApiResponse.error(400, "用户ID不能为空"));
            }
            
            String dirId = directoryService.createDirectory(projectId, userId, request.getName(), request.getParentDirectoryId());
            Directory directory = directoryService.getDirectoryById(dirId, projectId, userId);
            
            CreateDirectoryResponse data = new CreateDirectoryResponse(dirId, directory.getDirPath());
            return ResponseEntity.ok(ApiResponse.success("目录创建成功", data));
            
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
            
        } catch (RuntimeException e) {
            return ResponseEntity.status(409).body(ApiResponse.error(409, e.getMessage()));
            
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, "服务器内部错误: " + e.getMessage()));
        }
    }

    /**
     * 删除目录
     * DELETE /api/v1/directories/{dirId}
     */
    @DeleteMapping("/{dirId}")
    @Operation(summary = "删除目录", description = "删除目录（必须为空目录）")
    public ResponseEntity<ApiResponse<Void>> deleteDirectory(
            @PathVariable String dirId,
            @RequestHeader("project-id") String projectId,
            @RequestHeader("user-id") String userId) {
        try {
            directoryService.deleteDirectory(dirId, projectId, userId);
            return ResponseEntity.ok(ApiResponse.success("目录删除成功", null));
        } catch (RuntimeException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, "服务器内部错误"));
        }
    }
} 