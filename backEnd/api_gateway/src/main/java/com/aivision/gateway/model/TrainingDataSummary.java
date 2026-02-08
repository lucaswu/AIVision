package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "训练数据统计汇总")
public class TrainingDataSummary {

    @JsonProperty("RawCount")
    @Schema(description = "原始数据数量（未标注）", example = "12450")
    private Integer rawCount;

    @JsonProperty("LabeledCount")
    @Schema(description = "已标注数据数量", example = "8320")
    private Integer labeledCount;

    @JsonProperty("DatasetCount")
    @Schema(description = "数据集数量", example = "3")
    private Integer datasetCount;

    @JsonProperty("DataSourceCount")
    @Schema(description = "数据源数量", example = "5")
    private Integer dataSourceCount;

    public TrainingDataSummary() {}

    public TrainingDataSummary(Integer rawCount, Integer labeledCount, Integer datasetCount, Integer dataSourceCount) {
        this.rawCount = rawCount;
        this.labeledCount = labeledCount;
        this.datasetCount = datasetCount;
        this.dataSourceCount = dataSourceCount;
    }

    public Integer getRawCount() {
        return rawCount;
    }

    public void setRawCount(Integer rawCount) {
        this.rawCount = rawCount;
    }

    public Integer getLabeledCount() {
        return labeledCount;
    }

    public void setLabeledCount(Integer labeledCount) {
        this.labeledCount = labeledCount;
    }

    public Integer getDatasetCount() {
        return datasetCount;
    }

    public void setDatasetCount(Integer datasetCount) {
        this.datasetCount = datasetCount;
    }

    public Integer getDataSourceCount() {
        return dataSourceCount;
    }

    public void setDataSourceCount(Integer dataSourceCount) {
        this.dataSourceCount = dataSourceCount;
    }
}
