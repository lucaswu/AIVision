# SQL Scripts Directory

这个目录包含了AI Vision Detection System的数据库初始化和管理脚本。

## 重要说明

**`init_database.sql` 已移动！**

为了保持单一事实来源 (Single Source of Truth)，数据库初始化脚本现在统一维护在部署目录中：

👉 `AIVision/deploy/sql/init_database.sql`

请在开发和部署时参考该文件。

## 历史文件说明

### `init_database.sql` (已移除)
- **状态**: 已移动到 `deploy/sql/` 目录
- **说明**: 此目录不再保留数据库脚本副本，以避免版本不一致。

## 使用方法

### Docker环境初始化
Docker Compose 配置已指向 `deploy/sql/init_database.sql`，无需额外操作。
