package com.aivision.gateway.service;

import com.aivision.gateway.model.*;
import com.aivision.gateway.repository.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class TaskServiceTest {

    @Mock
    private TaskRepository taskRepository;

    @Mock
    private TaskFileRepository taskFileRepository;

    @Mock
    private FileRepository fileRepository;

    @Mock
    private DirectoryRepository directoryRepository;

    @Mock
    private ProjectRepository projectRepository;

    @InjectMocks
    private TaskService taskService;

    private String projectId = "proj-123";
    private String userId = "user-001";

    @BeforeEach
    void setUp() {
        // 模拟 Project 存在且属于当前用户
        Project project = new Project();
        project.setProjectId(projectId);
        project.setOwnerId(userId);
        lenient().when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));
    }

    @Test
    void testGetTaskList_Success() {
        // 1. Mock Tasks
        Task task1 = new Task();
        task1.setTaskId("task-1");
        task1.setTaskName("Task 1");
        task1.setProjectId(projectId);
        task1.setUserId(userId);
        task1.setCreatedAt(LocalDateTime.now());
        task1.setUpdatedAt(LocalDateTime.now());
        task1.setStatus(Task.Status.COMPLETED);

        when(taskRepository.findByProjectIdAndUserIdOrderByCreatedAtDesc(projectId, userId))
                .thenReturn(Arrays.asList(task1));

        // Act
        TaskListResponse response = taskService.getTaskList(projectId, userId);

        // Assert
        assertNotNull(response);
        assertEquals(1, response.getTotalCount());
        
        TaskListResponse.TaskListItem item = response.getTasks().get(0);
        assertEquals("task-1", item.getId());
        assertEquals("Task 1", item.getName());
        
        // TaskService does not populate taskFiles in list view
        assertNull(item.getTaskFiles());
    }

    @Test
    void testGetTaskList_Empty() {
        // Mock empty tasks
        when(taskRepository.findByProjectIdAndUserIdOrderByCreatedAtDesc(projectId, userId))
                .thenReturn(Collections.emptyList());

        // Act
        TaskListResponse response = taskService.getTaskList(projectId, userId);

        // Assert
        assertNotNull(response);
        assertEquals(0, response.getTotalCount());
        assertTrue(response.getTasks().isEmpty());

        // Verify that subsequent batch calls were NOT made
        verify(taskFileRepository, never()).findByTaskIdInOrderByCreatedAtAsc(anyList());
        verify(fileRepository, never()).findByFileIdIn(anyList());
    }
}

