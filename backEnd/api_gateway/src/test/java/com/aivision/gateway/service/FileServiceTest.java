package com.aivision.gateway.service;

import com.aivision.gateway.config.FileUploadProperties;
import com.aivision.gateway.model.Directory;
import com.aivision.gateway.model.File;
import com.aivision.gateway.model.FilePreviewResponse;
import com.aivision.gateway.model.FileUploadResponse;
import com.aivision.gateway.model.Project;
import com.aivision.gateway.repository.DirectoryRepository;
import com.aivision.gateway.repository.FileRepository;
import com.aivision.gateway.repository.ProjectRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.multipart.MultipartFile;

import java.util.Arrays;
import java.util.Collections;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class FileServiceTest {

    @Mock
    private FileRepository fileRepository;

    @Mock
    private ProjectRepository projectRepository;

    @Mock
    private DirectoryRepository directoryRepository;

    @Mock
    private FileUploadProperties fileUploadProperties;

    @InjectMocks
    private FileService fileService;

    private final String projectId = "proj-1";
    private final String userId = "user-1";
    private final String dirId = "dir-1";

    @BeforeEach
    void setUp() {
        // Mock 允许的文件类型
        lenient().when(fileUploadProperties.getAllowedImageTypes())
                .thenReturn(Arrays.asList("jpg", "png", "jpeg"));
    }

    @Test
    void testUploadFiles_Success() {
        // Mock Project & Directory
        Project project = new Project();
        project.setProjectId(projectId);
        project.setOwnerId(userId);
        
        Directory directory = new Directory();
        directory.setDirId(dirId);
        directory.setDirPath("/test-dir");

        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));
        when(directoryRepository.findByDirIdAndProjectIdAndUserIdAndStatus(eq(dirId), eq(projectId), eq(userId), any()))
                .thenReturn(Optional.of(directory));

        // Mock MultipartFile
        byte[] content = "fake-image-content".getBytes();
        MockMultipartFile file = new MockMultipartFile("File", "test.jpg", "image/jpeg", content);

        // Act
        FileUploadResponse response = fileService.uploadFiles(projectId, userId, dirId, new MultipartFile[]{file});

        // Assert
        assertEquals(1, response.getSuccessCount());
        assertEquals(0, response.getFailedCount());
        
        // Verify Repository save called
        verify(fileRepository, times(1)).save(any(File.class));
    }

    @Test
    void testGetFilePreview_Success() {
        // Mock File in DB
        String fileId = "file-123";
        byte[] content = "fake-image-content".getBytes();
        
        File fileEntity = new File();
        fileEntity.setFileId(fileId);
        fileEntity.setOriginalName("test.jpg");
        fileEntity.setFileExtension("jpg");
        fileEntity.setMimeType("image/jpeg");
        fileEntity.setFileData(content);
        fileEntity.setFileSize((long) content.length);

        when(fileRepository.findByFileIdAndProjectIdAndUserId(fileId, projectId, userId))
                .thenReturn(Optional.of(fileEntity));

        // Act
        FilePreviewResponse response = fileService.getFilePreview(fileId, projectId, userId);

        // Assert
        assertNotNull(response);
        assertEquals(fileId, response.getFileId());
        assertTrue(response.getImageData().startsWith("data:image/jpeg;base64,"));
    }
}

