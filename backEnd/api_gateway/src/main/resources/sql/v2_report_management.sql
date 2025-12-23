-- 创建报告表
CREATE TABLE IF NOT EXISTS report (
    report_id VARCHAR(255) PRIMARY KEY,
    task_id VARCHAR(255) NOT NULL UNIQUE,
    project_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    report_name VARCHAR(255) NOT NULL,
    total_files INTEGER DEFAULT 0,
    confirmed_files INTEGER DEFAULT 0,
    total_defects INTEGER DEFAULT 0,
    severe_defects INTEGER DEFAULT 0,
    normal_defects INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 为任务文件表增加审核相关字段
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS review_status VARCHAR(20) DEFAULT 'PENDING';
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS manual_result TEXT; -- 存储 JSONB 格式的字符串
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS plate_quality VARCHAR(50);

