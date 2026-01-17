-- v4_film_defect_info.sql
-- 为 task_file 表添加底片信息字段，并创建缺陷记录表（包含 geometry 字段）

-- 1. 为 task_file 表添加底片信息字段
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS weld_id VARCHAR(100);
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS film_number VARCHAR(100);
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS film_density VARCHAR(50);
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS sensitivity VARCHAR(50);

-- 2. 创建缺陷记录表（包含 geometry 字段）
CREATE TABLE IF NOT EXISTS defect_record (
    defect_record_id VARCHAR(255) PRIMARY KEY,
    task_file_id VARCHAR(255) NOT NULL,
    defect_name VARCHAR(100),
    position VARCHAR(100),          -- 算法计算的位置描述
    size VARCHAR(100),
    grade VARCHAR(20),
    remark TEXT,
    geometry TEXT,                  -- 标注区域的几何坐标 JSON
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    CONSTRAINT fk_defect_record_task_file 
        FOREIGN KEY (task_file_id) 
        REFERENCES task_file(task_file_id) 
        ON DELETE CASCADE
);

-- 3. 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_defect_record_task_file_id ON defect_record(task_file_id);
