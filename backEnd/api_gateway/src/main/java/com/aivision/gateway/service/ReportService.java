package com.aivision.gateway.service;

import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Service
@Transactional
public class ReportService {
    
    private static final Logger logger = LoggerFactory.getLogger(ReportService.class);
    private final ObjectMapper objectMapper = new ObjectMapper();
    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    
    @Autowired
    private ReportRepository reportRepository;
    
    @Autowired
    private TaskRepository taskRepository;
    
    @Autowired
    private TaskFileRepository taskFileRepository;
    
    @Autowired
    private ProjectRepository projectRepository;

    @Autowired
    private FileRepository fileRepository;

    @Autowired
    private DefectRecordRepository defectRecordRepository;

    /**
     * 获取报告列表
     */
    public List<Report> getReportsByProject(String projectId) {
        List<Report> reports = reportRepository.findByProjectIdOrderByCreatedAtDesc(projectId);
        // 填充任务名称
        for (Report r : reports) {
            taskRepository.findById(r.getTaskId()).ifPresent(t -> r.setTaskName(t.getTaskName()));
        }
        return reports;
    }

    /**
     * 根据报告ID获取详情
     */
    public Optional<Report> getReportById(String reportId) {
        Optional<Report> report = reportRepository.findById(reportId);
        report.ifPresent(r -> taskRepository.findById(r.getTaskId()).ifPresent(t -> r.setTaskName(t.getTaskName())));
        return report;
    }

    /**
     * 获取报告详情
     */
    public Optional<Report> getReportByTaskId(String taskId) {
        Optional<Report> report = reportRepository.findByTaskId(taskId);
        report.ifPresent(r -> taskRepository.findById(r.getTaskId()).ifPresent(t -> r.setTaskName(t.getTaskName())));
        return report;
    }

    /**
     * 获取报告关联的文件列表
     */
    public List<TaskFile> getReportFiles(String taskId, String status) {
        List<TaskFile> files = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId);
        
        // 填充文件名和缺陷记录
        for (TaskFile tf : files) {
            fileRepository.findById(tf.getFileId()).ifPresent(f -> tf.setFileName(f.getOriginalName()));
            tf.setDefectRecords(defectRecordRepository.findByTaskFileId(tf.getTaskFileId()));
        }

        if (status == null || status.isEmpty() || "all".equalsIgnoreCase(status)) {
            return files;
        }
        
        List<TaskFile> filtered = new ArrayList<>();
        for (TaskFile f : files) {
            boolean hasDefects = hasDefects(f);
            if ("has_defects".equalsIgnoreCase(status) && hasDefects) {
                filtered.add(f);
            } else if ("no_defects".equalsIgnoreCase(status) && !hasDefects) {
                filtered.add(f);
            }
        }
        return filtered;
    }

    private boolean hasDefects(TaskFile f) {
        String result = f.getManualResult() != null ? f.getManualResult() : f.getVisionResult();
        if (result == null) return false;
        try {
            JsonNode node = objectMapper.readTree(result);
            if (node.has("results") && node.get("results").isArray()) {
                for (JsonNode res : node.get("results")) {
                    String type = res.get("strName").asText();
                    if (!"normal".equalsIgnoreCase(type)) return true;
                }
            }
        } catch (Exception e) {
            logger.warn("解析检测结果失败: {}", e.getMessage());
        }
        return false;
    }

    /**
 * 更新单文件审核结果
 */
public void updateFileReview(String taskFileId, String manualResult, String plateQuality) {
    updateFileReview(taskFileId, manualResult, plateQuality, null, null, null, null);
}

/**
 * 更新单文件审核结果（包含底片信息）
 */
