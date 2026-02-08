package com.aivision.gateway.repository;

import com.aivision.gateway.model.TrainingDataSource;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface TrainingDataSourceRepository extends JpaRepository<TrainingDataSource, String> {
    List<TrainingDataSource> findByProjectIdOrderByCreatedAtDesc(String projectId);
    long countByProjectId(String projectId);
}
