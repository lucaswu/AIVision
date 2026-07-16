package com.aivision.gateway.service;

import com.aivision.gateway.model.Task;
import com.aivision.gateway.repository.TaskRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;

@Service
public class TaskResultCleanupService {

    private static final Logger logger = LoggerFactory.getLogger(TaskResultCleanupService.class);
    private static final Pattern TASK_REPORT_FILE_PATTERN = Pattern.compile("^result_(.+)\\.json$");
    private static final Pattern UUID_DIR_PATTERN = Pattern.compile(
        "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    );
    private static final Set<String> RESERVED_DIRECTORIES = Set.of("ocr_debug", "__warmup__");
    private static final Set<String> TASK_RESULT_MARKER_FILES = Set.of(
        "input_files.txt",
        "progress.json",
        "inference_results.json",
        "iqi_grade_results.json"
    );

    @Autowired
    private TaskRepository taskRepository;

    @Value("${storage.local.result-dir:/app/data/results}")
    private String resultBaseDir;

    @Value("${storage.local.result-cleanup.enabled:true}")
    private boolean cleanupEnabled;

    @Value("${storage.local.result-cleanup.retention-days:3}")
    private int retentionDays;

    @Scheduled(
        initialDelayString = "${storage.local.result-cleanup.initial-delay-ms:60000}",
        fixedDelayString = "${storage.local.result-cleanup.fixed-delay-ms:86400000}"
    )
    public void cleanupExpiredTaskResults() {
        if (!cleanupEnabled) {
            return;
        }
        if (retentionDays <= 0) {
            logger.warn("任务结果定时清理已跳过：retention-days 必须大于 0，当前值={}", retentionDays);
            return;
        }

        Path basePath = Paths.get(resultBaseDir).normalize().toAbsolutePath();
        if (!Files.isDirectory(basePath)) {
            return;
        }

        Instant cutoff = Instant.now().minus(retentionDays, ChronoUnit.DAYS);
        int deletedFiles = 0;
        int deletedDirectories = 0;
        int skippedActive = 0;
        int skippedOther = 0;

        try (DirectoryStream<Path> entries = Files.newDirectoryStream(basePath)) {
            for (Path entry : entries) {
                Path normalizedEntry = entry.normalize().toAbsolutePath();
                if (!normalizedEntry.startsWith(basePath) || normalizedEntry.equals(basePath)) {
                    skippedOther++;
                    continue;
                }

                try {
                    if (Files.isRegularFile(normalizedEntry)) {
                        String taskId = extractTaskIdFromReportFile(normalizedEntry);
                        if (taskId == null || !isExpired(normalizedEntry, cutoff)) {
                            continue;
                        }
                        if (isActiveTask(taskId)) {
                            skippedActive++;
                            continue;
                        }
                        Files.deleteIfExists(normalizedEntry);
                        deletedFiles++;
                    } else if (Files.isDirectory(normalizedEntry)) {
                        String dirName = normalizedEntry.getFileName().toString();
                        if (!isTaskResultDirectory(normalizedEntry, dirName) || !isDirectoryExpired(normalizedEntry, cutoff)) {
                            continue;
                        }
                        if (isActiveTask(dirName)) {
                            skippedActive++;
                            continue;
                        }
                        deleteDirectoryRecursively(normalizedEntry);
                        deletedDirectories++;
                    }
                } catch (Exception e) {
                    skippedOther++;
                    logger.warn("清理过期任务结果失败: path={}, error={}", normalizedEntry, e.getMessage());
                }
            }
        } catch (IOException e) {
            logger.warn("扫描任务结果目录失败: path={}, error={}", basePath, e.getMessage());
            return;
        }

        if (deletedFiles > 0 || deletedDirectories > 0 || skippedActive > 0) {
            logger.info(
                "任务结果定时清理完成: baseDir={}, retentionDays={}, deletedFiles={}, deletedDirectories={}, skippedActive={}, skippedOther={}",
                basePath, retentionDays, deletedFiles, deletedDirectories, skippedActive, skippedOther
            );
        }
    }

    private String extractTaskIdFromReportFile(Path file) {
        Matcher matcher = TASK_REPORT_FILE_PATTERN.matcher(file.getFileName().toString());
        return matcher.matches() ? matcher.group(1) : null;
    }

    private boolean isTaskResultDirectory(Path directory, String dirName) {
        if (RESERVED_DIRECTORIES.contains(dirName)) {
            return false;
        }
        if (UUID_DIR_PATTERN.matcher(dirName).matches()) {
            return true;
        }
        for (String markerFile : TASK_RESULT_MARKER_FILES) {
            if (Files.isRegularFile(directory.resolve(markerFile))) {
                return true;
            }
        }
        return false;
    }

    private boolean isExpired(Path path, Instant cutoff) throws IOException {
        return Files.getLastModifiedTime(path).toInstant().isBefore(cutoff);
    }

    private boolean isDirectoryExpired(Path directory, Instant cutoff) throws IOException {
        Instant latestModified = Files.getLastModifiedTime(directory).toInstant();
        try (Stream<Path> paths = Files.walk(directory)) {
            Optional<Instant> latestChildModified = paths
                .map(path -> {
                    try {
                        return Files.getLastModifiedTime(path).toInstant();
                    } catch (IOException e) {
                        return Instant.now();
                    }
                })
                .max(Comparator.naturalOrder());
            if (latestChildModified.isPresent()) {
                latestModified = latestChildModified.get();
            }
        }
        return latestModified.isBefore(cutoff);
    }

    private boolean isActiveTask(String taskId) {
        try {
            Optional<Task> taskOpt = taskRepository.findById(taskId);
            if (taskOpt.isEmpty()) {
                return false;
            }
            Task.Status status = taskOpt.get().getStatus();
            return status == Task.Status.PENDING || status == Task.Status.PROCESSING;
        } catch (Exception e) {
            logger.warn("检查任务状态失败，为避免误删将保留结果: taskId={}, error={}", taskId, e.getMessage());
            return true;
        }
    }

    private void deleteDirectoryRecursively(Path directory) throws IOException {
        try (Stream<Path> paths = Files.walk(directory)) {
            List<Path> pathsToDelete = paths
                .sorted(Comparator.reverseOrder())
                .collect(Collectors.toList());
            for (Path path : pathsToDelete) {
                Files.deleteIfExists(path);
            }
        }
    }
}
