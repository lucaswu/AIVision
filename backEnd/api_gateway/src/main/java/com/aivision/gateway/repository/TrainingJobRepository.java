package com.aivision.gateway.repository;

import com.aivision.gateway.model.TrainingJob;
import com.aivision.gateway.model.TrainingJobStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;

public interface TrainingJobRepository extends JpaRepository<TrainingJob, String> {
    List<TrainingJob> findByDatasetIdAndStatusIn(String datasetId, Collection<TrainingJobStatus> statuses);
    List<TrainingJob> findByProjectIdAndStatusIn(String projectId, Collection<TrainingJobStatus> statuses);
    long countByDatasetIdAndStatusIn(String datasetId, Collection<TrainingJobStatus> statuses);
}
