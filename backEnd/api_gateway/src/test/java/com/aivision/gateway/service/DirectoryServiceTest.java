package com.aivision.gateway.service;

import com.aivision.gateway.model.Directory;
import com.aivision.gateway.model.Project;
import com.aivision.gateway.model.User;
import com.aivision.gateway.repository.DirectoryRepository;
import com.aivision.gateway.repository.FileRepository;
import com.aivision.gateway.repository.ProjectRepository;
import com.aivision.gateway.repository.UserProjectPermissionRepository;
import com.aivision.gateway.repository.UserRepository;
import com.aivision.gateway.service.storage.StorageStrategy;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Collections;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class DirectoryServiceTest {

    @Mock
    private DirectoryRepository directoryRepository;

    @Mock
    private ProjectRepository projectRepository;

    @Mock
    private UserRepository userRepository;

    @Mock
    private UserProjectPermissionRepository permissionRepository;

    @Mock
    private FileRepository fileRepository;

    @Mock
    private StorageStrategy storageStrategy;

    @InjectMocks
    private DirectoryService directoryService;

    @Test
    void testCreateDirectory_Success() {
        // Arrange
        String projectId = "p1";
        String userId = "u1";
        String dirName = "test-dir";
        
        Project project = new Project(projectId, "P1", userId);
        User user = new User(userId, "admin", "password", User.Role.ADMIN);
        
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));
        when(userRepository.findById(userId)).thenReturn(Optional.of(user));
        when(directoryRepository.findByProjectIdAndParentIdAndDirNameAndStatus(
            projectId, null, dirName, Directory.Status.ACTIVE)).thenReturn(Optional.empty());
        when(directoryRepository.save(any(Directory.class))).thenAnswer(i -> i.getArgument(0));

        // Act
        String dirId = directoryService.createDirectory(projectId, userId, dirName, null);

        // Assert
        assertNotNull(dirId);
        verify(directoryRepository).save(any(Directory.class));
    }

    @Test
    void testCreateDirectory_DuplicateReturnsExistingId() {
        // Arrange
        String projectId = "p1";
        String userId = "u1";
        String dirName = "test-dir";
        Project project = new Project(projectId, "P1", userId);
        User user = new User(userId, "admin", "password", User.Role.ADMIN);
        Directory existingDirectory = new Directory();
        existingDirectory.setDirId("existing-dir");
        
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));
        when(userRepository.findById(userId)).thenReturn(Optional.of(user));
        when(directoryRepository.findByProjectIdAndParentIdAndDirNameAndStatus(
            projectId, null, dirName, Directory.Status.ACTIVE)).thenReturn(Optional.of(existingDirectory));

        // Act
        String dirId = directoryService.createDirectory(projectId, userId, dirName, null);

        // Assert
        assertEquals("existing-dir", dirId);
        verify(directoryRepository, never()).save(any(Directory.class));
    }

    @Test
    void testDeleteDirectory_Success() {
        // Arrange
        String dirId = "d1";
        String projectId = "p1";
        String userId = "u1";
        Directory dir = new Directory();
        dir.setDirId(dirId);
        dir.setProjectId(projectId);
        dir.setUserId(userId);
        dir.setStatus(Directory.Status.ACTIVE);
        User user = new User(userId, "admin", "password", User.Role.ADMIN);
        
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(new Project(projectId, "P1", userId)));
        when(userRepository.findById(userId)).thenReturn(Optional.of(user));
        when(directoryRepository.findByDirIdAndProjectIdAndStatus(dirId, projectId, Directory.Status.ACTIVE))
            .thenReturn(Optional.of(dir));
        when(directoryRepository.findByProjectIdAndParentIdAndStatus(projectId, dirId, Directory.Status.ACTIVE))
            .thenReturn(Collections.emptyList());
        when(fileRepository.findByDirectoryId(dirId)).thenReturn(Collections.emptyList());

        // Act
        directoryService.deleteDirectory(dirId, projectId, userId);

        // Assert
        assertEquals(Directory.Status.DELETED, dir.getStatus());
        verify(directoryRepository).saveAll(Collections.singletonList(dir));
    }

    @Test
    void testDeleteDirectory_WithChildDirectoriesDeletesSubtree() {
        // Arrange
        String dirId = "d1";
        String projectId = "p1";
        String userId = "u1";
        Directory dir = new Directory();
        dir.setDirId(dirId);
        dir.setProjectId(projectId);
        dir.setStatus(Directory.Status.ACTIVE);
        Directory child = new Directory();
        child.setDirId("d2");
        child.setProjectId(projectId);
        child.setStatus(Directory.Status.ACTIVE);
        User user = new User(userId, "admin", "password", User.Role.ADMIN);
        
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(new Project(projectId, "P1", userId)));
        when(userRepository.findById(userId)).thenReturn(Optional.of(user));
        when(directoryRepository.findByDirIdAndProjectIdAndStatus(dirId, projectId, Directory.Status.ACTIVE))
            .thenReturn(Optional.of(dir));
        when(directoryRepository.findByProjectIdAndParentIdAndStatus(projectId, dirId, Directory.Status.ACTIVE))
            .thenReturn(Collections.singletonList(child));
        when(directoryRepository.findByProjectIdAndParentIdAndStatus(projectId, child.getDirId(), Directory.Status.ACTIVE))
            .thenReturn(Collections.emptyList());
        when(fileRepository.findByDirectoryId(dirId)).thenReturn(Collections.emptyList());
        when(fileRepository.findByDirectoryId(child.getDirId())).thenReturn(Collections.emptyList());

        // Act
        directoryService.deleteDirectory(dirId, projectId, userId);

        // Assert
        assertEquals(Directory.Status.DELETED, dir.getStatus());
        assertEquals(Directory.Status.DELETED, child.getStatus());
        verify(directoryRepository).saveAll(java.util.Arrays.asList(dir, child));
    }
}
