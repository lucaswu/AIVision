package com.aivision.gateway.service;

import com.aivision.gateway.model.DefectRecord;
import com.aivision.gateway.repository.DefectRecordRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 缺陷记录服务层
 */
@Service
public class DefectRecordService {

    @Autowired
    private DefectRecordRepository defectRecordRepository;

    /**
     * 根据 TaskFileId 获取所有缺陷记录
     */
    public List<DefectRecord> getDefectRecordsByTaskFileId(String taskFileId) {
        return defectRecordRepository.findByTaskFileId(taskFileId);
    }

    /**
     * 根据 ID 获取单个缺陷记录
     */
    public Optional<DefectRecord> getDefectRecordById(String defectRecordId) {
        return defectRecordRepository.findById(defectRecordId);
    }

    /**
     * 创建缺陷记录
     */
    public DefectRecord createDefectRecord(DefectRecord defectRecord) {
        if (defectRecord.getDefectRecordId() == null || defectRecord.getDefectRecordId().isEmpty()) {
            defectRecord.setDefectRecordId(UUID.randomUUID().toString());
        }
        defectRecord.setCreatedAt(LocalDateTime.now());
        defectRecord.setUpdatedAt(LocalDateTime.now());
        return defectRecordRepository.save(defectRecord);
    }

    /**
     * 批量创建缺陷记录
     */
    @Transactional
    public List<DefectRecord> createDefectRecords(List<DefectRecord> defectRecords) {
        for (DefectRecord record : defectRecords) {
            if (record.getDefectRecordId() == null || record.getDefectRecordId().isEmpty()) {
                record.setDefectRecordId(UUID.randomUUID().toString());
            }
            record.setCreatedAt(LocalDateTime.now());
            record.setUpdatedAt(LocalDateTime.now());
        }
        return defectRecordRepository.saveAll(defectRecords);
    }

    /**
     * 更新缺陷记录
     */
    public DefectRecord updateDefectRecord(String defectRecordId, DefectRecord updatedRecord) {
        return defectRecordRepository.findById(defectRecordId)
            .map(existing -> {
                existing.setDefectName(updatedRecord.getDefectName());
                existing.setPosition(updatedRecord.getPosition());
                existing.setSize(updatedRecord.getSize());
                existing.setGrade(updatedRecord.getGrade());
                existing.setRemark(updatedRecord.getRemark());
                existing.setUpdatedAt(LocalDateTime.now());
                return defectRecordRepository.save(existing);
            })
            .orElseThrow(() -> new RuntimeException("缺陷记录不存在: " + defectRecordId));
    }

    /**
     * 删除单个缺陷记录
     */
    public void deleteDefectRecord(String defectRecordId) {
        defectRecordRepository.deleteById(defectRecordId);
    }

    /**
     * 删除某个 TaskFile 的所有缺陷记录
     */
    @Transactional
    public void deleteDefectRecordsByTaskFileId(String taskFileId) {
        defectRecordRepository.deleteByTaskFileId(taskFileId);
    }

    /**
     * 替换某个 TaskFile 的所有缺陷记录（先删后增）
     */
    @Transactional
    public List<DefectRecord> replaceDefectRecords(String taskFileId, List<DefectRecord> newRecords) {
        defectRecordRepository.deleteByTaskFileId(taskFileId);
        for (DefectRecord record : newRecords) {
            record.setTaskFileId(taskFileId);
            if (record.getDefectRecordId() == null || record.getDefectRecordId().isEmpty()) {
                record.setDefectRecordId(UUID.randomUUID().toString());
            }
            record.setCreatedAt(LocalDateTime.now());
            record.setUpdatedAt(LocalDateTime.now());
        }
        return defectRecordRepository.saveAll(newRecords);
    }

    /**
     * 统计某个 TaskFile 的缺陷数量
     */
    public long countDefectsByTaskFileId(String taskFileId) {
        return defectRecordRepository.countByTaskFileId(taskFileId);
    }
}
