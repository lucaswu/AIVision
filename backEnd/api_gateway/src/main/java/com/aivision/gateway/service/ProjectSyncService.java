package com.aivision.gateway.service;

import com.aivision.gateway.client.ThirdPartyClient;
import com.aivision.gateway.config.ThirdPartyProperties;
import com.aivision.gateway.model.Project;
import com.aivision.gateway.model.thirdparty.ThirdPartyProjectResponse;
import com.aivision.gateway.repository.ProjectRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class ProjectSyncService {

    private static final Logger logger = LoggerFactory.getLogger(ProjectSyncService.class);

    private final ThirdPartyProperties properties;
    private final ThirdPartyClient thirdPartyClient;
    private final ProjectRepository projectRepository;

    public ProjectSyncService(ThirdPartyProperties properties, 
                              ThirdPartyClient thirdPartyClient,
                              ProjectRepository projectRepository) {
        this.properties = properties;
        this.thirdPartyClient = thirdPartyClient;
        this.projectRepository = projectRepository;
    }

    @Transactional
    public void syncProjects() {
        if (!properties.isEnabled()) {
            logger.info("Third party project sync is disabled");
            return;
        }

        logger.info("Starting third party project sync...");

        // 1. Get Access Token
        String token = thirdPartyClient.getAccessToken();
        if (!StringUtils.hasText(token)) {
            logger.error("Failed to get access token, aborting sync");
            return;
        }

        // 2. Get Projects from Third Party
        ThirdPartyProjectResponse response = thirdPartyClient.getProjects(token);
        if (response == null || !response.isSuccess() || response.getData() == null) {
            logger.error("Failed to get projects from third party: {}", response != null ? response.getMsg() : "Empty response");
            return;
        }

        List<ThirdPartyProjectResponse.ProjectItem> thirdPartyProjects = response.getData();
        logger.info("Fetched {} projects from third party", thirdPartyProjects.size());

        // 3. Sync Logic
        // Get all existing projects that are synced from third party (identified by having thirdPartyId)
        List<Project> existingSyncedProjects = projectRepository.findAll().stream()
                .filter(p -> StringUtils.hasText(p.getThirdPartyId()))
                .collect(Collectors.toList());
        
        Map<String, Project> existingProjectMap = existingSyncedProjects.stream()
                .collect(Collectors.toMap(Project::getThirdPartyProjectOrderNumber, p -> p, (p1, p2) -> p1));

        Set<String> processedProjectOrderNumbers = new java.util.HashSet<>();

        for (ThirdPartyProjectResponse.ProjectItem item : thirdPartyProjects) {
            String projectOrderNumber = item.getProjectOrderNumber();
            if (!StringUtils.hasText(projectOrderNumber)) {
                logger.warn("Skipping third party project with empty projectOrderNumber: {}", item.getProjectName());
                continue;
            }

            processedProjectOrderNumbers.add(projectOrderNumber);
            
            Project project = existingProjectMap.get(projectOrderNumber);
            if (project == null) {
                // Try to find by projectOrderNumber even if thirdPartyId is missing (first sync case)
                // Assuming we don't have a direct findBy method exposed yet, we rely on the map built above.
                // If we want to be safer, we could query DB by projectOrderNumber if we added an index/method.
                // For now, create new.
                createNewProject(item);
            } else {
                updateProject(project, item);
            }
        }

        // 4. Handle Deletions/Archive
        // If a project exists in our DB as third-party sourced but is not in the fetched list, we might want to deactivate it.
        for (Project existing : existingSyncedProjects) {
            if (!processedProjectOrderNumbers.contains(existing.getThirdPartyProjectOrderNumber())) {
                logger.info("Project {} (OrderNum: {}) not found in third party list, marking as inactive/deleted", 
                        existing.getProjectName(), existing.getThirdPartyProjectOrderNumber());
                // Option: Mark as ARCHIVED or DELETED based on requirements. 
                // "后端项目信息同步逻辑是根据第三方接口的项目信息，去新建或者更新或者删除项目" -> Assuming deletion or soft deletion.
                // Using DELETED status as soft delete.
                existing.setStatus(Project.Status.DELETED);
                projectRepository.save(existing);
            }
        }

        logger.info("Third party project sync completed");
    }

    private void createNewProject(ThirdPartyProjectResponse.ProjectItem item) {
        Project project = new Project();
        project.setProjectId(UUID.randomUUID().toString());
        project.setProjectName(item.getProjectName());
        project.setOwnerId("admin"); // Default owner as requested
        project.setStatus(Project.Status.ACTIVE);
        
        // Map fields
        project.setThirdPartyId(item.getId());
        project.setThirdPartyProjectCode(item.getProjectNumber()); // Map projectNumber to thirdPartyProjectCode
        project.setThirdPartyProjectOrderNumber(item.getProjectOrderNumber()); // Map projectOrderNumber
        
        // Description composition
        StringBuilder desc = new StringBuilder();
        if (StringUtils.hasText(item.getProjectNumber())) desc.append("项目号: ").append(item.getProjectNumber()).append("\n");
        if (StringUtils.hasText(item.getConstructionUnit())) desc.append("建设单位: ").append(item.getConstructionUnit()).append("\n");
        if (StringUtils.hasText(item.getClient())) desc.append("委托单位: ").append(item.getClient()).append("\n");
        if (StringUtils.hasText(item.getProjectAddress())) desc.append("项目地址: ").append(item.getProjectAddress()).append("\n");
        if (StringUtils.hasText(item.getProjectYear())) desc.append("年份: ").append(item.getProjectYear()).append("\n");
        project.setDescription(desc.toString());

        // Project Type is independent, leave null or default
        
        projectRepository.save(project);
        logger.info("Created new project: {}", project.getProjectName());
    }

    private void updateProject(Project project, ThirdPartyProjectResponse.ProjectItem item) {
        boolean changed = false;

        if (!item.getProjectName().equals(project.getProjectName())) {
            project.setProjectName(item.getProjectName());
            changed = true;
        }

        // Update mapping fields if changed
        if (!item.getId().equals(project.getThirdPartyId())) {
            project.setThirdPartyId(item.getId());
            changed = true;
        }
        if (item.getProjectNumber() != null && !item.getProjectNumber().equals(project.getThirdPartyProjectCode())) {
            project.setThirdPartyProjectCode(item.getProjectNumber());
            changed = true;
        }

        // Update description
        StringBuilder desc = new StringBuilder();
        if (StringUtils.hasText(item.getProjectNumber())) desc.append("项目号: ").append(item.getProjectNumber()).append("\n");
        if (StringUtils.hasText(item.getConstructionUnit())) desc.append("建设单位: ").append(item.getConstructionUnit()).append("\n");
        if (StringUtils.hasText(item.getClient())) desc.append("委托单位: ").append(item.getClient()).append("\n");
        if (StringUtils.hasText(item.getProjectAddress())) desc.append("项目地址: ").append(item.getProjectAddress()).append("\n");
        if (StringUtils.hasText(item.getProjectYear())) desc.append("年份: ").append(item.getProjectYear()).append("\n");
        
        String newDesc = desc.toString();
        if (!newDesc.equals(project.getDescription())) {
            project.setDescription(newDesc);
            changed = true;
        }
        
        // Ensure status is active if it was deleted but now reappeared
        if (project.getStatus() == Project.Status.DELETED) {
            project.setStatus(Project.Status.ACTIVE);
            changed = true;
        }

        if (changed) {
            projectRepository.save(project);
            logger.info("Updated project: {}", project.getProjectName());
        }
    }
}
