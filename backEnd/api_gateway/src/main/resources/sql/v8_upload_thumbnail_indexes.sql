-- v8: 上传幂等查询与缩略图任务轮询的支撑索引
-- 背景：上传幂等校验 findByProjectIdAndDirectoryIdAndUploadSessionIdAndUploadKey
--       与缩略图调度 drainQueue 的轮询查询此前无索引，在 file 表增大后退化为全表扫描，
--       是大目录上传越传越慢的诱因之一。ddl-auto=update 会自动创建实体上声明的索引，
--       本脚本用于手动/存量库补建（幂等，可重复执行）。

-- 上传幂等覆盖索引
CREATE INDEX IF NOT EXISTS idx_file_upload_idem
    ON file (project_id, directory_id, upload_session_id, upload_key);

-- 缩略图任务轮询索引
CREATE INDEX IF NOT EXISTS idx_thumbnail_task_poll
    ON thumbnail_task (status, next_run_at);
