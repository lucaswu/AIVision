package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import javax.validation.constraints.Min;
import javax.validation.constraints.Size;

public class UpdateDirectoryRequest {

    @JsonProperty("Name")
    @Size(max = 255, message = "目录名称长度不能超过255个字符")
    private String Name;

    @JsonProperty("SortOrder")
    @Min(value = 0, message = "排序号不能小于0")
    private Integer SortOrder;

    public UpdateDirectoryRequest() {}

    public UpdateDirectoryRequest(String name, Integer sortOrder) {
        this.Name = name;
        this.SortOrder = sortOrder;
    }

    public String getName() {
        return Name;
    }

    public void setName(String name) {
        this.Name = name;
    }

    public Integer getSortOrder() {
        return SortOrder;
    }

    public void setSortOrder(Integer sortOrder) {
        this.SortOrder = sortOrder;
    }

    @Override
    public String toString() {
        return "UpdateDirectoryRequest{" +
                "Name='" + Name + '\'' +
                ", SortOrder=" + SortOrder +
                '}';
    }
}
