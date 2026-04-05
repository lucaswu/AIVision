-- 为 file 表新增 thumbnail_path 列，记录 JPEG 预览图在存储中的路径
-- NULL = 尚未生成（非 BMP 文件或转换进行中）
-- 有值 = JPEG 已就绪，可通过 /api/v1/files/thumbnail 接口获取
ALTER TABLE file ADD COLUMN IF NOT EXISTS thumbnail_path VARCHAR(500);
