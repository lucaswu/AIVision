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

    @Autowired
    private WeldJointRepository weldJointRepository;

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
        
        // 填充文件名、缺陷记录和焊口列表
        for (TaskFile tf : files) {
            fileRepository.findById(tf.getFileId()).ifPresent(f -> tf.setFileName(f.getOriginalName()));
            tf.setDefectRecords(defectRecordRepository.findByTaskFileId(tf.getTaskFileId()));
            tf.setWeldJoints(weldJointRepository.findByTaskFileIdOrderBySortOrderAsc(tf.getTaskFileId()));
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
    updateFileReview(taskFileId, manualResult, plateQuality,
        null, null, null, null, null, null, null, null);
}

/**
 * 更新单文件审核结果（包含底片信息）
 */
public void updateFileReview(String taskFileId, String manualResult, String plateQuality,
                              String filmPixelValue, String resolution, String specification, String inspectionDate,
                              String filmNumber, String filmDensity, String sensitivity,
                              String normalizedSnr) {
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
    if (filmPixelValue != null) tf.setFilmPixelValue(filmPixelValue);
    if (resolution != null) tf.setResolution(resolution);
    if (specification != null) tf.setSpecification(specification);
    if (inspectionDate != null) tf.setInspectionDate(inspectionDate);
    if (filmNumber != null) tf.setFilmNumber(filmNumber);
    if (filmDensity != null) tf.setFilmDensity(filmDensity);
    if (sensitivity != null) tf.setSensitivity(sensitivity);
    if (normalizedSnr != null) tf.setNormalizedSnr(normalizedSnr);
    
    tf.setReviewStatus(TaskFile.ReviewStatus.CONFIRMED);
    taskFileRepository.save(tf);

    // 重新统计报告汇总信息
    updateReportStats(report.getTaskId());
}

    /**
     * 更新文件定位信息（手动调整椭圆/原点）
     */
    public void updateFileLocation(String taskFileId, String weldLocation, String defectPosition) {
        TaskFile tf = taskFileRepository.findById(taskFileId)
            .orElseThrow(() -> new RuntimeException("任务文件不存在: " + taskFileId));
        if (weldLocation != null) tf.setWeldLocation(weldLocation);
        if (defectPosition != null) tf.setDefectPosition(defectPosition);
        taskFileRepository.save(tf);
    }

    /**
     * 更新用户手动矫正方向（相对原始图片的绝对方向，UserRotation/UserFlip 同时为 null 表示清除，回退 AI 矫正）
     */
    public void updateFileOrientation(String taskFileId, Integer userRotation, Boolean userFlip) {
        TaskFile tf = taskFileRepository.findById(taskFileId)
            .orElseThrow(() -> new RuntimeException("任务文件不存在: " + taskFileId));
        tf.setUserRotation(userRotation);
        tf.setUserFlip(userFlip);
        taskFileRepository.save(tf);
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
        
        // 详细检测结果与页面（ReportPreviewPage）同源：
        // 文件信息来自 TaskFile 持久化字段，缺陷明细来自 defect_record 表
        //（含用户在编辑页确认/修改的类型、位置、尺寸、等级、备注，位置为显示坐标系语义）
        List<TaskFile> files = taskFileRepository.findByTaskIdOrderByCreatedAtAsc(report.getTaskId());

        StringBuilder fileRows = new StringBuilder();
        StringBuilder defectRows = new StringBuilder();

        for (TaskFile tf : files) {
            String fileName = fileRepository.findById(tf.getFileId())
                .map(File::getOriginalName)
                .orElse("未知文件");
            String reviewStatus = TaskFile.ReviewStatus.CONFIRMED.equals(tf.getReviewStatus()) ? "已确认" : "待审核";

            List<WeldJoint> namedJoints = new ArrayList<>();
            for (WeldJoint joint : weldJointRepository.findByTaskFileIdOrderBySortOrderAsc(tf.getTaskFileId())) {
                if (joint.getWeldNo() != null && !joint.getWeldNo().trim().isEmpty()) {
                    namedJoints.add(joint);
                }
            }
            StringBuilder weldNos = new StringBuilder();
            for (WeldJoint joint : namedJoints) {
                if (weldNos.length() > 0) weldNos.append("、");
                weldNos.append(joint.getWeldNo());
            }

            List<DefectRecord> defects = defectRecordRepository.findByTaskFileId(tf.getTaskFileId());
            int[] dispSize = getDisplaySize(tf);

            fileRows.append(String.format("\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",%d\n",
                csv(fileName),
                reviewStatus,
                dispSize[0] + "×" + dispSize[1],
                tf.getProcessingEndTime() != null ? tf.getProcessingEndTime().format(DATE_FORMATTER) : "-",
                csv(tf.getFilmPixelValue()),
                csv(tf.getResolution()),
                csv(tf.getSpecification()),
                csv(tf.getInspectionDate()),
                csv(weldNos.toString()),
                csv(tf.getFilmNumber()),
                csv(tf.getFilmDensity()),
                csv(tf.getSensitivity()),
                csv(tf.getNormalizedSnr()),
                defects.size()
            ));

            for (DefectRecord d : defects) {
                // 与页面分组规则一致：匹配已命名焊口显示焊口编号；
                // 存在已命名焊口但未匹配的记为"未分组"；无已命名焊口则不分组
                String weldNo = "-";
                if (!namedJoints.isEmpty()) {
                    weldNo = "未分组";
                    for (WeldJoint joint : namedJoints) {
                        if (joint.getWeldJointId().equals(d.getWeldJointId())) {
                            weldNo = joint.getWeldNo();
                            break;
                        }
                    }
                }
                String defectName = d.getDefectName() != null ? d.getDefectName() : "";
                defectRows.append(String.format("\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\"\n",
                    csv(fileName),
                    csv(weldNo),
                    csv(defectName),
                    isSevere(defectName) ? "严重" : "一般",
                    csv(d.getPosition()),
                    csv(d.getSize()),
                    csv(d.getGrade()),
                    csv(d.getRemark())
                ));
            }
        }

        sb.append("文件信息\n");
        sb.append("文件名,审核状态,尺寸,检测时间,底片像素值,双丝分辨率,规格,检验日期,焊口编号,片号,黑度,灵敏度,区域归一化信噪比,缺陷数\n");
        sb.append(fileRows);
        sb.append("\n缺陷明细\n");
        sb.append("文件名,焊口,缺陷类型,严重程度,位置,尺寸,等级,备注\n");
        sb.append(defectRows.length() == 0 ? "未检测到缺陷\n" : defectRows);

        return sb.toString();
    }

    /** CSV 单元格转义：空值显示 "-"，双引号转义为两个双引号 */
    private static String csv(String value) {
        if (value == null || value.trim().isEmpty()) return "-";
        return value.replace("\"", "\"\"");
    }

    /**
     * 与前端 ReportPreviewPage 一致的"显示画幅"：
     * VisionResult metadata 记录的是矫正后画幅；先还原原图画幅（矫正旋转 90/270 时宽高互换），
     * 再按显示方向（用户矫正优先，AI 矫正兜底）换算。两次互换仅在旋转奇偶不同时产生净互换。
     */
    private int[] getDisplaySize(TaskFile tf) {
        int w = 1920, h = 1080;
        try {
            JsonNode meta = objectMapper.readTree(
                tf.getVisionResult() != null ? tf.getVisionResult() : "{}").path("metadata");
            if (meta.has("width")) w = meta.get("width").asInt(w);
            if (meta.has("height")) h = meta.get("height").asInt(h);
        } catch (Exception e) {
            logger.warn("导出报告解析图像画幅失败: {}", e.getMessage());
        }
        int corrRotation = tf.getCorrectionRotation() != null ? tf.getCorrectionRotation() : 0;
        boolean hasUserOrientation = tf.getUserRotation() != null || tf.getUserFlip() != null;
        int dispRotation = hasUserOrientation
            ? (tf.getUserRotation() != null ? tf.getUserRotation() : 0)
            : corrRotation;
        boolean corrSwapped = Math.floorMod(corrRotation, 180) != 0;
        boolean dispSwapped = Math.floorMod(dispRotation, 180) != 0;
        if (corrSwapped != dispSwapped) {
            int tmp = w; w = h; h = tmp;
        }
        return new int[]{w, h};
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
