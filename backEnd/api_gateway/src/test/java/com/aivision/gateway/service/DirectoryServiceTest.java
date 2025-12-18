package com.aivision.gateway.service;

import com.aivision.gateway.model.Directory;
import com.aivision.gateway.model.Project;
import com.aivision.gateway.repository.DirectoryRepository;
import com.aivision.gateway.repository.ProjectRepository;
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

    @InjectMocks
    private DirectoryService directoryService;

    @Test
    void testCreateDirectory_Success() {
        // Arrange
        String projectId = "p1";
        String userId = "u1";
        String dirName = "test-dir";
        
        Project project = new Project(projectId, "P1", userId);
        
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));
        when(directoryRepository.findByProjectIdAndUserIdAndParentIdAndDirNameAndStatus(
            projectId, userId, null, dirName, Directory.Status.ACTIVE)).thenReturn(Optional.empty());
        when(directoryRepository.save(any(Directory.class))).thenAnswer(i -> i.getArgument(0));

        // Act
        String dirId = directoryService.createDirectory(projectId, userId, dirName, null);

        // Assert
        assertNotNull(dirId);
        verify(directoryRepository).save(any(Directory.class));
    }

    @Test
    void testCreateDirectory_Duplicate() {
        // Arrange
        String projectId = "p1";
        String userId = "u1";
        String dirName = "test-dir";
        Project project = new Project(projectId, "P1", userId);
        
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));
        when(directoryRepository.findByProjectIdAndUserIdAndParentIdAndDirNameAndStatus(
            projectId, userId, null, dirName, Directory.Status.ACTIVE)).thenReturn(Optional.of(new Directory()));

        // Act & Assert
        assertThrows(RuntimeException.class, () -> 
            directoryService.createDirectory(projectId, userId, dirName, null));
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
        
        when(directoryRepository.findByDirIdAndProjectIdAndUserIdAndStatus(dirId, projectId, userId, Directory.Status.ACTIVE))
            .thenReturn(Optional.of(dir));
        when(directoryRepository.findByParentIdAndUserIdAndStatusOrderByDirNameAsc(dirId, userId, Directory.Status.ACTIVE))
            .thenReturn(Collections.emptyList());

        // Act
        directoryService.deleteDirectory(dirId, projectId, userId);

        // Assert
        assertEquals(Directory.Status.DELETED, dir.getStatus());
        verify(directoryRepository).save(dir);
    }

    @Test
    void testDeleteDirectory_NotEmpty() {
        // Arrange
        String dirId = "d1";
        String projectId = "p1";
        String userId = "u1";
        Directory dir = new Directory();
        dir.setDirId(dirId);
        
        when(directoryRepository.findByDirIdAndProjectIdAndUserIdAndStatus(dirId, projectId, userId, Directory.Status.ACTIVE))
            .thenReturn(Optional.of(dir));
        when(directoryRepository.findByParentIdAndUserIdAndStatusOrderByDirNameAsc(dirId, userId, Directory.Status.ACTIVE))
            .thenReturn(Collections.singletonList(new Directory()));

        // Act & Assert
        assertThrows(RuntimeException.class, () -> 
            directoryService.deleteDirectory(dirId, projectId, userId));
    }
}

