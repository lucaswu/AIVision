package com.aivision.gateway.repository;

import com.aivision.gateway.model.Report;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ReportRepository extends JpaRepository<Report, String> {
    List<Report> findByProjectIdOrderByCreatedAtDesc(String projectId);
    Optional<Report> findByTaskId(String taskId);
    void deleteByTaskId(String taskId);
}

