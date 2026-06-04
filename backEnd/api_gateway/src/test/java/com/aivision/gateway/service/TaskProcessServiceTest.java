package com.aivision.gateway.service;

import com.aivision.gateway.model.Task;
import com.aivision.gateway.model.TaskFile;
import com.aivision.gateway.repository.TaskFileRepository;
import com.aivision.gateway.repository.TaskRepository;
import com.aivision.gateway.service.storage.StorageStrategy;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.ByteArrayInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class TaskProcessServiceTest {

    @Mock
    private TaskRepository taskRepository;

    @Mock
    private TaskFileRepository taskFileRepository;

    @Mock
    private AiServiceClient aiServiceClient;

    @Mock
    private StorageStrategy storageStrategy;

    @InjectMocks
    private TaskProcessService taskProcessService;

    @TempDir
    Path tempDir;

    private ObjectMapper objectMapper = new ObjectMapper();

    @BeforeEach
    void setUp() {
        // 将 resultBaseDir 设置为 JUnit 提供的临时目录
        ReflectionTestUtils.setField(taskProcessService, "resultBaseDir", tempDir.toString());
        ReflectionTestUtils.setField(taskProcessService, "inferenceInputBaseDir", tempDir.resolve("files").toString());
        ReflectionTestUtils.setField(taskProcessService, "storageType", "local");
    }

    @Test
    void processTaskAsync_ShouldProcessBatchesAndAppendJson() throws Exception {
        // Arrange
        String taskId = "task-123";
        Task task = new Task();
        task.setTaskId(taskId);
        task.setTaskName("Test Task");
        task.setStatus(Task.Status.PENDING);

        // 模拟 15 个文件 (BATCH_SIZE=10，所以会有 2 个批次)
        List<TaskFile> taskFiles = new ArrayList<>();
        for (int i = 0; i < 15; i++) {
            TaskFile tf = new TaskFile();
            tf.setTaskFileId("tf-" + i);
            tf.setTaskId(taskId);
            tf.setFileId("file-" + i);
            tf.setLogicalFilePath("/test/img_" + i + ".jpg");
            tf.setMinioFilePath("/test/img_" + i + ".jpg");
            tf.setStatus(TaskFile.Status.PENDING);
            taskFiles.add(tf);
        }

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId)).thenReturn(taskFiles);
        when(storageStrategy.exists(anyString())).thenReturn(true);
        when(storageStrategy.download(anyString())).thenReturn(new ByteArrayInputStream("image".getBytes()));

        // 模拟 Vision AI 返回结果
        when(aiServiceClient.callBatchVisionAi(anyList(), eq(taskId), any(), any(), any())).thenAnswer(invocation -> {
            List<String> paths = invocation.getArgument(0);
            Map<String, String> results = new HashMap<>();
            for (String path : paths) {
                results.put(path, "{\"mock\": \"result_for_" + path + "\"}");
            }
            return results;
        });

        // Act
        taskProcessService.processTaskAsync(taskId);

        // Assert
        // 1. 验证任务状态更新为 COMPLETED
        verify(taskRepository, atLeastOnce()).save(task);
        assertEquals(Task.Status.COMPLETED, task.getStatus());
        assertNotNull(task.getEndTime());
        
        // 2. 验证生成了结果文件
        String expectedFileName = "result_" + taskId + ".json";
        Path resultFile = tempDir.resolve(expectedFileName);
        assertTrue(Files.exists(resultFile), "结果文件应当存在");

        // 3. 验证文件内容是合法的 JSON 数组
        String content = new String(Files.readAllBytes(resultFile));
        System.out.println("Generated JSON Content: " + content);

        JsonNode rootNode = objectMapper.readTree(content);
        assertTrue(rootNode.isArray(), "结果文件应当是 JSON 数组");
        assertEquals(15, rootNode.size(), "结果数组应当包含 15 个元素");

        // 验证数组中的第一个元素
        JsonNode firstItem = rootNode.get(0);
        assertEquals("file-0", firstItem.get("fileId").asText());
        assertEquals("/test/img_0.jpg", firstItem.get("logicalPath").asText());
        assertNotNull(firstItem.get("visionResult"));
        
        // 验证文件状态更新
        verify(taskFileRepository, atLeast(2)).saveAll(anyList()); // 至少保存2次 (每个批次)
    }

    @Test
    void processTaskAsync_ShouldHandleEmptyFileList() {
        // Arrange
        String taskId = "task-empty";
        Task task = new Task();
        task.setTaskId(taskId);
        
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId)).thenReturn(new ArrayList<>());

        // Act
        taskProcessService.processTaskAsync(taskId);

        // Assert
        assertEquals(Task.Status.FAILED, task.getStatus());
        assertEquals("任务文件列表为空", task.getErrorMessage());
    }

    @Test
    void processTaskAsync_ShouldCleanStagedFilesAfterMinioTaskCompletes() throws Exception {
        String taskId = "task-minio-clean";
        ReflectionTestUtils.setField(taskProcessService, "storageType", "minio");
        Path taskInferenceResultDir = tempDir.resolve(taskId);
        Files.createDirectories(taskInferenceResultDir.resolve("prepared_inputs"));
        Files.writeString(taskInferenceResultDir.resolve("inference_results.json"), "{}");
        Files.writeString(taskInferenceResultDir.resolve("prepared_inputs/image.jpg"), "prepared");

        Task task = new Task();
        task.setTaskId(taskId);
        task.setTaskName("MinIO Task");
        task.setStatus(Task.Status.PENDING);

        TaskFile taskFile = createTaskFile(taskId, "tf-1", "/project/user/image.jpg");

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId)).thenReturn(List.of(taskFile));
        when(taskFileRepository.countByMinioFilePathAndStatusExcludingTask(
            anyString(), eq(TaskFile.Status.PROCESSING), eq(taskId))).thenReturn(0L);
        when(storageStrategy.exists("/project/user/image.jpg")).thenReturn(true);
        when(storageStrategy.download("/project/user/image.jpg"))
            .thenReturn(new ByteArrayInputStream("image".getBytes()));
        when(aiServiceClient.callBatchVisionAi(anyList(), eq(taskId), any(), any(), any())).thenAnswer(invocation -> {
            Map<String, String> results = new HashMap<>();
            results.put("/project/user/image.jpg", "{\"metadata\":{},\"results\":[]}");
            return results;
        });

        taskProcessService.processTaskAsync(taskId);

        assertEquals(Task.Status.COMPLETED, task.getStatus());
        assertFalse(Files.exists(tempDir.resolve("files/project/user/image.jpg")));
        assertFalse(Files.exists(taskInferenceResultDir));
        assertTrue(Files.exists(tempDir.resolve("result_" + taskId + ".json")));
    }

    @Test
    void processTaskAsync_ShouldCleanStagedFilesAfterMinioTaskFails() throws Exception {
        String taskId = "task-minio-fail-clean";
        ReflectionTestUtils.setField(taskProcessService, "storageType", "minio");
        Path taskInferenceResultDir = tempDir.resolve(taskId);
        Files.createDirectories(taskInferenceResultDir);
        Files.writeString(taskInferenceResultDir.resolve("progress.json"), "{}");

        Task task = new Task();
        task.setTaskId(taskId);
        task.setTaskName("Failing MinIO Task");
        task.setStatus(Task.Status.PENDING);

        TaskFile taskFile = createTaskFile(taskId, "tf-1", "/project/user/fail.jpg");

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId)).thenReturn(List.of(taskFile));
        when(taskFileRepository.countByMinioFilePathAndStatusExcludingTask(
            anyString(), eq(TaskFile.Status.PROCESSING), eq(taskId))).thenReturn(0L);
        when(storageStrategy.exists("/project/user/fail.jpg")).thenReturn(true);
        when(storageStrategy.download("/project/user/fail.jpg"))
            .thenReturn(new ByteArrayInputStream("image".getBytes()));
        when(aiServiceClient.callBatchVisionAi(anyList(), eq(taskId), any(), any(), any()))
            .thenThrow(new RuntimeException("AI unavailable"));

        taskProcessService.processTaskAsync(taskId);

        assertEquals(Task.Status.FAILED, task.getStatus());
        assertFalse(Files.exists(tempDir.resolve("files/project/user/fail.jpg")));
        assertFalse(Files.exists(taskInferenceResultDir));
        assertTrue(Files.exists(tempDir.resolve("result_" + taskId + ".json")));
    }

    @Test
    void processTaskAsync_ShouldCleanTaskInferenceResultDirectoryWhenStorageTypeIsLocal() throws Exception {
        String taskId = "task-local-clean-results";
        Path taskInferenceResultDir = tempDir.resolve(taskId);
        Files.createDirectories(taskInferenceResultDir.resolve("iqi_vis"));
        Files.writeString(taskInferenceResultDir.resolve("progress.json"), "{}");
        Files.writeString(taskInferenceResultDir.resolve("iqi_vis/vis.jpg"), "vis");

        Task task = new Task();
        task.setTaskId(taskId);
        task.setTaskName("Local Result Cleanup Task");
        task.setStatus(Task.Status.PENDING);

        TaskFile taskFile = createTaskFile(taskId, "tf-1", "/project/user/local-result.jpg");

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId)).thenReturn(List.of(taskFile));
        when(storageStrategy.exists("/project/user/local-result.jpg")).thenReturn(true);
        when(storageStrategy.download("/project/user/local-result.jpg"))
            .thenReturn(new ByteArrayInputStream("image".getBytes()));
        when(aiServiceClient.callBatchVisionAi(anyList(), eq(taskId), any(), any(), any())).thenAnswer(invocation -> {
            Map<String, String> results = new HashMap<>();
            results.put("/project/user/local-result.jpg", "{\"metadata\":{},\"results\":[]}");
            return results;
        });

        taskProcessService.processTaskAsync(taskId);

        assertEquals(Task.Status.COMPLETED, task.getStatus());
        assertTrue(Files.exists(tempDir.resolve("files/project/user/local-result.jpg")));
        assertFalse(Files.exists(taskInferenceResultDir));
        assertTrue(Files.exists(tempDir.resolve("result_" + taskId + ".json")));
    }

    @Test
    void processTaskAsync_ShouldKeepFilesWhenStorageTypeIsLocal() throws Exception {
        String taskId = "task-local-keep";

        Task task = new Task();
        task.setTaskId(taskId);
        task.setTaskName("Local Task");
        task.setStatus(Task.Status.PENDING);

        TaskFile taskFile = createTaskFile(taskId, "tf-1", "/project/user/local.jpg");

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId)).thenReturn(List.of(taskFile));
        when(storageStrategy.exists("/project/user/local.jpg")).thenReturn(true);
        when(storageStrategy.download("/project/user/local.jpg"))
            .thenReturn(new ByteArrayInputStream("image".getBytes()));
        when(aiServiceClient.callBatchVisionAi(anyList(), eq(taskId), any(), any(), any())).thenAnswer(invocation -> {
            Map<String, String> results = new HashMap<>();
            results.put("/project/user/local.jpg", "{\"metadata\":{},\"results\":[]}");
            return results;
        });

        taskProcessService.processTaskAsync(taskId);

        assertEquals(Task.Status.COMPLETED, task.getStatus());
        assertTrue(Files.exists(tempDir.resolve("files/project/user/local.jpg")));
        verify(taskFileRepository, never()).countByMinioFilePathAndStatusExcludingTask(anyString(), any(), anyString());
    }

    private TaskFile createTaskFile(String taskId, String taskFileId, String path) {
        TaskFile taskFile = new TaskFile();
        taskFile.setTaskFileId(taskFileId);
        taskFile.setTaskId(taskId);
        taskFile.setFileId("file-" + taskFileId);
        taskFile.setLogicalFilePath(path);
        taskFile.setMinioFilePath(path);
        taskFile.setStatus(TaskFile.Status.PENDING);
        return taskFile;
    }
}
