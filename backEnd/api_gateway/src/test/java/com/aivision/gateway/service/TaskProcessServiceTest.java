package com.aivision.gateway.service;

import com.aivision.gateway.model.Task;
import com.aivision.gateway.model.TaskFile;
import com.aivision.gateway.repository.TaskFileRepository;
import com.aivision.gateway.repository.TaskRepository;
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

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
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

    @InjectMocks
    private TaskProcessService taskProcessService;

    @TempDir
    Path tempDir;

    private ObjectMapper objectMapper = new ObjectMapper();

    @BeforeEach
    void setUp() {
        // 将 resultBaseDir 设置为 JUnit 提供的临时目录
        ReflectionTestUtils.setField(taskProcessService, "resultBaseDir", tempDir.toString());
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
            tf.setStatus(TaskFile.Status.PENDING);
            taskFiles.add(tf);
        }

        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task));
        when(taskFileRepository.findByTaskIdOrderByCreatedAtAsc(taskId)).thenReturn(taskFiles);

        // 模拟 Vision AI 返回结果
        when(aiServiceClient.callBatchVisionAi(anyList(), eq(taskId))).thenAnswer(invocation -> {
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
}

