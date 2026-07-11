package com.aivision.gateway.repository;

import com.aivision.gateway.model.WeldJoint;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collection;
import java.util.List;

/**
 * 焊口记录数据访问层
 */
@Repository
public interface WeldJointRepository extends JpaRepository<WeldJoint, String> {

    /**
     * 根据 TaskFileId 查询所有焊口记录（按顺序）
     */
    List<WeldJoint> findByTaskFileIdOrderBySortOrderAsc(String taskFileId);

    /**
     * 根据 TaskFileId 删除所有焊口记录
     */
    @Transactional
    void deleteByTaskFileId(String taskFileId);

    /**
     * 删除某个 TaskFile 下、不在给定 id 集合中的焊口记录（被用户移除的焊口）
     */
    @Transactional
    void deleteByTaskFileIdAndWeldJointIdNotIn(String taskFileId, Collection<String> keepIds);

    /**
     * 查询按项目/焊口编号列表过滤的焊口记录（跨项目检索用）
     */
    @Query("SELECT wj FROM WeldJoint wj JOIN TaskFile tf ON wj.taskFileId = tf.taskFileId " +
           "JOIN Task t ON tf.taskId = t.taskId " +
           "WHERE t.projectId IN :projectIds AND wj.weldNo IN :weldNos")
    List<WeldJoint> findByProjectIdsAndWeldNos(@Param("projectIds") List<String> projectIds,
                                                @Param("weldNos") List<String> weldNos);
}
