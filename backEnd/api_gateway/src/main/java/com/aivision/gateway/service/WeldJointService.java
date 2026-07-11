package com.aivision.gateway.service;

import com.aivision.gateway.model.WeldJoint;
import com.aivision.gateway.repository.WeldJointRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 焊口记录服务层
 */
@Service
public class WeldJointService {

    @Autowired
    private WeldJointRepository weldJointRepository;

    /**
     * 根据 TaskFileId 获取所有焊口记录（按顺序）
     */
    public List<WeldJoint> getWeldJointsByTaskFileId(String taskFileId) {
        return weldJointRepository.findByTaskFileIdOrderBySortOrderAsc(taskFileId);
    }

    /**
     * 替换某个 TaskFile 的焊口列表。
     * 与 defect_record 不同，焊口记录会被 defect_record.weld_joint_id 引用，
     * 因此这里采用 diff 式 upsert（已有 id 更新、新 id 插入、被移除的 id 才删除），
     * 而不是简单粗暴地全部删除重建，避免同一编辑会话内缺陷引用的焊口 id 失效。
     * 被移除焊口关联的缺陷记录，其 weld_joint_id 由数据库外键 ON DELETE SET NULL 自动置空。
     */
    @Transactional
    public List<WeldJoint> replaceWeldJoints(String taskFileId, List<WeldJoint> newJoints) {
        Set<String> keepIds = newJoints.stream()
            .map(WeldJoint::getWeldJointId)
            .filter(id -> id != null && !id.isEmpty())
            .collect(Collectors.toSet());

        if (keepIds.isEmpty()) {
            weldJointRepository.deleteByTaskFileId(taskFileId);
        } else {
            weldJointRepository.deleteByTaskFileIdAndWeldJointIdNotIn(taskFileId, keepIds);
        }

        // 已存在的焊口在受管实体上更新（保留 createdAt），新 id 才插入；
        // 不能直接 saveAll 请求体里的游离实体，否则 merge 会把 createdAt 冲成 null
        Map<String, WeldJoint> existingById = weldJointRepository
            .findByTaskFileIdOrderBySortOrderAsc(taskFileId)
            .stream()
            .collect(Collectors.toMap(WeldJoint::getWeldJointId, joint -> joint));

        List<WeldJoint> toSave = new ArrayList<>();
        for (int i = 0; i < newJoints.size(); i++) {
            WeldJoint incoming = newJoints.get(i);
            WeldJoint existing = incoming.getWeldJointId() == null
                ? null
                : existingById.get(incoming.getWeldJointId());

            if (existing != null) {
                existing.setWeldNo(incoming.getWeldNo());
                existing.setSortOrder(i);
                toSave.add(existing);
            } else {
                if (incoming.getWeldJointId() == null || incoming.getWeldJointId().isEmpty()) {
                    incoming.setWeldJointId(UUID.randomUUID().toString());
                }
                incoming.setTaskFileId(taskFileId);
                incoming.setSortOrder(i);
                incoming.setCreatedAt(LocalDateTime.now());
                incoming.setUpdatedAt(LocalDateTime.now());
                toSave.add(incoming);
            }
        }

        return weldJointRepository.saveAll(toSave);
    }

    /**
     * 删除某个 TaskFile 的所有焊口记录
     */
    @Transactional
    public void deleteWeldJointsByTaskFileId(String taskFileId) {
        weldJointRepository.deleteByTaskFileId(taskFileId);
    }
}
