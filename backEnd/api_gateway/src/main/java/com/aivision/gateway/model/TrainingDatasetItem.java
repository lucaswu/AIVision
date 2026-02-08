package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

@Schema(description = "训练数据集列表项")
public class TrainingDatasetItem {

    @JsonProperty("Id")
    @Schema(description = "数据集ID", example = "dataset-001")
    private String id;

    @JsonProperty("Name")
    @Schema(description = "数据集名称", example = "training_set_v1")
    private String name;

    @JsonProperty("Type")
    @Schema(description = "数据集类型 (训练集/测试集)", example = "训练集")
    private String type;

    @JsonProperty("Count")
    @Schema(description = "数据量", example = "8450")
    private Integer count;

    @JsonProperty("Source")
    @Schema(description = "数据源名称汇总", example = "images_batch_001, images_batch_002")
    private String source;

    @JsonProperty("SourceIds")
    @Schema(description = "数据源ID列表")
    private List<String> sourceIds;

    @JsonProperty("CreateTime")
    @Schema(description = "创建时间", example = "2023-10-15")
    private String createTime;

    @JsonProperty("InUseExperiments")
    @Schema(description = "正在使用该数据集的实验/训练任务")
    private List<String> inUseExperiments;

    public TrainingDatasetItem() {}

    public TrainingDatasetItem(String id, String name, String type, Integer count, String source,
                               List<String> sourceIds, String createTime, List<String> inUseExperiments) {
        this.id = id;
        this.name = name;
        this.type = type;
        this.count = count;
        this.source = source;
        this.sourceIds = sourceIds;
        this.createTime = createTime;
        this.inUseExperiments = inUseExperiments;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public Integer getCount() {
        return count;
    }

    public void setCount(Integer count) {
        this.count = count;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public List<String> getSourceIds() {
        return sourceIds;
    }

    public void setSourceIds(List<String> sourceIds) {
        this.sourceIds = sourceIds;
    }

    public String getCreateTime() {
        return createTime;
    }

    public void setCreateTime(String createTime) {
        this.createTime = createTime;
    }

    public List<String> getInUseExperiments() {
        return inUseExperiments;
    }

    public void setInUseExperiments(List<String> inUseExperiments) {
        this.inUseExperiments = inUseExperiments;
    }
}
