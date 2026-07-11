-- AI Vision Detection System Database Initialization
-- PostgreSQL compatible
-- 完整的数据库初始化脚本，包含所有表结构和索引

-- =====================================================
-- 0. 用户管理表
-- =====================================================

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(255) PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_username UNIQUE (username)
);

-- Create indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- Initial Admin User (Default password: password)
INSERT INTO users (user_id, username, password, role, status)
VALUES ('admin-001', 'Admin', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'ADMIN', 'ACTIVE')
ON CONFLICT (username) DO NOTHING;

-- =====================================================
-- 1. 项目管理表
-- =====================================================

-- Create project table
CREATE TABLE IF NOT EXISTS project (
    project_id VARCHAR(255) PRIMARY KEY,
    project_name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED', 'DELETED')),
    project_type VARCHAR(100),
    settings TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for project table
CREATE INDEX IF NOT EXISTS idx_project_name ON project(project_name);
CREATE INDEX IF NOT EXISTS idx_project_owner_id ON project(owner_id);
CREATE INDEX IF NOT EXISTS idx_project_status ON project(status);
CREATE INDEX IF NOT EXISTS idx_project_type ON project(project_type);
CREATE INDEX IF NOT EXISTS idx_project_created_at ON project(created_at);

-- Create user_project_permission table (Depends on users and project)
CREATE TABLE IF NOT EXISTS user_project_permission (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    project_id VARCHAR(255) NOT NULL,
    permission VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_project_permission UNIQUE (user_id, project_id),
    CONSTRAINT fk_permission_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_permission_project FOREIGN KEY (project_id) REFERENCES project(project_id) ON DELETE CASCADE
);

-- Create indexes for user_project_permission table
CREATE INDEX IF NOT EXISTS idx_permission_user_id ON user_project_permission(user_id);
CREATE INDEX IF NOT EXISTS idx_permission_project_id ON user_project_permission(project_id);

-- =====================================================
-- 2. 目录管理表
-- =====================================================

-- Create directory table
CREATE TABLE IF NOT EXISTS directory (
    dir_id VARCHAR(255) PRIMARY KEY,
    project_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    parent_id VARCHAR(255),
    dir_name VARCHAR(255) NOT NULL,
    dir_path TEXT NOT NULL,
    dir_level INTEGER NOT NULL DEFAULT 1 CHECK (dir_level <= 5),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DELETED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_directory_project FOREIGN KEY (project_id) REFERENCES project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_directory_parent FOREIGN KEY (parent_id) REFERENCES directory(dir_id) ON DELETE CASCADE,
    
    -- Unique constraint for directory name within same parent
    CONSTRAINT unique_dir_name_per_parent UNIQUE (project_id, parent_id, dir_name, user_id)
);

-- Create indexes for directory table
CREATE INDEX IF NOT EXISTS idx_directory_project ON directory(project_id);
CREATE INDEX IF NOT EXISTS idx_directory_user ON directory(user_id);
CREATE INDEX IF NOT EXISTS idx_directory_project_user ON directory(project_id, user_id);
CREATE INDEX IF NOT EXISTS idx_directory_parent ON directory(parent_id);
CREATE INDEX IF NOT EXISTS idx_directory_level ON directory(dir_level);
CREATE INDEX IF NOT EXISTS idx_directory_path ON directory(dir_path);
CREATE INDEX IF NOT EXISTS idx_directory_status ON directory(status);
CREATE INDEX IF NOT EXISTS idx_directory_created_at ON directory(created_at);

-- =====================================================
-- 3. 文件管理表
-- =====================================================

-- Create file table
CREATE TABLE IF NOT EXISTS file (
    file_id VARCHAR(255) PRIMARY KEY,
    project_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    directory_id VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100),
    file_extension VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_file_project FOREIGN KEY (project_id) REFERENCES project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_file_directory FOREIGN KEY (directory_id) REFERENCES directory(dir_id) ON DELETE CASCADE
);

