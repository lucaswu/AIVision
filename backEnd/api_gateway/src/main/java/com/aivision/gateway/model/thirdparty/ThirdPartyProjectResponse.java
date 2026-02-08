package com.aivision.gateway.model.thirdparty;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

public class ThirdPartyProjectResponse {
    private int code;
    private boolean success;
    private String msg;
    private List<ProjectItem> data;

    public int getCode() {
        return code;
    }

    public void setCode(int code) {
        this.code = code;
    }

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public String getMsg() {
        return msg;
    }

    public void setMsg(String msg) {
        this.msg = msg;
    }

    public List<ProjectItem> getData() {
        return data;
    }

    public void setData(List<ProjectItem> data) {
        this.data = data;
    }

    @Override
    public String toString() {
        return "ThirdPartyProjectResponse{" +
                "code=" + code +
                ", success=" + success +
                ", msg='" + msg + '\'' +
                ", data=" + data +
                '}';
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class ProjectItem {
        private String id;
        private String projectName;
        private String projectOrderNumber;
        private String projectNumber;
        private String constructionUnit;
        private String client;
        private String projectAddress;
        private String createTime;
        private String projectYear;
        private String projectInitiationDate;
        private String commencementDate;
        private String completionDate;
        private String estimatedCompletionDate;

        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id;
        }

        public String getProjectName() {
            return projectName;
        }

        public void setProjectName(String projectName) {
            this.projectName = projectName;
        }

        public String getProjectOrderNumber() {
            return projectOrderNumber;
        }

        public void setProjectOrderNumber(String projectOrderNumber) {
            this.projectOrderNumber = projectOrderNumber;
        }

        public String getProjectNumber() {
            return projectNumber;
        }

        public void setProjectNumber(String projectNumber) {
            this.projectNumber = projectNumber;
        }

        public String getConstructionUnit() {
            return constructionUnit;
        }

        public void setConstructionUnit(String constructionUnit) {
            this.constructionUnit = constructionUnit;
        }

        public String getClient() {
            return client;
        }

        public void setClient(String client) {
            this.client = client;
        }

        public String getProjectAddress() {
            return projectAddress;
        }

        public void setProjectAddress(String projectAddress) {
            this.projectAddress = projectAddress;
        }

        public String getCreateTime() {
            return createTime;
        }

        public void setCreateTime(String createTime) {
            this.createTime = createTime;
        }

        public String getProjectYear() {
            return projectYear;
        }

        public void setProjectYear(String projectYear) {
            this.projectYear = projectYear;
        }

        public String getProjectInitiationDate() {
            return projectInitiationDate;
        }

        public void setProjectInitiationDate(String projectInitiationDate) {
            this.projectInitiationDate = projectInitiationDate;
        }

        public String getCommencementDate() {
            return commencementDate;
        }

        public void setCommencementDate(String commencementDate) {
            this.commencementDate = commencementDate;
        }

        public String getCompletionDate() {
            return completionDate;
        }

        public void setCompletionDate(String completionDate) {
            this.completionDate = completionDate;
        }

        public String getEstimatedCompletionDate() {
            return estimatedCompletionDate;
        }

        @Override
        public String toString() {
            return "ProjectItem{" +
                    "id='" + id + '\'' +
                    ", projectName='" + projectName + '\'' +
                    ", projectOrderNumber='" + projectOrderNumber + '\'' +
                    ", projectNumber='" + projectNumber + '\'' +
                    ", constructionUnit='" + constructionUnit + '\'' +
                    ", client='" + client + '\'' +
                    ", projectAddress='" + projectAddress + '\'' +
                    ", createTime='" + createTime + '\'' +
                    ", projectYear='" + projectYear + '\'' +
                    ", projectInitiationDate='" + projectInitiationDate + '\'' +
                    ", commencementDate='" + commencementDate + '\'' +
                    ", completionDate='" + completionDate + '\'' +
                    ", estimatedCompletionDate='" + estimatedCompletionDate + '\'' +
                    '}';
        }
    }
}
