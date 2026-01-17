package com.aivision.gateway.controller;

import com.aivision.gateway.model.ApiResponse;
import com.aivision.gateway.model.DefectType;
import com.aivision.gateway.repository.DefectTypeRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/defect-types")
@CrossOrigin(origins = "*")
@Tag(name = "缺陷类型管理", description = "焊缝缺陷类型配置接口")
public class DefectTypeController {
    
    @Autowired
    private DefectTypeRepository defectTypeRepository;

    @GetMapping
    @Operation(summary = "获取所有启用的缺陷类型")
    public ResponseEntity<ApiResponse<List<DefectType>>> getDefectTypes() {
        try {
            List<DefectType> types = defectTypeRepository.findByEnabledTrueOrderBySortOrderAsc();
            return ResponseEntity.ok(ApiResponse.success("获取成功", types));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(ApiResponse.error(500, e.getMessage()));
        }
    }
}
