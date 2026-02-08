package com.aivision.gateway.repository;

import com.aivision.gateway.model.TrainingDataset;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface TrainingDatasetRepository extends JpaRepository<TrainingDataset, String> {
    List<TrainingDataset> findByProjectIdOrderByCreatedAtDesc(String projectId);
    long countByProjectId(String projectId);
}
