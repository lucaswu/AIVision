package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.ArrayList;
import java.util.List;

/**
 * 单任务详细报告结果（第三方报告系统对接用）
 * GET /api/v1/tasks/{task_id}/report-result
 */
public class TaskReportResultResponse {

    @JsonProperty("TaskId")
    private String taskId;

    @JsonProperty("TaskName")
    private String taskName;

    @JsonProperty("ProjectId")
    private String projectId;

    @JsonProperty("ProjectName")
    private String projectName;

    @JsonProperty("Status")
    private String status;

    @JsonProperty("CreateTime")
    private String createTime;

    @JsonProperty("EndTime")
    private String endTime;

    @JsonProperty("ReportItems")
    private List<ReportResultResponse.ReportItem> reportItems = new ArrayList<>();

    @JsonProperty("Total")
    private Integer total = 0;

    public String getTaskId() { return taskId; }
    public void setTaskId(String taskId) { this.taskId = taskId; }

    public String getTaskName() { return taskName; }
    public void setTaskName(String taskName) { this.taskName = taskName; }

    public String getProjectId() { return projectId; }
    public void setProjectId(String projectId) { this.projectId = projectId; }

    public String getProjectName() { return projectName; }
    public void setProjectName(String projectName) { this.projectName = projectName; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getCreateTime() { return createTime; }
    public void setCreateTime(String createTime) { this.createTime = createTime; }

    public String getEndTime() { return endTime; }
    public void setEndTime(String endTime) { this.endTime = endTime; }

    public List<ReportResultResponse.ReportItem> getReportItems() { return reportItems; }
    public void setReportItems(List<ReportResultResponse.ReportItem> reportItems) {
        this.reportItems = reportItems != null ? reportItems : new ArrayList<>();
        this.total = this.reportItems.size();
    }

    public Integer getTotal() { return total; }
    public void setTotal(Integer total) { this.total = total; }
}
