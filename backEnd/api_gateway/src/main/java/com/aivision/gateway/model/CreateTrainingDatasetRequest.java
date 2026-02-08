package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

@Schema(description = "创建训练数据集请求")
public class CreateTrainingDatasetRequest {

    @JsonProperty("Name")
    @Schema(description = "数据集名称", example = "training_set_v1")
    private String name;

    @JsonProperty("Type")
    @Schema(description = "数据集类型 (TRAIN/TEST)", example = "TRAIN")
    private String type;

    @JsonProperty("SourceIds")
    @Schema(description = "数据源ID列表")
    private List<String> sourceIds;

    public CreateTrainingDatasetRequest() {}

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

    public List<String> getSourceIds() {
        return sourceIds;
    }

    public void setSourceIds(List<String> sourceIds) {
        this.sourceIds = sourceIds;
    }
}