-- Create indexes for file table
CREATE INDEX IF NOT EXISTS idx_file_project ON file(project_id);
CREATE INDEX IF NOT EXISTS idx_file_user ON file(user_id);
CREATE INDEX IF NOT EXISTS idx_file_directory ON file(directory_id);
CREATE INDEX IF NOT EXISTS idx_file_project_user ON file(project_id, user_id);
CREATE INDEX IF NOT EXISTS idx_file_extension ON file(file_extension);
CREATE INDEX IF NOT EXISTS idx_file_original_name ON file(original_name);
CREATE INDEX IF NOT EXISTS idx_file_created_at ON file(created_at);

-- =====================================================
-- 4. 任务管理表
-- =====================================================

-- Create task table
CREATE TABLE IF NOT EXISTS task (
    task_id VARCHAR(255) PRIMARY KEY,
    project_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    description TEXT,
    algorithm_type VARCHAR(50) NOT NULL DEFAULT 'object-detection',
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    total_files INTEGER NOT NULL DEFAULT 0,
    processed_files INTEGER NOT NULL DEFAULT 0,
    success_files INTEGER NOT NULL DEFAULT 0,
    failed_files INTEGER NOT NULL DEFAULT 0,
    progress INTEGER NOT NULL DEFAULT 0, -- (processed_files / total_files) * 100
    parallel_count INTEGER NOT NULL DEFAULT 10, -- 并行度配置
    error_message TEXT, -- 整体任务失败原因
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    task_report TEXT,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_task_project FOREIGN KEY (project_id) REFERENCES project(project_id) ON DELETE CASCADE
);

