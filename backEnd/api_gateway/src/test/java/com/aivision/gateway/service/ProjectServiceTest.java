package com.aivision.gateway.service;

import com.aivision.gateway.model.Project;
import com.aivision.gateway.model.ProjectListItem;
import com.aivision.gateway.model.TaskFile;
import com.aivision.gateway.model.User;
import com.aivision.gateway.repository.DirectoryRepository;
import com.aivision.gateway.repository.FileRepository;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.TaskFileRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import com.aivision.gateway.service.storage.StorageStrategy;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.InOrder;
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

    @Mock
    private DirectoryRepository directoryRepository;

    @Mock
    private UserProjectPermissionRepository permissionRepository;

    @Mock
    private UserRepository userRepository;

    @Mock
    private TaskFileRepository taskFileRepository;

    @Mock
    private StorageStrategy storageStrategy;

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

        when(userRepository.findById(userId)).thenReturn(Optional.of(createInspector(userId)));
        when(projectRepository.findByOwnerId(userId)).thenReturn(Arrays.asList(p1, p2));
        when(permissionRepository.findByUserId(userId)).thenReturn(List.of());
        when(projectRepository.findAllById(any())).thenReturn(Arrays.asList(p1, p2));
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
        
        when(userRepository.findById(userId)).thenReturn(Optional.of(createAdmin(userId)));
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
        
        when(userRepository.findById(userId)).thenReturn(Optional.of(createAdmin(userId)));
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
        when(userRepository.findById(userId)).thenReturn(Optional.of(createInspector(userId)));
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
        when(userRepository.findById(userId)).thenReturn(Optional.of(createInspector(userId)));
        when(permissionRepository.findByUserIdAndProjectId(userId, projectId)).thenReturn(Optional.empty());

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
        com.aivision.gateway.model.File file = new com.aivision.gateway.model.File();
        file.setFilePath("/projects/p1/original.bmp");
        file.setThumbnailPath("/projects/p1/original.bmp.thumb.jpg");

        TaskFile taskFile = new TaskFile();
        taskFile.setMinioFilePath("/projects/p1/original.bmp");
        taskFile.setReportPath("/projects/p1/reports/result.json");
        
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));
        when(userRepository.findById(userId)).thenReturn(Optional.of(createInspector(userId)));
        when(fileRepository.findByProjectId(projectId)).thenReturn(List.of(file));
        when(taskFileRepository.findByProjectIds(List.of(projectId))).thenReturn(List.of(taskFile));
        when(storageStrategy.exists("/projects/p1/original.bmp")).thenReturn(true, false);
        when(storageStrategy.exists("/projects/p1/original.bmp.thumb.jpg")).thenReturn(true, false);
        when(storageStrategy.exists("/projects/p1/reports/result.json")).thenReturn(true, false);

        // Act
        projectService.deleteProject(projectId, userId);

        // Assert
        InOrder inOrder = inOrder(storageStrategy, projectRepository);
        inOrder.verify(storageStrategy).exists("/projects/p1/original.bmp");
        inOrder.verify(storageStrategy).delete("/projects/p1/original.bmp");
        inOrder.verify(storageStrategy).exists("/projects/p1/original.bmp");
        inOrder.verify(storageStrategy).exists("/projects/p1/original.bmp.thumb.jpg");
        inOrder.verify(storageStrategy).delete("/projects/p1/original.bmp.thumb.jpg");
        inOrder.verify(storageStrategy).exists("/projects/p1/original.bmp.thumb.jpg");
        inOrder.verify(storageStrategy).exists("/projects/p1/reports/result.json");
        inOrder.verify(storageStrategy).delete("/projects/p1/reports/result.json");
        inOrder.verify(storageStrategy).exists("/projects/p1/reports/result.json");
        inOrder.verify(projectRepository).delete(project);

        verify(storageStrategy, times(1)).delete("/projects/p1/original.bmp");
        verifyNoInteractions(permissionRepository, directoryRepository);
        verify(fileRepository, never()).deleteByProjectId(any());
    }

    @Test
    void testDeleteProject_AdminCanDeleteOtherUsersProject() {
        // Arrange
        String projectId = "p1";
        String adminId = "admin-1";
        String ownerId = "sso-user-1";
        Project project = new Project(projectId, "SSO Project", ownerId);

        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));
        when(userRepository.findById(adminId)).thenReturn(Optional.of(createAdmin(adminId)));
        when(fileRepository.findByProjectId(projectId)).thenReturn(List.of());
        when(taskFileRepository.findByProjectIds(List.of(projectId))).thenReturn(List.of());

        // Act
        projectService.deleteProject(projectId, adminId);

        // Assert
        verify(projectRepository).delete(project);
        verifyNoInteractions(permissionRepository, directoryRepository, storageStrategy);
    }

    private User createAdmin(String userId) {
        return new User(userId, "admin", "password", User.Role.ADMIN);
    }

    private User createInspector(String userId) {
        return new User(userId, "inspector", "password", User.Role.INSPECTOR);
    }
}
