package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

@Schema(description = "训练数据源列表项")
public class TrainingDataSourceItem {

    @JsonProperty("Id")
    @Schema(description = "数据源ID", example = "source-001")
    private String id;

    @JsonProperty("Name")
    @Schema(description = "数据源名称", example = "images_batch_001")
    private String name;

    @JsonProperty("Path")
    @Schema(description = "数据源路径", example = "/data/raw/images/")
    private String path;

    @JsonProperty("FileCount")
    @Schema(description = "文件数", example = "1245")
    private Integer fileCount;

    @JsonProperty("LabeledCount")
    @Schema(description = "已标注数量", example = "800")
    private Integer labeledCount;

    @JsonProperty("SizeBytes")
    @Schema(description = "总大小（字节）", example = "2800000000")
    private Long sizeBytes;

    @JsonProperty("CreateTime")
    @Schema(description = "创建时间", example = "2025-12-15 10:24")
    private String createTime;

    @JsonProperty("UpdateTime")
    @Schema(description = "更新时间", example = "2025-12-15 10:24")
    private String updateTime;

    @JsonProperty("UsedByDatasets")
    @Schema(description = "引用该数据源的数据集名称列表")
    private List<String> usedByDatasets;

    @JsonProperty("UsedByExperiments")
    @Schema(description = "正在使用该数据源的实验/训练任务")
    private List<String> usedByExperiments;

    public TrainingDataSourceItem() {}

    public TrainingDataSourceItem(String id, String name, String path, Integer fileCount, Integer labeledCount,
                                  Long sizeBytes, String createTime, String updateTime,
                                  List<String> usedByDatasets, List<String> usedByExperiments) {
        this.id = id;
        this.name = name;
        this.path = path;
        this.fileCount = fileCount;
        this.labeledCount = labeledCount;
        this.sizeBytes = sizeBytes;
        this.createTime = createTime;
        this.updateTime = updateTime;
        this.usedByDatasets = usedByDatasets;
        this.usedByExperiments = usedByExperiments;
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

    public String getCreateTime() {
        return createTime;
    }

    public void setCreateTime(String createTime) {
        this.createTime = createTime;
    }

    public String getUpdateTime() {
        return updateTime;
    }

    public void setUpdateTime(String updateTime) {
        this.updateTime = updateTime;
    }

    public List<String> getUsedByDatasets() {
        return usedByDatasets;
    }

    public void setUsedByDatasets(List<String> usedByDatasets) {
        this.usedByDatasets = usedByDatasets;
    }

    public List<String> getUsedByExperiments() {
        return usedByExperiments;
    }

    public void setUsedByExperiments(List<String> usedByExperiments) {
        this.usedByExperiments = usedByExperiments;
    }
}
