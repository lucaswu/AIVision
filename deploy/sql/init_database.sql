-- AI Vision Detection System Database Initialization
-- PostgreSQL compatible
-- 完整的数据库初始化脚本，包含所有表结构和索引

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
    minio_file_path VARCHAR(500), -- 实际MinIO路径，从file表获取
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    vision_result TEXT, -- Vision AI 检测结果 JSON
    llm_result TEXT, -- LLM 分析结果 JSON
    report_path VARCHAR(500), -- 生成的报告在MinIO中的路径
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
    AND tablename IN ('project', 'directory', 'file', 'task', 'task_file')
ORDER BY tablename, attname; 