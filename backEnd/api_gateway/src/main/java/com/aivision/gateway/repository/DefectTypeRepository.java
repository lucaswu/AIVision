package com.aivision.gateway.repository;

import com.aivision.gateway.model.DefectType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface DefectTypeRepository extends JpaRepository<DefectType, String> {
    List<DefectType> findByEnabledTrueOrderBySortOrderAsc();
    
    /**
     * 获取所有启用的缺陷类型名称（去除括号内容），用于传递给推理服务
     * 使用原生 SQL 查询以支持 regexp_replace 函数
     */
    @Query(value = "SELECT regexp_replace(name, '\\(.*?\\)', '', 'g') FROM defect_type WHERE enabled = true ORDER BY sort_order ASC", nativeQuery = true)
    List<String> findAllEnabledDefectTypeNames();
    
    /**
     * 根据名称模糊匹配缺陷类型（用于匹配推理结果中的 class_name）
     */
    @Query("SELECT d FROM DefectType d WHERE d.enabled = true AND d.name LIKE %:className%")
    Optional<DefectType> findByNameContaining(@Param("className") String className);
}
