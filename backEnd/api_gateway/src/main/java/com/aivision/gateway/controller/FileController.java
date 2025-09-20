package com.aivision.gateway.controller;

import com.aivision.gateway.model.ApiResponse;
import com.aivision.gateway.model.FileImageData;
import com.aivision.gateway.model.FilePreviewResponse;
import com.aivision.gateway.model.FileUploadResponse;
import com.aivision.gateway.service.FileService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/files")
@CrossOrigin(origins = "*")
@Tag(name = "文件管理", description = "AI Vision 文件上传管理相关接口 V1")
public class FileController {
    
    @Autowired
    private FileService fileService;
    
    /**
     * 多文件上传
     * POST /api/v1/files/upload
     */
    @PostMapping(value = "/upload", consumes = "multipart/form-data")
    @Operation(
        summary = "多文件上传",
        description = "上传多个图片文件到指定目录，支持jpg, jpeg, png, gif, bmp, webp格式，项目ID和用户ID从header获取"
    )
    @ApiResponses(value = {
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "200",
            description = "文件上传处理完成",
            content = @Content(
                mediaType = "application/json",
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"Code\": 200,\n" +
                           "    \"Message\": \"文件上传处理完成\",\n" +
                           "    \"Data\": {\n" +
                           "        \"SuccessCount\": 2,\n" +
                           "        \"FailedCount\": 0,\n" +
                           "        \"SuccessFiles\": [\n" +
                           "            {\n" +
                           "                \"FileId\": \"uuid-1\",\n" +
                           "                \"OriginalName\": \"image1.jpg\",\n" +
                           "                \"FileSize\": 1024000,\n" +
                           "                \"FilePath\": \"/ai-detection-files/project-id/user-id/dir-path/uuid-1.jpg\"\n" +
                           "            }\n" +
                           "        ],\n" +
                           "        \"FailedFiles\": []\n" +
                           "    }\n" +
                           "}"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "请求参数错误"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "413", description = "文件大小超过限制"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    public ResponseEntity<ApiResponse<FileUploadResponse>> uploadFiles(
        @Parameter(description = "项目ID", required = true, example = "70072504-0da8-4638-8f53-4ca031da7604", in = ParameterIn.HEADER)
        @RequestHeader("project-id") String projectId,
        
        @Parameter(description = "用户ID", required = true, example = "user001", in = ParameterIn.HEADER)
        @RequestHeader("user-id") String userId,
        
        @Parameter(description = "目录ID", required = true, example = "58ad6d46-756a-4491-905a-23352b282fe8", in = ParameterIn.HEADER)
        @RequestHeader("directory-id") String directoryId,
        
        @Parameter(
            description = "上传的文件（支持多文件）",
            required = true,
            content = @Content(mediaType = "multipart/form-data")
        )
        @RequestPart("File") MultipartFile[] files) {
        
        try {
            // 基础验证
            if (files == null || files.length == 0) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "请选择要上传的文件"));
            }
            
            if (projectId == null || projectId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "项目ID不能为空"));
            }
            
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "用户ID不能为空"));
            }
            
            if (directoryId == null || directoryId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "目录ID不能为空"));
            }
            
            // 处理文件上传
            FileUploadResponse uploadResponse = fileService.uploadFiles(projectId, userId, directoryId, files);
            
            String message;
            if (uploadResponse.getFailedCount() == 0) {
                message = "所有文件上传成功";
            } else if (uploadResponse.getSuccessCount() == 0) {
                message = "所有文件上传失败";
            } else {
                message = String.format("部分文件上传成功：成功 %d 个，失败 %d 个", 
                    uploadResponse.getSuccessCount(), uploadResponse.getFailedCount());
            }
            
            return ResponseEntity.ok(ApiResponse.success(message, uploadResponse));
            
        } catch (Exception e) {
            return ResponseEntity.status(500).body(
                ApiResponse.error(500, "服务器内部错误: " + e.getMessage()));
        }
    }
    
    /**
     * 图片预览 - 直接返回图片数据流
     * GET /api/v1/files/preview
     */
    @GetMapping("/preview")
    @Operation(
        summary = "图片预览",
        description = "根据文件ID直接返回图片的二进制数据流，设置正确的Content-Type头部，前端可直接在img标签的src属性中使用此API URL"
    )
    @ApiResponses(value = {
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "200",
            description = "图片数据返回成功",
            content = @Content(
                mediaType = "image/*",
                examples = @ExampleObject(
                    description = "直接返回图片二进制数据，Content-Type根据图片格式设置为image/jpeg、image/png等"
                )
            )
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "400", 
            description = "请求参数错误",
            content = @Content(mediaType = "application/json")
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "404", 
            description = "文件不存在或无权限访问",
            content = @Content(mediaType = "application/json")
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "500", 
            description = "服务器内部错误",
            content = @Content(mediaType = "application/json")
        )
    })
    public ResponseEntity<?> previewFile(
        @Parameter(description = "文件ID", required = true, example = "4852273e-b64a-44a7-b676-94b533c3ac23")
        @RequestParam("FileId") String fileId,
        
        @Parameter(description = "项目ID", required = true, example = "c6f4c9b9-a12e-4b11-9792-24993a69497a")
        @RequestParam("ProjectId") String projectId,
        
        @Parameter(description = "用户ID", required = true, example = "user001")
        @RequestParam("UseId") String userId) {
        
        try {
            // 基础验证
            if (projectId == null || projectId.trim().isEmpty()) {
                return ResponseEntity.badRequest()
                    .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                    .body(ApiResponse.error(400, "项目ID不能为空"));
            }
            
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest()
                    .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                    .body(ApiResponse.error(400, "用户ID不能为空"));
            }
            
            if (fileId == null || fileId.trim().isEmpty()) {
                return ResponseEntity.badRequest()
                    .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                    .body(ApiResponse.error(400, "文件ID不能为空"));
            }
            
            // 获取文件二进制数据和Content-Type
            var fileData = fileService.getFileImageData(fileId, projectId, userId);
            byte[] imageBytes = fileData.getImageBytes();
            String contentType = fileData.getContentType();
            
            // 直接返回图片数据流
            return ResponseEntity.ok()
                .contentType(org.springframework.http.MediaType.parseMediaType(contentType))
                .contentLength(imageBytes.length)
                .body(imageBytes);
            
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(404)
                .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                .body(ApiResponse.error(404, e.getMessage()));
                
        } catch (Exception e) {
            return ResponseEntity.status(500)
                .contentType(org.springframework.http.MediaType.APPLICATION_JSON)
                .body(ApiResponse.error(500, "服务器内部错误: " + e.getMessage()));
        }
    }
    
    /**
     * 删除文件
     * DELETE /api/v1/files/{fileId}
     */
    @DeleteMapping("/{fileId}")
    @Operation(
        summary = "删除文件",
        description = "根据文件ID删除指定文件，需要提供项目ID用于权限验证"
    )
    @ApiResponses(value = {
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "200",
            description = "文件删除成功",
            content = @Content(
                mediaType = "application/json",
                examples = @ExampleObject(
                    value = "{\n" +
                           "    \"Code\": 200,\n" +
                           "    \"Message\": \"文件删除成功\",\n" +
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
            description = "文件不存在或无权限访问"
        ),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
            responseCode = "500", 
            description = "服务器内部错误"
        )
    })
    public ResponseEntity<ApiResponse<Void>> deleteFile(
        @Parameter(description = "文件ID", required = true, example = "0409586a-b641-4d7c-84da-bb464c9bdc4c")
        @PathVariable String fileId,
        
        @Parameter(description = "项目ID", required = true, example = "c6f4c9b9-a12e-4b11-9792-24993a69497a")
        @RequestHeader("project-id") String projectId,
        
        @Parameter(description = "用户ID", required = true, example = "user001")
        @RequestHeader("user-id") String userId) {
        
        try {
            // 基础验证
            if (fileId == null || fileId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "文件ID不能为空"));
            }
            
            if (projectId == null || projectId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "项目ID不能为空"));
            }
            
            if (userId == null || userId.trim().isEmpty()) {
                return ResponseEntity.badRequest().body(
                    ApiResponse.error(400, "用户ID不能为空"));
            }
            
            // 调用服务删除文件
            boolean deleted = fileService.deleteFile(fileId, projectId, userId);
            
            if (deleted) {
                return ResponseEntity.ok(ApiResponse.success("文件删除成功", null));
            } else {
                return ResponseEntity.status(404).body(
                    ApiResponse.error(404, "文件不存在或无权限访问"));
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