package com.aivision.gateway.repository;

import com.aivision.gateway.model.DefectRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 缺陷记录数据访问层
 */
@Repository
public interface DefectRecordRepository extends JpaRepository<DefectRecord, String> {

    /**
     * 根据 TaskFileId 查询所有缺陷记录
     */
    List<DefectRecord> findByTaskFileId(String taskFileId);

    /**
     * 根据 TaskFileId 删除所有缺陷记录
     */
    @Transactional
    void deleteByTaskFileId(String taskFileId);

    /**
     * 根据 TaskFileId 统计缺陷数量
     */
    long countByTaskFileId(String taskFileId);
}
