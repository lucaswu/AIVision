package com.aivision.gateway.repository;

import com.aivision.gateway.model.File;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface FileRepository extends JpaRepository<File, String> {
    
    /**
     * 根据项目ID和用户ID查找文件
     */
    List<File> findByProjectIdAndUserIdOrderByCreatedAtDesc(String projectId, String userId);
    
    /**
     * 根据目录ID查找文件
     */
    List<File> findByDirectoryIdOrderByCreatedAtDesc(String directoryId);
    
    /**
     * 根据项目ID、用户ID和目录ID查找文件
     */
    List<File> findByProjectIdAndUserIdAndDirectoryIdOrderByCreatedAtDesc(String projectId, String userId, String directoryId);
    
    /**
     * 根据文件ID、项目ID和用户ID查找文件
     */
    Optional<File> findByFileIdAndProjectIdAndUserId(String fileId, String projectId, String userId);
    
    /**
     * 统计目录下的文件数量
     */
    @Query("SELECT COUNT(f) FROM File f WHERE f.directoryId = :directoryId")
    long countByDirectoryId(@Param("directoryId") String directoryId);
    
    /**
     * 统计项目下的文件数量
     */
    @Query("SELECT COUNT(f) FROM File f WHERE f.projectId = :projectId AND f.userId = :userId")
    long countByProjectIdAndUserId(@Param("projectId") String projectId, @Param("userId") String userId);

    /**
     * 统计项目下的所有文件数量（不区分用户）
     */
    long countByProjectId(String projectId);
    
    /**
     * 计算目录下文件总大小
     */
    @Query("SELECT COALESCE(SUM(f.fileSize), 0) FROM File f WHERE f.directoryId = :directoryId")
    long sumFileSizeByDirectoryId(@Param("directoryId") String directoryId);
    
    /**
     * 计算用户在项目下的文件总大小
     */
    @Query("SELECT COALESCE(SUM(f.fileSize), 0) FROM File f WHERE f.projectId = :projectId AND f.userId = :userId")
    long sumFileSizeByProjectIdAndUserId(@Param("projectId") String projectId, @Param("userId") String userId);
    
    /**
     * 根据项目ID查找所有文件（用于构建文件树）
     */
    List<File> findByProjectIdOrderByDirectoryIdAscCreatedAtDesc(String projectId);

    /**
     * 批量查询文件详情
     */
    List<File> findByFileIdIn(List<String> fileIds);
} 