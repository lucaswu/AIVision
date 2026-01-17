package com.aivision.gateway.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import javax.persistence.*;

@Entity
@Table(name = "defect_type")
public class DefectType {
    
    @Id
    @Column(name = "code", length = 50)
    @JsonProperty("Code")
    private String code;
    
    @Column(name = "name", nullable = false, length = 100)
    @JsonProperty("Name")
    private String name;
    
    @Column(name = "color", nullable = false, length = 20)
    @JsonProperty("Color")
    private String color;
    
    @Column(name = "sort_order")
    @JsonProperty("SortOrder")
    private Integer sortOrder = 0;
    
    @Column(name = "enabled")
    @JsonProperty("Enabled")
    private Boolean enabled = true;

    // Constructors
    public DefectType() {}

    public DefectType(String code, String name, String color, Integer sortOrder) {
        this.code = code;
        this.name = name;
        this.color = color;
        this.sortOrder = sortOrder;
        this.enabled = true;
    }

    // Getters and Setters
    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getColor() { return color; }
    public void setColor(String color) { this.color = color; }

    public Integer getSortOrder() { return sortOrder; }
    public void setSortOrder(Integer sortOrder) { this.sortOrder = sortOrder; }

    public Boolean getEnabled() { return enabled; }
    public void setEnabled(Boolean enabled) { this.enabled = enabled; }
}
