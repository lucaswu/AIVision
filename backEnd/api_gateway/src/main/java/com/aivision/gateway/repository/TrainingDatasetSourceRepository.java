package com.aivision.gateway.repository;

import com.aivision.gateway.model.TrainingDatasetSource;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;

public interface TrainingDatasetSourceRepository extends JpaRepository<TrainingDatasetSource, String> {
    List<TrainingDatasetSource> findBySourceId(String sourceId);
    List<TrainingDatasetSource> findByDatasetId(String datasetId);
    List<TrainingDatasetSource> findBySourceIdIn(Collection<String> sourceIds);
    List<TrainingDatasetSource> findByDatasetIdIn(Collection<String> datasetIds);
}
