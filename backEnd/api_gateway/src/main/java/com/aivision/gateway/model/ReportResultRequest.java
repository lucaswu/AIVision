package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public class ReportResultRequest {
    
    @JsonProperty("projectIds")
    private List<String> projectIds;
    
    @JsonProperty("weldNos")
    private List<String> weldNos;
    
    public List<String> getProjectIds() {
        return projectIds;
    }
    
    public void setProjectIds(List<String> projectIds) {
        this.projectIds = projectIds;
    }
    
    public List<String> getWeldNos() {
        return weldNos;
    }
    
    public void setWeldNos(List<String> weldNos) {
        this.weldNos = weldNos;
    }
}
