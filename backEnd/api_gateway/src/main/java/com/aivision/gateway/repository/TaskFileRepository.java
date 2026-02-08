package com.aivision.gateway.repository;

import com.aivision.gateway.model.TaskFile;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface TaskFileRepository extends JpaRepository<TaskFile, String> {
    
    /**
     * 根据任务ID查找所有任务文件
     */
    List<TaskFile> findByTaskIdOrderByCreatedAtAsc(String taskId);
    
    /**
     * 根据任务ID和状态查找任务文件
     */
    List<TaskFile> findByTaskIdAndStatusOrderByCreatedAtAsc(String taskId, TaskFile.Status status);
    
    /**
     * 根据文件ID查找任务文件
     */
    List<TaskFile> findByFileIdOrderByCreatedAtDesc(String fileId);
    
    /**
     * 根据任务文件ID和任务ID查找任务文件（用于权限验证）
     */
    Optional<TaskFile> findByTaskFileIdAndTaskId(String taskFileId, String taskId);
    
    /**
     * 统计任务下的文件数量
     */
    @Query("SELECT COUNT(tf) FROM TaskFile tf WHERE tf.taskId = :taskId")
    long countByTaskId(@Param("taskId") String taskId);
    
    /**
     * 统计任务下指定状态的文件数量
     */
    @Query("SELECT COUNT(tf) FROM TaskFile tf WHERE tf.taskId = :taskId AND tf.status = :status")
    long countByTaskIdAndStatus(@Param("taskId") String taskId, @Param("status") TaskFile.Status status);
    
    /**
     * 查找任务下待处理的文件
     */
    @Query("SELECT tf FROM TaskFile tf WHERE tf.taskId = :taskId AND tf.status = 'PENDING' ORDER BY tf.createdAt ASC")
    List<TaskFile> findPendingFilesByTaskId(@Param("taskId") String taskId);
    
    /**
     * 查找任务下正在处理的文件
     */
    @Query("SELECT tf FROM TaskFile tf WHERE tf.taskId = :taskId AND tf.status = 'PROCESSING' ORDER BY tf.processingStartTime ASC")
    List<TaskFile> findProcessingFilesByTaskId(@Param("taskId") String taskId);
    
    /**
     * 查找任务下已完成的文件
     */
    @Query("SELECT tf FROM TaskFile tf WHERE tf.taskId = :taskId AND tf.status = 'COMPLETED' ORDER BY tf.processingEndTime DESC")
    List<TaskFile> findCompletedFilesByTaskId(@Param("taskId") String taskId);
    
    /**
     * 查找任务下失败的文件
     */
    @Query("SELECT tf FROM TaskFile tf WHERE tf.taskId = :taskId AND tf.status = 'FAILED' ORDER BY tf.processingEndTime DESC")
    List<TaskFile> findFailedFilesByTaskId(@Param("taskId") String taskId);
    
    /**
     * 删除任务下的所有文件记录
     */
    void deleteByTaskId(String taskId);
    
    /**
     * 查找所有待处理的文件（跨任务）
     */
    @Query("SELECT tf FROM TaskFile tf WHERE tf.status = 'PENDING' ORDER BY tf.createdAt ASC")
    List<TaskFile> findAllPendingFiles();
    
    /**
     * 根据MinIO文件路径查找任务文件
     */
    Optional<TaskFile> findByMinioFilePath(String minioFilePath);

    /**
     * 批量查询多个任务ID下的所有文件记录
     */
    List<TaskFile> findByTaskIdInOrderByCreatedAtAsc(List<String> taskIds);

    /**
     * 根据项目ID列表和工件编号列表查询任务文件
     */
    @Query("SELECT tf FROM TaskFile tf JOIN Task t ON tf.taskId = t.taskId " +
           "WHERE t.projectId IN :projectIds AND tf.weldId IN :weldNos " +
           "ORDER BY tf.createdAt DESC")
    List<TaskFile> findByProjectIdsAndWeldNos(@Param("projectIds") List<String> projectIds, 
                                             @Param("weldNos") List<String> weldNos);

    /**
     * 根据项目ID列表查询任务文件（不过滤工件编号）
     */
    @Query("SELECT tf FROM TaskFile tf JOIN Task t ON tf.taskId = t.taskId " +
           "WHERE t.projectId IN :projectIds " +
           "ORDER BY tf.createdAt DESC")
    List<TaskFile> findByProjectIds(@Param("projectIds") List<String> projectIds);
} 