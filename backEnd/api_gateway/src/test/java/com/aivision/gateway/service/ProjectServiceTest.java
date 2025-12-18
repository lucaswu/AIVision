package com.aivision.gateway.service;

import com.aivision.gateway.model.Project;
import com.aivision.gateway.model.ProjectListItem;
import com.aivision.gateway.repository.FileRepository;
import com.aivision.gateway.repository.ProjectRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class ProjectServiceTest {

    @Mock
    private ProjectRepository projectRepository;

    @Mock
    private FileRepository fileRepository;

    @InjectMocks
    private ProjectService projectService;

    @Test
    void testGetProjectListByUserId() {
        // Arrange
        String userId = "user-1";
        Project p1 = new Project("p1", "Project 1", userId);
        p1.setDescription("Desc 1");
        p1.setCreatedAt(LocalDateTime.now());
        p1.setUpdatedAt(LocalDateTime.now());
        
        Project p2 = new Project("p2", "Project 2", userId);
        p2.setDescription("Desc 2");
        p2.setCreatedAt(LocalDateTime.now());
        p2.setUpdatedAt(LocalDateTime.now());

        when(projectRepository.findByOwnerId(userId)).thenReturn(Arrays.asList(p1, p2));
        when(fileRepository.countByProjectId("p1")).thenReturn(10L);
        when(fileRepository.countByProjectId("p2")).thenReturn(5L);

        // Act
        List<ProjectListItem> result = projectService.getProjectListByUserId(userId);

        // Assert
        assertEquals(2, result.size());
        
        ProjectListItem item1 = result.stream().filter(i -> i.getId().equals("p1")).findFirst().orElse(null);
        assertNotNull(item1);
        assertEquals("Project 1", item1.getName());
        assertEquals("Desc 1", item1.getDescription());
        assertEquals(10, item1.getFileCount());
        
        ProjectListItem item2 = result.stream().filter(i -> i.getId().equals("p2")).findFirst().orElse(null);
        assertNotNull(item2);
        assertEquals(5, item2.getFileCount());
    }

    @Test
    void testCreateProject_Success() {
        // Arrange
        String userId = "user-1";
        String name = "New Project";
        String desc = "New Desc";
        
        when(projectRepository.existsByProjectNameAndOwnerId(name, userId)).thenReturn(false);
        when(projectRepository.save(any(Project.class))).thenAnswer(inv -> {
            Project p = inv.getArgument(0);
            return p; // mock save returning the same object
        });

        // Act
        String projectId = projectService.createProject(userId, name, desc);

        // Assert
        assertNotNull(projectId);
        verify(projectRepository).save(any(Project.class));
    }

    @Test
    void testCreateProject_DuplicateName() {
        // Arrange
        String userId = "user-1";
        String name = "Duplicate Project";
        
        when(projectRepository.existsByProjectNameAndOwnerId(name, userId)).thenReturn(true);

        // Act & Assert
        assertThrows(RuntimeException.class, () -> 
            projectService.createProject(userId, name, "desc"));
    }

    @Test
    void testUpdateProject_Success() {
        // Arrange
        String projectId = "p1";
        String userId = "user-1";
        Project project = new Project(projectId, "Old Name", userId);
        project.setDescription("Old Desc");
        
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));
        when(projectRepository.existsByProjectNameAndOwnerId("New Name", userId)).thenReturn(false);

        // Act
        projectService.updateProject(projectId, userId, "New Name", "New Desc");

        // Assert
        assertEquals("New Name", project.getProjectName());
        assertEquals("New Desc", project.getDescription());
        verify(projectRepository).save(project);
    }

    @Test
    void testUpdateProject_NoPermission() {
        // Arrange
        String projectId = "p1";
        String userId = "user-1";
        String otherUser = "user-2";
        Project project = new Project(projectId, "Name", otherUser); // Owner is user-2
        
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));

        // Act & Assert
        assertThrows(RuntimeException.class, () -> 
            projectService.updateProject(projectId, userId, "New Name", "New Desc"));
    }

    @Test
    void testDeleteProject_Success() {
        // Arrange
        String projectId = "p1";
        String userId = "user-1";
        Project project = new Project(projectId, "Name", userId);
        
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));

        // Act
        projectService.deleteProject(projectId, userId);

        // Assert
        verify(projectRepository).delete(project);
    }
}

