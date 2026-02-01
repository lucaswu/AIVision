package com.aivision.gateway.repository;

import com.aivision.gateway.model.Task;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface TaskRepository extends JpaRepository<Task, String> {
    
    /**
     * 根据项目ID和用户ID查找任务
     */
    List<Task> findByProjectIdAndUserIdOrderByCreatedAtDesc(String projectId, String userId);
    
    /**
     * 根据用户ID查找任务
     */
    List<Task> findByUserIdOrderByCreatedAtDesc(String userId);
    
    /**
     * 根据状态查找任务
     */
    List<Task> findByStatusOrderByCreatedAtDesc(Task.Status status);
    
    /**
     * 根据项目ID、用户ID和状态查找任务
     */
    List<Task> findByProjectIdAndUserIdAndStatusOrderByCreatedAtDesc(String projectId, String userId, Task.Status status);
    
    /**
     * 根据任务ID、项目ID和用户ID查找任务（用于权限验证）
     */
    Optional<Task> findByTaskIdAndProjectIdAndUserId(String taskId, String projectId, String userId);
    
    /**
     * 统计用户的任务数量
     */
    @Query("SELECT COUNT(t) FROM Task t WHERE t.userId = :userId")
    long countByUserId(@Param("userId") String userId);
    
    /**
     * 统计项目下的任务数量
     */
    @Query("SELECT COUNT(t) FROM Task t WHERE t.projectId = :projectId AND t.userId = :userId")
    long countByProjectIdAndUserId(@Param("projectId") String projectId, @Param("userId") String userId);
    
    /**
     * 统计不同状态的任务数量
     */
    @Query("SELECT COUNT(t) FROM Task t WHERE t.userId = :userId AND t.status = :status")
    long countByUserIdAndStatus(@Param("userId") String userId, @Param("status") Task.Status status);
    
    /**
     * 查找需要处理的任务（状态为PENDING或PROCESSING）
     */
    @Query("SELECT t FROM Task t WHERE t.status IN ('PENDING', 'PROCESSING') ORDER BY t.createdAt ASC")
    List<Task> findPendingAndProcessingTasks();
    
    /**
     * 根据项目ID查找所有任务（用于项目统计）
     */
    List<Task> findByProjectIdOrderByCreatedAtDesc(String projectId);

    /**
     * 根据项目ID删除任务
     */
    void deleteByProjectId(String projectId);
} 