package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import javax.persistence.*;
import java.time.LocalDateTime;

/**
 * 缺陷记录实体 - 存储单个缺陷的详细信息
 * 每个 TaskFile 可以关联多个 DefectRecord
 */
@Entity
@Table(name = "defect_record")
public class DefectRecord {

    @Id
    @Column(name = "defect_record_id", length = 255)
    @JsonProperty("DefectRecordId")
    private String defectRecordId;

    @Column(name = "task_file_id", nullable = false, length = 255)
    @JsonProperty("TaskFileId")
    private String taskFileId;

    @Column(name = "weld_joint_id", length = 255)
    @JsonProperty("WeldJointId")
    private String weldJointId;

    @Column(name = "defect_name", length = 100)
    @JsonProperty("DefectName")
    private String defectName;

    @Column(name = "position", length = 100)
    @JsonProperty("Position")
    private String position;

    @Column(name = "size", length = 100)
    @JsonProperty("Size")
    private String size;

    @Column(name = "grade", length = 20)
    @JsonProperty("Grade")
    private String grade;

    @Column(name = "remark", columnDefinition = "TEXT")
    @JsonProperty("Remark")
    private String remark;

    @Column(name = "geometry", columnDefinition = "TEXT")
    @JsonProperty("Geometry")
    private String geometry;

    @Column(name = "created_at")
    @JsonProperty("CreatedAt")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    @JsonProperty("UpdatedAt")
    private LocalDateTime updatedAt;

    // Constructors
    public DefectRecord() {}

    public DefectRecord(String defectRecordId, String taskFileId, String defectName,
                        String position, String size, String grade, String remark) {
        this.defectRecordId = defectRecordId;
        this.taskFileId = taskFileId;
        this.defectName = defectName;
        this.position = position;
        this.size = size;
        this.grade = grade;
        this.remark = remark;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    // Getters and Setters
    public String getDefectRecordId() {
        return defectRecordId;
    }

    public void setDefectRecordId(String defectRecordId) {
        this.defectRecordId = defectRecordId;
    }

    public String getTaskFileId() {
        return taskFileId;
    }

    public void setTaskFileId(String taskFileId) {
        this.taskFileId = taskFileId;
        this.updatedAt = LocalDateTime.now();
    }

    public String getWeldJointId() {
        return weldJointId;
    }

    public void setWeldJointId(String weldJointId) {
        this.weldJointId = weldJointId;
        this.updatedAt = LocalDateTime.now();
    }

    public String getDefectName() {
        return defectName;
    }

    public void setDefectName(String defectName) {
        this.defectName = defectName;
        this.updatedAt = LocalDateTime.now();
    }

    public String getPosition() {
        return position;
    }

    public void setPosition(String position) {
        this.position = position;
        this.updatedAt = LocalDateTime.now();
    }

    public String getSize() {
        return size;
    }

    public void setSize(String size) {
        this.size = size;
        this.updatedAt = LocalDateTime.now();
    }

    public String getGrade() {
        return grade;
    }

    public void setGrade(String grade) {
        this.grade = grade;
        this.updatedAt = LocalDateTime.now();
    }

    public String getRemark() {
        return remark;
    }

    public void setRemark(String remark) {
        this.remark = remark;
        this.updatedAt = LocalDateTime.now();
    }

    public String getGeometry() {
        return geometry;
    }

    public void setGeometry(String geometry) {
        this.geometry = geometry;
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
        return "DefectRecord{" +
                "defectRecordId='" + defectRecordId + '\'' +
                ", taskFileId='" + taskFileId + '\'' +
                ", weldJointId='" + weldJointId + '\'' +
                ", defectName='" + defectName + '\'' +
                ", position='" + position + '\'' +
                ", size='" + size + '\'' +
                ", grade='" + grade + '\'' +
                ", remark='" + remark + '\'' +
                ", geometry='" + geometry + '\'' +
                ", createdAt=" + createdAt +
                ", updatedAt=" + updatedAt +
                '}';
    }
}
