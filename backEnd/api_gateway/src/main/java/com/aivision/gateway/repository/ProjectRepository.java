package com.aivision.gateway.repository;

import com.aivision.gateway.model.Project;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ProjectRepository extends JpaRepository<Project, String> {
    
    // 根据项目所有者查找项目
    List<Project> findByOwnerId(String ownerId);
    
    // 根据项目状态查找项目
    List<Project> findByStatus(Project.Status status);
    
    // 根据项目类型查找项目
    List<Project> findByProjectType(String projectType);
    
    // 根据所有者分页查询项目
    Page<Project> findByOwnerId(String ownerId, Pageable pageable);
    
    // 根据状态分页查询项目
    Page<Project> findByStatus(Project.Status status, Pageable pageable);
    
    // 根据项目名称模糊搜索
    @Query("SELECT p FROM Project p WHERE p.projectName LIKE %:keyword% OR p.description LIKE %:keyword%")
    Page<Project> searchProjects(@Param("keyword") String keyword, Pageable pageable);
    
    // 根据所有者和状态查找项目
    List<Project> findByOwnerIdAndStatus(String ownerId, Project.Status status);
    
    // 检查项目名称是否存在（同一个所有者下）
    boolean existsByProjectNameAndOwnerId(String projectName, String ownerId);
    
    // 统计用户的项目数量
    long countByOwnerId(String ownerId);
    
    // 统计各状态下的项目数量
    long countByStatus(Project.Status status);
}
