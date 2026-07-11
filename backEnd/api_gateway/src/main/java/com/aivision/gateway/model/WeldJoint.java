package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import javax.persistence.*;
import java.time.LocalDateTime;

/**
 * 焊口记录实体 - 一张底片(TaskFile)可以关联多个焊口编号
 */
@Entity
@Table(name = "weld_joint")
public class WeldJoint {

    @Id
    @Column(name = "weld_joint_id", length = 255)
    @JsonProperty("WeldJointId")
    private String weldJointId;

    @Column(name = "task_file_id", nullable = false, length = 255)
    @JsonProperty("TaskFileId")
    private String taskFileId;

    @Column(name = "weld_no", length = 100)
    @JsonProperty("WeldNo")
    private String weldNo;

    @Column(name = "sort_order")
    @JsonProperty("SortOrder")
    private Integer sortOrder = 0;

    @Column(name = "created_at")
    @JsonProperty("CreatedAt")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    @JsonProperty("UpdatedAt")
    private LocalDateTime updatedAt;

    public WeldJoint() {}

    public WeldJoint(String weldJointId, String taskFileId, String weldNo, Integer sortOrder) {
        this.weldJointId = weldJointId;
        this.taskFileId = taskFileId;
        this.weldNo = weldNo;
        this.sortOrder = sortOrder;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    public String getWeldJointId() {
        return weldJointId;
    }

    public void setWeldJointId(String weldJointId) {
        this.weldJointId = weldJointId;
    }

    public String getTaskFileId() {
        return taskFileId;
    }

    public void setTaskFileId(String taskFileId) {
        this.taskFileId = taskFileId;
        this.updatedAt = LocalDateTime.now();
    }

    public String getWeldNo() {
        return weldNo;
    }

    public void setWeldNo(String weldNo) {
        this.weldNo = weldNo;
        this.updatedAt = LocalDateTime.now();
    }

    public Integer getSortOrder() {
        return sortOrder;
    }

    public void setSortOrder(Integer sortOrder) {
        this.sortOrder = sortOrder;
        this.updatedAt = LocalDateTime.now();
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        this.updatedAt = LocalDateTime.now();
    }

    @Override
    public String toString() {
        return "WeldJoint{" +
                "weldJointId='" + weldJointId + '\'' +
                ", taskFileId='" + taskFileId + '\'' +
                ", weldNo='" + weldNo + '\'' +
                ", sortOrder=" + sortOrder +
                '}';
    }
}
