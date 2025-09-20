# SQL Scripts Directory

这个目录包含了AI Vision Detection System的数据库初始化和管理脚本。

## 文件说明

### `init_database.sql`
- **用途**: 完整的数据库初始化脚本
- **内容**: 包含所有表结构、索引、外键约束、触发器等
- **使用场景**: 新环境部署时的数据库初始化

#### 包含的表结构:
1. **project** - 项目管理表
2. **directory** - 目录管理表  
3. **file** - 文件管理表
4. **task** - 任务管理表
5. **task_file** - 任务文件关联表

#### 特性:
- 完整的外键约束
- 优化的索引设计
- 自动更新时间戳触发器
- 数据完整性检查约束

### `task_tables.sql` (已废弃)
- **状态**: 已合并到 `init_database.sql`
- **说明**: 这个文件的内容已经包含在完整初始化脚本中，可以删除

## 使用方法

### 1. 新环境初始化
```bash
# 连接到PostgreSQL数据库
psql -h localhost -U postgres -d ai_vision

# 执行初始化脚本
\i src/main/resources/sql/init_database.sql
```

### 2. Docker环境初始化
```bash
# 在docker-compose.yml中挂载SQL脚本
volumes:
  - ./src/main/resources/sql/init_database.sql:/docker-entrypoint-initdb.d/init_database.sql
```

## 数据库设计要点

### 1. 层级结构
- Project → Directory → File
- Project → Task → TaskFile

### 2. 权限控制
- 所有表都包含 `user_id` 字段用于权限控制
- 外键约束确保数据一致性

### 3. 性能优化
- 关键字段建立索引
- 复合索引优化查询性能
- 分区表设计（未来扩展）

### 4. 数据完整性
- CHECK约束限制状态值
- UNIQUE约束防止重复
- 级联删除维护数据一致性

## 维护说明

- 所有数据库结构变更都应该更新 `init_database.sql`
- 生产环境变更需要创建迁移脚本
- 定期备份数据库结构和数据

## 版本历史

- v1.0: 初始版本，包含基础表结构
- v1.1: 添加任务管理功能
- v1.2: 优化索引和约束（当前版本） 