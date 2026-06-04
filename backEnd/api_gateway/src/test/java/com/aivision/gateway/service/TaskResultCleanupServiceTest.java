package com.aivision.gateway.service;

import com.aivision.gateway.model.Task;
import com.aivision.gateway.repository.TaskRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TaskResultCleanupServiceTest {

    @Mock
    private TaskRepository taskRepository;

    @InjectMocks
    private TaskResultCleanupService cleanupService;

    @TempDir
    Path tempDir;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(cleanupService, "resultBaseDir", tempDir.toString());
        ReflectionTestUtils.setField(cleanupService, "cleanupEnabled", true);
        ReflectionTestUtils.setField(cleanupService, "retentionDays", 7);
    }

    @Test
    void cleanupExpiredTaskResults_ShouldDeleteOnlyExpiredTaskResults() throws Exception {
        String expiredTaskId = "11111111-1111-1111-1111-111111111111";
        String freshTaskId = "22222222-2222-2222-2222-222222222222";
        String activeTaskId = "33333333-3333-3333-3333-333333333333";

        Path expiredReport = tempDir.resolve("result_" + expiredTaskId + ".json");
        Path freshReport = tempDir.resolve("result_" + freshTaskId + ".json");
        Path activeReport = tempDir.resolve("result_" + activeTaskId + ".json");
        Path otherFile = tempDir.resolve("notes.json");
        Files.writeString(expiredReport, "[]");
        Files.writeString(freshReport, "[]");
        Files.writeString(activeReport, "[]");
        Files.writeString(otherFile, "{}");

        Path expiredTaskDir = createTaskResultDir(expiredTaskId);
        Path freshTaskDir = createTaskResultDir(freshTaskId);
        Path activeTaskDir = createTaskResultDir(activeTaskId);
        Path ocrDebugDir = tempDir.resolve("ocr_debug");
        Files.createDirectories(ocrDebugDir);
        Files.writeString(ocrDebugDir.resolve("old.png"), "debug");
        Path warmupDir = tempDir.resolve("__warmup__");
        Files.createDirectories(warmupDir);
        Files.writeString(warmupDir.resolve("input_files.txt"), "");

        markOld(expiredReport);
        markOld(activeReport);
        markOld(expiredTaskDir);
        markOld(activeTaskDir);
        markOld(ocrDebugDir);
        markOld(warmupDir);

        Task activeTask = new Task();
        activeTask.setTaskId(activeTaskId);
        activeTask.setStatus(Task.Status.PROCESSING);
        when(taskRepository.findById(expiredTaskId)).thenReturn(Optional.empty());
        when(taskRepository.findById(activeTaskId)).thenReturn(Optional.of(activeTask));

        cleanupService.cleanupExpiredTaskResults();

        assertFalse(Files.exists(expiredReport));
        assertFalse(Files.exists(expiredTaskDir));
        assertTrue(Files.exists(freshReport));
        assertTrue(Files.exists(freshTaskDir));
        assertTrue(Files.exists(activeReport));
        assertTrue(Files.exists(activeTaskDir));
        assertTrue(Files.exists(otherFile));
        assertTrue(Files.exists(ocrDebugDir));
        assertTrue(Files.exists(warmupDir));
    }

    @Test
    void cleanupExpiredTaskResults_ShouldSkipWhenDisabled() throws Exception {
        ReflectionTestUtils.setField(cleanupService, "cleanupEnabled", false);

        String taskId = "44444444-4444-4444-4444-444444444444";
        Path report = tempDir.resolve("result_" + taskId + ".json");
        Files.writeString(report, "[]");
        markOld(report);

        cleanupService.cleanupExpiredTaskResults();

        assertTrue(Files.exists(report));
    }

    private Path createTaskResultDir(String taskId) throws Exception {
        Path taskDir = tempDir.resolve(taskId);
        Files.createDirectories(taskDir.resolve("prepared_inputs"));
        Files.writeString(taskDir.resolve("input_files.txt"), "/app/data/files/example.jpg");
        Files.writeString(taskDir.resolve("prepared_inputs/example.jpg"), "image");
        return taskDir;
    }

    private void markOld(Path path) throws Exception {
        FileTime oldTime = FileTime.from(Instant.now().minus(8, ChronoUnit.DAYS));
        Files.setLastModifiedTime(path, oldTime);
        if (Files.isDirectory(path)) {
            try (var children = Files.walk(path)) {
                children.forEach(child -> {
                    try {
                        Files.setLastModifiedTime(child, oldTime);
                    } catch (Exception ignored) {
                    }
                });
            }
        }
    }
}
