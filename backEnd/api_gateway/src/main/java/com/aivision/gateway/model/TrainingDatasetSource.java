package com.aivision.gateway.model;

import javax.persistence.Column;
import javax.persistence.Entity;
import javax.persistence.Id;
import javax.persistence.Table;

@Entity
@Table(name = "training_dataset_source")
public class TrainingDatasetSource {

    @Id
    @Column(name = "id", length = 255)
    private String id;

    @Column(name = "dataset_id", nullable = false, length = 255)
    private String datasetId;

    @Column(name = "source_id", nullable = false, length = 255)
    private String sourceId;

    public TrainingDatasetSource() {}

    public TrainingDatasetSource(String id, String datasetId, String sourceId) {
        this.id = id;
        this.datasetId = datasetId;
        this.sourceId = sourceId;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getDatasetId() {
        return datasetId;
    }

    public void setDatasetId(String datasetId) {
        this.datasetId = datasetId;
    }

    public String getSourceId() {
        return sourceId;
    }

    public void setSourceId(String sourceId) {
        this.sourceId = sourceId;
    }
}
