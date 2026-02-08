package com.aivision.gateway.service;

import com.aivision.gateway.client.ThirdPartyClient;
import com.aivision.gateway.config.ThirdPartyProperties;
import com.aivision.gateway.model.Project;
import com.aivision.gateway.model.thirdparty.ThirdPartyProjectResponse;
import com.aivision.gateway.repository.ProjectRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ProjectSyncServiceTest {

    @Mock
    private ThirdPartyProperties properties;

    @Mock
    private ThirdPartyClient thirdPartyClient;

    @Mock
    private ProjectRepository projectRepository;

    private ProjectSyncService projectSyncService;

    @BeforeEach
    void setUp() {
        projectSyncService = new ProjectSyncService(properties, thirdPartyClient, projectRepository);
    }

    @Test
    void testSyncProjects_NewProject() {
        // 1. Mock Properties
        when(properties.isEnabled()).thenReturn(true);

        // 2. Mock Token
        when(thirdPartyClient.getAccessToken()).thenReturn("mock-token");

        // 3. Mock Third Party Projects
        ThirdPartyProjectResponse response = new ThirdPartyProjectResponse();
        response.setSuccess(true);
        ThirdPartyProjectResponse.ProjectItem item = new ThirdPartyProjectResponse.ProjectItem();
        item.setId("tp-1");
        item.setProjectName("Test Project");
        item.setProjectOrderNumber("PJ-001");
        item.setProjectNumber("No.1");
        item.setClient("Client A");
        item.setConstructionUnit("Unit B");
        response.setData(Collections.singletonList(item));
        
        when(thirdPartyClient.getProjects("mock-token")).thenReturn(response);

        // 4. Mock Repository (Initially empty)
        when(projectRepository.findAll()).thenReturn(Collections.emptyList());

        // 5. Execute
        projectSyncService.syncProjects();

        // 6. Verify
        ArgumentCaptor<Project> projectCaptor = ArgumentCaptor.forClass(Project.class);
        verify(projectRepository, times(1)).save(projectCaptor.capture());

        Project savedProject = projectCaptor.getValue();
        assertEquals("Test Project", savedProject.getProjectName());
        assertEquals("tp-1", savedProject.getThirdPartyId());
        assertEquals("PJ-001", savedProject.getThirdPartyProjectOrderNumber());
        assertEquals("No.1", savedProject.getThirdPartyProjectCode());
        assertTrue(savedProject.getDescription().contains("委托单位: Client A"));
        assertEquals(Project.Status.ACTIVE, savedProject.getStatus());
    }

    @Test
    void testSyncProjects_UpdateProject() {
        // 1. Mock Properties
        when(properties.isEnabled()).thenReturn(true);
        when(thirdPartyClient.getAccessToken()).thenReturn("mock-token");

        // 2. Mock Existing Project
        Project existingProject = new Project();
        existingProject.setProjectId("local-1");
        existingProject.setProjectName("Old Name");
        existingProject.setThirdPartyId("tp-1");
        existingProject.setThirdPartyProjectOrderNumber("PJ-001");
        existingProject.setStatus(Project.Status.ACTIVE);
        when(projectRepository.findAll()).thenReturn(Collections.singletonList(existingProject));

        // 3. Mock Third Party Update
        ThirdPartyProjectResponse response = new ThirdPartyProjectResponse();
        response.setSuccess(true);
        ThirdPartyProjectResponse.ProjectItem item = new ThirdPartyProjectResponse.ProjectItem();
        item.setId("tp-1");
        item.setProjectName("New Name"); // Name changed
        item.setProjectOrderNumber("PJ-001");
        response.setData(Collections.singletonList(item));
        when(thirdPartyClient.getProjects("mock-token")).thenReturn(response);

        // 4. Execute
        projectSyncService.syncProjects();

        // 5. Verify
        ArgumentCaptor<Project> projectCaptor = ArgumentCaptor.forClass(Project.class);
        verify(projectRepository, times(1)).save(projectCaptor.capture());

        Project updatedProject = projectCaptor.getValue();
        assertEquals("local-1", updatedProject.getProjectId());
        assertEquals("New Name", updatedProject.getProjectName());
    }

    @Test
    void testSyncProjects_DeleteProject() {
        // 1. Mock Properties
        when(properties.isEnabled()).thenReturn(true);
        when(thirdPartyClient.getAccessToken()).thenReturn("mock-token");

        // 2. Mock Existing Project that should be deleted
        Project existingProject = new Project();
        existingProject.setProjectId("local-1");
        existingProject.setProjectName("To Be Deleted");
        existingProject.setThirdPartyId("tp-1");
        existingProject.setThirdPartyProjectOrderNumber("PJ-001");
        existingProject.setStatus(Project.Status.ACTIVE);
        when(projectRepository.findAll()).thenReturn(Collections.singletonList(existingProject));

        // 3. Mock Third Party Empty List
        ThirdPartyProjectResponse response = new ThirdPartyProjectResponse();
        response.setSuccess(true);
        response.setData(Collections.emptyList()); // No projects returned
        when(thirdPartyClient.getProjects("mock-token")).thenReturn(response);

        // 4. Execute
        projectSyncService.syncProjects();

        // 5. Verify
        ArgumentCaptor<Project> projectCaptor = ArgumentCaptor.forClass(Project.class);
        verify(projectRepository, times(1)).save(projectCaptor.capture());

        Project deletedProject = projectCaptor.getValue();
        assertEquals("local-1", deletedProject.getProjectId());
        assertEquals(Project.Status.DELETED, deletedProject.getStatus());
    }
}
