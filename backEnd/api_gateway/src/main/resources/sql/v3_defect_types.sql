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
