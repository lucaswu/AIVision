-- v9_weld_joint.sql
-- 支持一张底片(task_file)关联多个焊口编号：新增 weld_joint 表，
-- defect_record 增加 weld_joint_id 外键标识每条缺陷所属的焊口

-- 1. 创建焊口表
CREATE TABLE IF NOT EXISTS weld_joint (
    weld_joint_id VARCHAR(255) PRIMARY KEY,
    task_file_id VARCHAR(255) NOT NULL,
    weld_no VARCHAR(100),            -- 焊口编号
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    CONSTRAINT fk_weld_joint_task_file
        FOREIGN KEY (task_file_id)
        REFERENCES task_file(task_file_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_weld_joint_task_file_id ON weld_joint(task_file_id);
CREATE INDEX IF NOT EXISTS idx_weld_joint_weld_no ON weld_joint(weld_no);

-- 2. defect_record 增加所属焊口字段（可空，兼容未分配焊口的缺陷）
ALTER TABLE defect_record ADD COLUMN IF NOT EXISTS weld_joint_id VARCHAR(255);

ALTER TABLE defect_record DROP CONSTRAINT IF EXISTS fk_defect_record_weld_joint;
ALTER TABLE defect_record ADD CONSTRAINT fk_defect_record_weld_joint
    FOREIGN KEY (weld_joint_id)
    REFERENCES weld_joint(weld_joint_id)
    ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_defect_record_weld_joint_id ON defect_record(weld_joint_id);

-- 3. 数据回填：迁移前一张底片最多一个焊口编号(task_file.weld_id)，
--    为每个已有 weld_id 的底片生成对应的 weld_joint 记录，
--    并把该底片下所有缺陷记录的 weld_joint_id 指向这条记录
INSERT INTO weld_joint (weld_joint_id, task_file_id, weld_no, sort_order, created_at, updated_at)
SELECT gen_random_uuid()::text, tf.task_file_id, tf.weld_id, 0, NOW(), NOW()
FROM task_file tf
WHERE tf.weld_id IS NOT NULL AND tf.weld_id <> ''
  AND NOT EXISTS (SELECT 1 FROM weld_joint wj WHERE wj.task_file_id = tf.task_file_id);

UPDATE defect_record dr
SET weld_joint_id = wj.weld_joint_id
FROM weld_joint wj
WHERE wj.task_file_id = dr.task_file_id
  AND dr.weld_joint_id IS NULL;

-- 注：task_file.weld_id 列保留但业务代码不再读写，待迁移稳定后再单独清理
