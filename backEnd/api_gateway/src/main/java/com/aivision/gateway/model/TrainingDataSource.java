package com.aivision.gateway.model;

import javax.persistence.Column;
import javax.persistence.Entity;
import javax.persistence.Id;
import javax.persistence.PrePersist;
import javax.persistence.PreUpdate;
import javax.persistence.Table;
import java.time.LocalDateTime;

@Entity
@Table(name = "training_data_source")
public class TrainingDataSource {

    @Id
    @Column(name = "source_id", length = 255)
    private String sourceId;

    @Column(name = "project_id", nullable = false, length = 255)
    private String projectId;

    @Column(name = "name", nullable = false, length = 255)
    private String name;

    @Column(name = "path", nullable = false, length = 1024)
    private String path;

    @Column(name = "file_count")
    private Integer fileCount;

    @Column(name = "labeled_count")
    private Integer labeledCount;

    @Column(name = "size_bytes")
    private Long sizeBytes;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    public TrainingDataSource() {}

    public TrainingDataSource(String sourceId, String projectId, String name, String path) {
        this.sourceId = sourceId;
        this.projectId = projectId;
        this.name = name;
        this.path = path;
    }

    @PrePersist
    public void onCreate() {
        LocalDateTime now = LocalDateTime.now();
        this.createdAt = now;
        this.updatedAt = now;
    }

    @PreUpdate
    public void onUpdate() {
        this.updatedAt = LocalDateTime.now();
    }

    public String getSourceId() {
        return sourceId;
    }

    public void setSourceId(String sourceId) {
        this.sourceId = sourceId;
    }

    public String getProjectId() {
        return projectId;
    }

    public void setProjectId(String projectId) {
        this.projectId = projectId;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getPath() {
        return path;
    }

    public void setPath(String path) {
        this.path = path;
    }

    public Integer getFileCount() {
        return fileCount;
    }

    public void setFileCount(Integer fileCount) {
        this.fileCount = fileCount;
    }

    public Integer getLabeledCount() {
        return labeledCount;
    }

    public void setLabeledCount(Integer labeledCount) {
        this.labeledCount = labeledCount;
    }

    public Long getSizeBytes() {
        return sizeBytes;
    }

    public void setSizeBytes(Long sizeBytes) {
        this.sizeBytes = sizeBytes;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}
