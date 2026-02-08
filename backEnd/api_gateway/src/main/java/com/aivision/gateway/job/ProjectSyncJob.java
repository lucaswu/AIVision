package com.aivision.gateway.job;

import com.aivision.gateway.service.ProjectSyncService;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class ProjectSyncJob {

    private final ProjectSyncService projectSyncService;

    public ProjectSyncJob(ProjectSyncService projectSyncService) {
        this.projectSyncService = projectSyncService;
    }

    @Scheduled(cron = "${third-party.project-sync.cron:0 0 2 * * ?}")
    public void syncProjects() {
        projectSyncService.syncProjects();
    }
}