-- Create task_file table
CREATE TABLE IF NOT EXISTS task_file (
    task_file_id VARCHAR(255) PRIMARY KEY,
    task_id VARCHAR(255) NOT NULL,
    file_id VARCHAR(255) NOT NULL,
    logical_file_path VARCHAR(500) NOT NULL, -- 逻辑路径，如 /images/pcb-boards/001.jpg
    minio_file_path VARCHAR(500), -- 实际存储路径，从file表获取
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    vision_result TEXT, -- Vision AI 检测结果 JSON
    report_path VARCHAR(500), -- 生成的报告路径
    error_message TEXT, -- 单个文件失败原因
    processing_start_time TIMESTAMP,
    processing_end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_task_file_task FOREIGN KEY (task_id) REFERENCES task(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_task_file_file FOREIGN KEY (file_id) REFERENCES file(file_id) ON DELETE CASCADE
);

-- Create indexes for task table
CREATE INDEX IF NOT EXISTS idx_task_project_user ON task(project_id, user_id);
CREATE INDEX IF NOT EXISTS idx_task_status ON task(status);
CREATE INDEX IF NOT EXISTS idx_task_algorithm_type ON task(algorithm_type);
CREATE INDEX IF NOT EXISTS idx_task_created_at ON task(created_at);
CREATE INDEX IF NOT EXISTS idx_task_updated_at ON task(updated_at);

-- Create indexes for task_file table
CREATE INDEX IF NOT EXISTS idx_task_file_task_id ON task_file(task_id);
CREATE INDEX IF NOT EXISTS idx_task_file_file_id ON task_file(file_id);
CREATE INDEX IF NOT EXISTS idx_task_file_status ON task_file(status);
CREATE INDEX IF NOT EXISTS idx_task_file_logical_path ON task_file(logical_file_path);
CREATE INDEX IF NOT EXISTS idx_task_file_created_at ON task_file(created_at);
CREATE INDEX IF NOT EXISTS idx_task_file_processing_times ON task_file(processing_start_time, processing_end_time);

-- =====================================================
-- 4.1 报告管理表
-- =====================================================

-- Create report table
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_report_task FOREIGN KEY (task_id) REFERENCES task(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_report_project FOREIGN KEY (project_id) REFERENCES project(project_id) ON DELETE CASCADE
);

-- Add review fields to task_file
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS review_status VARCHAR(20) DEFAULT 'PENDING';
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS manual_result TEXT;
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS plate_quality VARCHAR(50);

-- Create index for report
CREATE INDEX IF NOT EXISTS idx_report_project_id ON report(project_id);
CREATE INDEX IF NOT EXISTS idx_report_task_id ON report(task_id);

-- =====================================================
-- 5. 触发器和函数
-- =====================================================

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers to automatically update updated_at
CREATE TRIGGER update_project_updated_at 
    BEFORE UPDATE ON project 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_directory_updated_at 
    BEFORE UPDATE ON directory 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_file_updated_at 
    BEFORE UPDATE ON file 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_task_updated_at 
    BEFORE UPDATE ON task 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_task_file_updated_at 
    BEFORE UPDATE ON task_file 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_report_updated_at 
    BEFORE UPDATE ON report 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 6. 初始化完成消息
-- =====================================================

-- Print initialization completion message
SELECT 'AI Vision Detection PostgreSQL Database Initialized Successfully!' as message;

-- 显示表统计信息
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats 
WHERE schemaname = 'public' 
    AND tablename IN ('users', 'user_project_permission', 'project', 'directory', 'file', 'task', 'task_file')
ORDER BY tablename, attname;

-- =====================================================
-- 7. 补充更新 (v3 & v4)
-- =====================================================

-- -----------------------------------------------------
-- v3_defect_types.sql
-- -----------------------------------------------------

-- 缺陷类型表
CREATE TABLE IF NOT EXISTS defect_type (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(20) NOT NULL,
    sort_order INT DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE
);

-- 插入8种标准焊缝缺陷类型
INSERT INTO defect_type (code, name, color, sort_order, enabled) VALUES
('crack', '裂纹(A)', '#ff4d4f', 1, TRUE),
('lack_fusion', '未熔合(B)', '#eb2f96', 2, TRUE),
('incomplete_penetration', '未焊透(C)', '#a0522d', 3, TRUE),
('linear_defect', '条形缺陷(D)', '#faad14', 4, TRUE),
('round_defect', '圆形缺陷(E)', '#722ed1', 5, TRUE),
('undercut', '咬边(F)', '#13c2c2', 6, TRUE),
('concave', '内凹(G)', '#1890ff', 7, TRUE),
('other', '其他(H)', '#52c41a', 8, TRUE)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    color = EXCLUDED.color,
    sort_order = EXCLUDED.sort_order;

-- -----------------------------------------------------
-- v4_film_defect_info.sql
-- -----------------------------------------------------

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

-- -----------------------------------------------------
-- v5_correction_info.sql
-- -----------------------------------------------------

-- 为 task_file 表添加焊缝底片方向矫正信息字段
-- correction_rotation: 前端需要应用的旋转角度 (0 / 90 / 180 / -90)
-- correction_flip: 前端是否需要水平翻转
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS correction_rotation INTEGER DEFAULT 0;
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS correction_flip BOOLEAN DEFAULT FALSE;

-- -----------------------------------------------------
-- v6_weld_location.sql
-- -----------------------------------------------------

-- 为 task_file 表添加焊缝位置检测结果字段
-- weld_location: JSON 数组，每条记录含 class/confidence/bbox/keypoints（12个关键点形成椭圆）
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS weld_location TEXT;

-- -----------------------------------------------------
-- v7_defect_position.sql
-- -----------------------------------------------------

-- 为 task_file 表添加缺陷位置检测2结果字段（D路径，location_1.pt）
-- defect_position: JSON 对象，仅存 positioning_type==0 (center_mark) 的原点坐标
-- 格式: {"origin_x": float, "origin_y": float, "positioning_type": 0}
ALTER TABLE task_file ADD COLUMN IF NOT EXISTS defect_position TEXT;

-- -----------------------------------------------------
-- v9_weld_joint.sql
-- -----------------------------------------------------

-- 支持一张底片(task_file)关联多个焊口编号：新增 weld_joint 表，
-- defect_record 增加 weld_joint_id 外键标识每条缺陷所属的焊口
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

ALTER TABLE defect_record ADD COLUMN IF NOT EXISTS weld_joint_id VARCHAR(255);

ALTER TABLE defect_record DROP CONSTRAINT IF EXISTS fk_defect_record_weld_joint;
ALTER TABLE defect_record ADD CONSTRAINT fk_defect_record_weld_joint
    FOREIGN KEY (weld_joint_id)
    REFERENCES weld_joint(weld_joint_id)
    ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_defect_record_weld_joint_id ON defect_record(weld_joint_id);

-- 数据回填：迁移前一张底片最多一个焊口编号(task_file.weld_id)，
-- 为每个已有 weld_id 的底片生成对应的 weld_joint 记录，
-- 并把该底片下所有缺陷记录的 weld_joint_id 指向这条记录
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
