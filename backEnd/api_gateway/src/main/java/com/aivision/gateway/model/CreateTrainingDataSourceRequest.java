package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "创建训练数据源请求")
public class CreateTrainingDataSourceRequest {

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

    public CreateTrainingDataSourceRequest() {}

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
}