public void updateFileReview(String taskFileId, String manualResult, String plateQuality,
                              String weldId, String filmNumber, String filmDensity, String sensitivity) {
    TaskFile tf = taskFileRepository.findById(taskFileId)
        .orElseThrow(() -> new RuntimeException("任务文件不存在: " + taskFileId));
    
    Report report = reportRepository.findByTaskId(tf.getTaskId())
        .orElseThrow(() -> new RuntimeException("关联报告不存在"));
    
    if (report.getStatus() == Report.Status.ARCHIVED) {
        throw new RuntimeException("报告已归档，无法修改");
    }

    tf.setManualResult(manualResult);
    tf.setPlateQuality(plateQuality);
    
    // 更新底片信息字段
    if (weldId != null) tf.setWeldId(weldId);
    if (filmNumber != null) tf.setFilmNumber(filmNumber);
    if (filmDensity != null) tf.setFilmDensity(filmDensity);
    if (sensitivity != null) tf.setSensitivity(sensitivity);
    
    tf.setReviewStatus(TaskFile.ReviewStatus.CONFIRMED);
    taskFileRepository.save(tf);

    // 重新统计报告汇总信息
    updateReportStats(report.getTaskId());
}

    /**
     * 批量确认文件
     */
    public void batchConfirmFiles(List<String> taskFileIds) {
        if (taskFileIds == null || taskFileIds.isEmpty()) return;
        
        List<TaskFile> files = taskFileRepository.findAllById(taskFileIds);
        if (files.isEmpty()) return;
        
        String taskId = files.get(0).getTaskId();
        Report report = reportRepository.findByTaskId(taskId)
            .orElseThrow(() -> new RuntimeException("关联报告不存在"));
            
        if (report.getStatus() == Report.Status.ARCHIVED) {
            throw new RuntimeException("报告已归档，无法修改");
        }

        for (TaskFile tf : files) {
            tf.setReviewStatus(TaskFile.ReviewStatus.CONFIRMED);
        }
        taskFileRepository.saveAll(files);
        updateReportStats(taskId);
    }

    /**
     * 归档报告
     */
    public void archiveReport(String reportId, boolean archived) {
        Report report = reportRepository.findById(reportId)
            .orElseThrow(() -> new RuntimeException("报告不存在"));
        report.setStatus(archived ? Report.Status.ARCHIVED : Report.Status.COMPLETED);
        reportRepository.save(report);
    }

    /**
     * 当任务完成时生成或更新报告
     */
    public void generateReportForTask(String taskId) {
        Task task = taskRepository.findById(taskId)
            .orElseThrow(() -> new RuntimeException("任务不存在"));
        
        Optional<Report> existingReport = reportRepository.findByTaskId(taskId);
        Report report;
        
        if (existingReport.isPresent()) {
            // 更新已有报告
            report = existingReport.get();
            report.setProjectId(task.getProjectId());
            report.setUserId(task.getUserId());
            report.setReportName("检测报告_" + task.getTaskName());
            report.setTotalFiles(task.getTotalFiles());
            report.setStatus(Report.Status.PENDING);
            report.setUpdatedAt(LocalDateTime.now());
        } else {
            // 创建新报告
            report = new Report(
                UUID.randomUUID().toString(),
                taskId,
                task.getProjectId(),
                task.getUserId(),
                "检测报告_" + task.getTaskName()
            );
            report.setTotalFiles(task.getTotalFiles());
            report.setStatus(Report.Status.PENDING);
        }
        
        reportRepository.save(report);
        
        updateReportStats(taskId);
    }

    /**
     * 重新统计报告数据
     */
    public void updateReportStats(String taskId) {
        Report report = reportRepository.findByTaskId(taskId)
            .orElseThrow(() -> new RuntimeException("报告不存在"));
        
        List<TaskFile> files = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId);
        
        int confirmedCount = 0;
        int totalDefects = 0;
        int severeCount = 0;
        int normalCount = 0;

        for (TaskFile f : files) {
            if (f.getReviewStatus() == TaskFile.ReviewStatus.CONFIRMED) {
                confirmedCount++;
            }
            
            String resultStr = f.getManualResult() != null ? f.getManualResult() : f.getVisionResult();
            if (resultStr != null) {
                try {
                    JsonNode node = objectMapper.readTree(resultStr);
                    if (node.has("results") && node.get("results").isArray()) {
                        for (JsonNode res : node.get("results")) {
                            String type = res.get("strName").asText();
                            if ("normal".equalsIgnoreCase(type)) continue;
                            
                            totalDefects++;
                            if (isSevere(type)) {
                                severeCount++;
                            } else {
                                normalCount++;
                            }
                        }
                    }
                } catch (Exception e) {
                    logger.warn("统计缺陷失败: {}", e.getMessage());
                }
            }
        }

        report.setConfirmedFiles(confirmedCount);
        report.setTotalDefects(totalDefects);
        report.setSevereDefects(severeCount);
        report.setNormalDefects(normalCount);
        
        if (confirmedCount == report.getTotalFiles() && report.getTotalFiles() > 0) {
            report.setStatus(Report.Status.COMPLETED);
        }
        
        report.setUpdatedAt(LocalDateTime.now());
        reportRepository.save(report);
    }

    /**
     * 导出报告 (CSV 格式)
     */
    public String exportReport(String reportId) {
        Report report = reportRepository.findById(reportId)
            .orElseThrow(() -> new RuntimeException("报告不存在"));
        
        // 填充任务名称
        taskRepository.findById(report.getTaskId()).ifPresent(t -> report.setTaskName(t.getTaskName()));
        
        StringBuilder sb = new StringBuilder();
        // UTF-8 BOM for Excel
        sb.append("\uFEFF");
        sb.append("报告名称,检测任务,总文件数,已确认数,严重缺陷,一般缺陷,生成时间,状态\n");
        sb.append(String.format("\"%s\",\"%s\",%d,%d,%d,%d,\"%s\",\"%s\"\n\n",
            report.getReportName(),
            report.getTaskName() != null ? report.getTaskName() : "未知任务",
            report.getTotalFiles(),
            report.getConfirmedFiles(),
            report.getSevereDefects(),
            report.getNormalDefects(),
            report.getCreatedAt().format(DATE_FORMATTER),
            report.getStatus().toString()
        ));
        
        sb.append("详细检测结果\n");
        sb.append("文件名,审核状态,缺陷详情 (类型 | 位置 | 尺寸)\n");
        
        List<TaskFile> files = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(report.getTaskId());
        for (TaskFile tf : files) {
            String fileName = fileRepository.findById(tf.getFileId())
                .map(File::getOriginalName)
                .orElse("未知文件");
            
            String resultStr = tf.getManualResult() != null ? tf.getManualResult() : tf.getVisionResult();
            StringBuilder defects = new StringBuilder();
            if (resultStr != null) {
                try {
                    JsonNode node = objectMapper.readTree(resultStr);
                    if (node.has("results") && node.get("results").isArray()) {
                        for (JsonNode res : node.get("results")) {
                            String type = res.get("strName").asText();
                            if ("normal".equalsIgnoreCase(type)) continue;
                            
                            if (defects.length() > 0) defects.append("; ");
                            
                            defects.append("[").append(type);
                            
                            // 提取位置和尺寸 (从 vvContour 计算)
                            if (res.has("vvContour") && res.get("vvContour").isArray() && res.get("vvContour").size() > 0) {
                                int minX = Integer.MAX_VALUE, maxX = Integer.MIN_VALUE;
                                int minY = Integer.MAX_VALUE, maxY = Integer.MIN_VALUE;
                                boolean hasValidPoints = false;
                                
                                for (JsonNode point : res.get("vvContour")) {
                                    if (point.isArray() && point.size() >= 2) {
                                        int x = point.get(0).asInt();
                                        int y = point.get(1).asInt();
                                        minX = Math.min(minX, x);
                                        maxX = Math.max(maxX, x);
                                        minY = Math.min(minY, y);
                                        maxY = Math.max(maxY, y);
                                        hasValidPoints = true;
                                    }
                                }
                                
                                if (hasValidPoints) {
                                    defects.append(String.format(" | 位置:(%d, %d) | 尺寸:%dx%dpx", 
                                        minX, minY, (maxX - minX), (maxY - minY)));
                                }
                            }
                            
                            defects.append("]");
                        }
                    }
                } catch (Exception e) {
                    logger.warn("导出报告解析缺陷详情失败: {}", e.getMessage());
                }
            }
            
            sb.append(String.format("\"%s\",\"%s\",\"%s\"\n",
                fileName,
                tf.getReviewStatus(),
                defects.length() == 0 ? "无缺陷" : defects.toString()
            ));
        }
        
        return sb.toString();
    }

    private boolean isSevere(String defectType) {
        // 映射关系
        // SEVERE: crack, lack_of_fusion, incomplete_penetration
        // 支持英文和中文名称
        String t = defectType.toLowerCase();
        return t.contains("crack") || t.contains("unfused") || t.contains("incomplete_penetration") ||
               t.contains("裂纹") || t.contains("未熔合") || t.contains("未焊透");
    }
}

