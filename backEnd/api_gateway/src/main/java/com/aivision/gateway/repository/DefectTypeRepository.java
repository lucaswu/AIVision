package com.aivision.gateway.repository;

import com.aivision.gateway.model.DefectType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface DefectTypeRepository extends JpaRepository<DefectType, String> {
    List<DefectType> findByEnabledTrueOrderBySortOrderAsc();
}
