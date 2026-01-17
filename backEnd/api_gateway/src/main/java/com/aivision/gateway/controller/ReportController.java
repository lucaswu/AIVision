package com.aivision.gateway.controller;

import com.aivision.gateway.model.*;
import com.aivision.gateway.service.ReportService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/reports")
@CrossOrigin(origins = "*")
@Tag(name = "报告管理", description = "AI Vision 检测报告管理及审核相关接口")
public class ReportController {
    
    @Autowired
    private ReportService reportService;

    private static final DateTimeFormatter FILE_DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy_MM_dd_HH_mm");
    
    @GetMapping("/list")
    @Operation(summary = "获取报告列表")
    public ResponseEntity<ApiResponse<List<Report>>> getReports(
        @RequestHeader("project-id") String projectId) {
        try {
            List<Report> reports = reportService.getReportsByProject(projectId);
            return ResponseEntity.ok(ApiResponse.success("获取成功", reports));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @GetMapping("/{reportId}/download")
    @Operation(summary = "导出/下载报告")
    public ResponseEntity<byte[]> downloadReport(@PathVariable String reportId) {
        try {
            Report report = reportService.getReportById(reportId)
                .orElseThrow(() -> new RuntimeException("报告不存在"));
            
            String csvContent = reportService.exportReport(reportId);
            byte[] bytes = csvContent.getBytes(StandardCharsets.UTF_8);
            
            // 构建人性化的文件名: [任务名]的检测报告_[时间].csv
            String taskName = report.getTaskName() != null ? report.getTaskName() : "未知任务";
            String timestamp = report.getCreatedAt().format(FILE_DATE_FORMATTER);
            String fileName = String.format("%s的检测报告_%s.csv", taskName, timestamp);
            
            // 对文件名进行编码，防止中文乱码
            String encodedFileName = URLEncoder.encode(fileName, StandardCharsets.UTF_8.toString()).replace("+", "%20");
            
            return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename*=UTF-8''" + encodedFileName)
                .contentType(MediaType.parseMediaType("text/csv"))
                .body(bytes);
        } catch (Exception e) {
            return ResponseEntity.status(500).body(null);
        }
    }

    @GetMapping("/{taskId}/detail")
    @Operation(summary = "获取报告详情")
    public ResponseEntity<ApiResponse<Report>> getReportDetail(
        @PathVariable String taskId) {
        try {
            return reportService.getReportByTaskId(taskId)
                .map(r -> ResponseEntity.ok(ApiResponse.success("获取成功", r)))
                .orElse(ResponseEntity.status(404).body(ApiResponse.error(404, "报告不存在")));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @GetMapping("/{taskId}/files")
    @Operation(summary = "获取报告关联的文件列表 (用于审核/预览)")
    public ResponseEntity<ApiResponse<List<TaskFile>>> getReportFiles(
        @PathVariable String taskId,
        @RequestParam(value = "status", required = false, defaultValue = "all") String status) {
        try {
            List<TaskFile> files = reportService.getReportFiles(taskId, status);
            return ResponseEntity.ok(ApiResponse.success("获取成功", files));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PutMapping("/files/{taskFileId}/review")
    @Operation(summary = "提交单文件审核结果")
    public ResponseEntity<ApiResponse<Void>> reviewFile(
        @PathVariable String taskFileId,
        @RequestBody Map<String, Object> body) {
        try {
            String manualResult = (String) body.get("ManualResult");
            String plateQuality = (String) body.get("PlateQuality");
            // 新增：底片信息字段
            String weldId = (String) body.get("WeldId");
            String filmNumber = (String) body.get("FilmNumber");
            String filmDensity = (String) body.get("FilmDensity");
            String sensitivity = (String) body.get("Sensitivity");
            
            reportService.updateFileReview(taskFileId, manualResult, plateQuality,
                weldId, filmNumber, filmDensity, sensitivity);
            return ResponseEntity.ok(ApiResponse.success("保存成功", null));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PostMapping("/files/batch-confirm")
    @Operation(summary = "批量确认文件")
    public ResponseEntity<ApiResponse<Void>> batchConfirm(
        @RequestBody List<String> taskFileIds) {
        try {
            reportService.batchConfirmFiles(taskFileIds);
            return ResponseEntity.ok(ApiResponse.success("批量确认成功", null));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }

    @PutMapping("/{reportId}/archive")
    @Operation(summary = "归档/取消归档报告")
    public ResponseEntity<ApiResponse<Void>> archiveReport(
        @PathVariable String reportId,
        @RequestParam boolean archived) {
        try {
            reportService.archiveReport(reportId, archived);
            return ResponseEntity.ok(ApiResponse.success(archived ? "归档成功" : "已取消归档", null));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }
}


