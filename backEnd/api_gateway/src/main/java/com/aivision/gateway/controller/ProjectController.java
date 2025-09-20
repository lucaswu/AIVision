package com.aivision.gateway.controller;

import com.aivision.gateway.model.*;
import com.aivision.gateway.service.ProjectService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
// import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/api/v1/projects")
@CrossOrigin(origins = "*")
@Tag(name = "项目管理", description = "AI Vision 项目管理相关接口 V1")
public class ProjectController {
    
    @Autowired
    private ProjectService projectService;
    
    /**
     * 创建项目
     * POST /api/v1/projects/create
     */
    @PostMapping("/create")
    @Operation(
        summary = "创建项目",
        description = "创建新的 AI 检测项目，需要传入项目名称和描述信息，用户ID从header获取"
    )
    @ApiResponses(value = {
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "200",
            description = "项目创建成功",
            content = @Content(
                mediaType = "application/json",
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"Code\": 200,\n" +
                           "    \"Message\": \"项目创建成功\",\n" +
                           "    \"Data\": {\n" +
                           "        \"ProjectId\": \"550e8400-e29b-41d4-a716-446655440000\"\n" +
                           "    }\n" +
                           "}"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "请求参数错误"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "409", description = "项目名称已存在"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    public ResponseEntity<ApiResponse<CreateProjectResponse>> createProject(
        @Parameter(description = "用户ID", required = true, example = "user001", in = ParameterIn.HEADER)
        @RequestHeader("user-id") String userId,
        @io.swagger.v3.oas.annotations.parameters.RequestBody(
            description = "创建项目请求",
            required = true,
            content = @Content(
                schema = @Schema(implementation = CreateProjectRequest.class),
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"ProjectName\": \"我的AI检测项目\",\n" +
                           "    \"Description\": \"PCB板自动化检测项目，用于电路板缺陷识别\"\n" +
                           "}"
                )
            )
        )
        @Valid @RequestBody CreateProjectRequest request) {
        
        try {
            // 验证 userId 不能为空
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(ApiResponse.error(400, "用户ID不能为空"));
            }
            
            String projectId = projectService.createProject(userId, request.getProjectName(), request.getDescription());
            CreateProjectResponse data = new CreateProjectResponse(projectId);
            return ResponseEntity.ok(ApiResponse.success("项目创建成功", data));
            
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ApiResponse.error(400, e.getMessage()));
            
        } catch (RuntimeException e) {
            return ResponseEntity.status(409).body(ApiResponse.error(409, e.getMessage()));
            
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, "服务器内部错误: " + e.getMessage()));
        }
    }
    
    /**
     * 获取项目列表
     * GET /api/v1/projects/list
     */
    @GetMapping("/list")
    @Operation(
        summary = "获取项目列表",
        description = "根据用户ID获取项目列表，返回该用户下所有项目信息，用户ID从header获取"
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
                           "    \"Data\": [\n" +
                           "        {\n" +
                           "            \"Id\": \"1\",\n" +
                           "            \"Name\": \"检测项目1\",\n" +
                           "            \"Description\": \"PCB板自动化检测项目，用于电路板缺陷识别\",\n" +
                           "            \"CreateTime\": \"2023-10-01 14:30:22\",\n" +
                           "            \"UpdateTime\": \"2023-10-15 09:15:18\",\n" +
                           "            \"FileCount\": 0,\n" +
                           "            \"TaskCount\": 0\n" +
                           "        }\n" +
                           "    ],\n" +
                           "    \"Total\": 1\n" +
                           "}"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "用户ID不能为空"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    public ResponseEntity<ApiResponse<List<ProjectListItem>>> getProjectList(
            @Parameter(description = "用户ID", required = true, example = "user001", in = ParameterIn.HEADER)
            @RequestHeader("user-id") String userId) {
        
        try {
            // 验证 UserId 不能为空
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "用户ID不能为空")
                );
            }
            
            // 获取用户所有项目
            List<ProjectListItem> projects = projectService.getProjectListByUserId(userId);
            
            return ResponseEntity.ok(
                ApiResponse.success("获取成功", projects, projects.size())
            );
            
        } catch (Exception e) {
            return ResponseEntity.status(500).body(
                ApiResponse.error(500, "服务器内部错误: " + e.getMessage())
            );
        }
    }
    
    /**
     * 获取项目文件树
     * GET /api/v1/projects/{project_id}/files
     */
    @GetMapping("/{project_id}/files")
    @Operation(
        summary = "获取项目文件树",
        description = "根据项目ID获取所有相关图片和目录信息，返回层级化的文件树结构，需要验证用户权限"
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
                           "    \"Data\": [\n" +
                           "        {\n" +
                           "            \"Id\": \"dir_3\",\n" +
                           "            \"Name\": \"焊接图像\",\n" +
                           "            \"Type\": \"directory\",\n" +
                           "            \"ProjectId\": \"1\",\n" +
                           "            \"UserId\": \"user001\",\n" +
                           "            \"Children\": [\n" +
                           "                {\n" +
                           "                    \"Id\": \"7\",\n" +
                           "                    \"Name\": \"Solder_001.jpg\",\n" +
                           "                    \"Type\": \"file\",\n" +
                           "                    \"ProjectId\": \"1\",\n" +
                           "                    \"UserId\": \"user001\",\n" +
                           "                    \"FileType\": \"jpg\",\n" +
                           "                    \"Size\": \"2000000\",\n" +
                           "                    \"UploadDate\": \"2023-10-15 14:36\"\n" +
                           "                }\n" +
                           "            ]\n" +
                           "        }\n" +
                           "    ]\n" +
                           "}"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "请求参数错误"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "403", description = "无权限访问该项目"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "项目不存在"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    public ResponseEntity<ApiResponse<List<ProjectFileTreeResponse.TreeNode>>> getProjectFiles(
            @Parameter(description = "项目ID", required = true, example = "70072504-0da8-4638-8f53-4ca031da7604")
            @PathVariable("project_id") String projectId,
            @Parameter(description = "用户ID", required = true, example = "user001", in = ParameterIn.HEADER)
            @RequestHeader("user-id") String userId) {
        
        try {
            // 验证参数不能为空
            if (projectId == null || projectId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "项目ID不能为空")
                );
            }
            
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "用户ID不能为空")
                );
            }
            
            // 获取项目文件树（包含权限验证）
            ProjectFileTreeResult result = projectService.getProjectFileTree(projectId, userId);
            
            return ResponseEntity.ok(
                ApiResponse.success("获取成功", result.getFileTree(), result.getTotalFileCount())
            );
            
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(
                ApiResponse.error(400, e.getMessage())
            );
            
        } catch (RuntimeException e) {
            if (e.getMessage().contains("项目不存在")) {
                return ResponseEntity.status(404).body(
                    ApiResponse.error(404, e.getMessage())
                );
            } else if (e.getMessage().contains("无权限访问")) {
                return ResponseEntity.status(403).body(
                    ApiResponse.error(403, e.getMessage())
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
} 