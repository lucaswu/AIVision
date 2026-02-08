package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public class ReportResultResponse {
    
    @JsonProperty("ReportItems")
    private List<ReportItem> reportItems;
    
    @JsonProperty("Total")
    private Integer total;
    
    public ReportResultResponse(List<ReportItem> reportItems) {
        this.reportItems = reportItems;
        this.total = reportItems != null ? reportItems.size() : 0;
    }
    
    public List<ReportItem> getReportItems() {
        return reportItems;
    }
    
    public void setReportItems(List<ReportItem> reportItems) {
        this.reportItems = reportItems;
        this.total = reportItems != null ? reportItems.size() : 0;
    }
    
    public Integer getTotal() {
        return total;
    }
    
    public void setTotal(Integer total) {
        this.total = total;
    }
    
    public static class ReportItem {
        @JsonProperty("FileId")
        private String fileId;
        
        @JsonProperty("FileName")
        private String fileName;
        
        @JsonProperty("WeldNo")
        private String weldNo;
        
        @JsonProperty("SliceNo")
        private String sliceNo;
        
        @JsonProperty("FilmDensity")
        private String filmDensity;
        
        @JsonProperty("IQISensitivity")
        private String iqiSensitivity;
        
        @JsonProperty("QualityLevel")
        private String qualityLevel;
        
        @JsonProperty("EvaluationResult")
        private String evaluationResult;
        
        @JsonProperty("Remark")
        private String remark;
        
        @JsonProperty("Defects")
        private List<DefectItem> defects;
        
        // Getters and Setters
        public String getFileId() { return fileId; }
        public void setFileId(String fileId) { this.fileId = fileId; }
        
        public String getFileName() { return fileName; }
        public void setFileName(String fileName) { this.fileName = fileName; }
        
        public String getWeldNo() { return weldNo; }
        public void setWeldNo(String weldNo) { this.weldNo = weldNo; }
        
        public String getSliceNo() { return sliceNo; }
        public void setSliceNo(String sliceNo) { this.sliceNo = sliceNo; }
        
        public String getFilmDensity() { return filmDensity; }
        public void setFilmDensity(String filmDensity) { this.filmDensity = filmDensity; }
        
        public String getIqiSensitivity() { return iqiSensitivity; }
        public void setIqiSensitivity(String iqiSensitivity) { this.iqiSensitivity = iqiSensitivity; }
        
        public String getQualityLevel() { return qualityLevel; }
        public void setQualityLevel(String qualityLevel) { this.qualityLevel = qualityLevel; }
        
        public String getEvaluationResult() { return evaluationResult; }
        public void setEvaluationResult(String evaluationResult) { this.evaluationResult = evaluationResult; }
        
        public String getRemark() { return remark; }
        public void setRemark(String remark) { this.remark = remark; }
        
        public List<DefectItem> getDefects() { return defects; }
        public void setDefects(List<DefectItem> defects) { this.defects = defects; }
    }
    
    public static class DefectItem {
        @JsonProperty("DefectId")
        private String defectId;
        
        @JsonProperty("DefectNature")
        private String defectNature;
        
        @JsonProperty("DefectLocation")
        private String defectLocation;
        
        @JsonProperty("DefectSize")
        private String defectSize;
        
        @JsonProperty("DefectLevel")
        private String defectLevel;
        
        @JsonProperty("Remark")
        private String remark;
        
        // Getters and Setters
        public String getDefectId() { return defectId; }
        public void setDefectId(String defectId) { this.defectId = defectId; }
        
        public String getDefectNature() { return defectNature; }
        public void setDefectNature(String defectNature) { this.defectNature = defectNature; }
        
        public String getDefectLocation() { return defectLocation; }
        public void setDefectLocation(String defectLocation) { this.defectLocation = defectLocation; }
        
        public String getDefectSize() { return defectSize; }
        public void setDefectSize(String defectSize) { this.defectSize = defectSize; }
        
        public String getDefectLevel() { return defectLevel; }
        public void setDefectLevel(String defectLevel) { this.defectLevel = defectLevel; }
        
        public String getRemark() { return remark; }
        public void setRemark(String remark) { this.remark = remark; }
    }
}
