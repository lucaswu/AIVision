import React, { useState } from "react";
import {
  Table,
  Button,
  Card,
  Space,
  Tag,
  Typography,
  Modal,
  message,
  Avatar,
  Breadcrumb,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import { useNavigate } from "react-router-dom";
import { User } from "@/utils/data";
import { userAPI } from "@/utils/api";

const { Title, Text } = Typography;

export default function UserManagement() {
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
  });
  const navigate = useNavigate();

  // 使用useRequest获取用户列表，依赖分页参数
  const {
    data: usersResponse,
    loading,
    refresh,
  } = useRequest(
    () =>
      userAPI.getUsers({
        page: pagination.current,
        pageSize: pagination.pageSize,
      }),
    {
      refreshDeps: [pagination.current, pagination.pageSize],
    }
  );

  const users = usersResponse?.Data?.content || [];
  const total = usersResponse?.Data?.totalElements || users.length;

  const handleAddUser = () => {
    navigate("/users/add");
  };

  const handleEditUser = (user: User) => {
    navigate(`/users/edit/${user.userId}`);
  };

  const handleDeleteUser = async (user: User) => {
    const username = user.username;
    if (username === "Admin") {
      message.error("系统管理员账号不允许删除");
      return;
    }
    Modal.confirm({
      title: "确认删除",
      content: `确定要删除用户 ${user.username} 吗？`,
      okText: "确认删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      async onOk() {
        try {
          await userAPI.deleteUser(user.userId.toString());
          message.success("用户删除成功！");
          refresh();
        } catch (error) {
          // API工具已经处理了错误消息
        }
      },
    });
  };

  // 处理分页变化
  const handleTableChange = (page: number, pageSize: number) => {
    setPagination({
      current: page,
      pageSize: pageSize,
    });
  };

  const columns = [
    {
      title: "ID",
      dataIndex: "userId",
      key: "userId",
      width: 100,
      render: (id: string) => id || "-",
    },
    {
      title: "姓名",
      dataIndex: "username",
      key: "username",
      render: (username: string) => (
        <Space>
          <Avatar 
            style={{ backgroundColor: "#1890ff", verticalAlign: "middle" }}
            size="small"
          >
            {(username || "?")[0].toUpperCase()}
          </Avatar>
          <Text strong>{username}</Text>
        </Space>
      ),
    },
    {
      title: "邮箱",
      dataIndex: "email",
      key: "email",
      render: (email: string) => email || "-",
    },
    {
      title: "角色",
      dataIndex: "role",
      key: "role",
      render: (role: string) => {
        const r = (role || "").toUpperCase();
        if (r === "ADMIN") {
          return (
            <Tag color="blue" style={{ borderRadius: "10px", padding: "0 12px" }}>
              管理员
            </Tag>
          );
        }
        return (
          <Tag color="green" style={{ borderRadius: "10px", padding: "0 12px" }}>
            质检员
          </Tag>
        );
      },
    },
    {
      title: "项目",
      dataIndex: "projectPermissions",
      key: "projectPermissions",
      render: (permissions: any[]) => {
        const perms = permissions || [];
        if (!perms || perms.length === 0) return <Text type="secondary">无项目</Text>;
        return (
          <Space size={[0, 4]} wrap>
            {perms.slice(0, 2).map((p: any) => (
              <Tag key={p.projectId} color="cyan" style={{ border: "none" }}>
                {p.projectName}
              </Tag>
            ))}
            {perms.length > 2 && <Text type="secondary">+{perms.length - 2}</Text>}
          </Space>
        );
      },
    },
    {
      title: "操作",
      key: "action",
      width: 120,
      align: "center" as const,
      render: (_: any, record: User) => (
        <Space size="middle">
          <Button
            type="text"
            icon={<EditOutlined style={{ color: "#1890ff" }} />}
            onClick={() => handleEditUser(record)}
          />
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteUser(record)}
            disabled={record.username === "Admin"}
          />
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: "24px", maxWidth: "1400px", margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 24,
        }}
      >
        <div>
          <Title level={2} style={{ margin: "0 0 4px 0" }}>
            用户管理
          </Title>
          <Text type="secondary">管理用户账号和权限</Text>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size="large"
          onClick={handleAddUser}
          style={{ height: 48, borderRadius: 8, padding: "0 24px" }}
        >
          添加用户
        </Button>
      </div>

      <Card
        variant="borderless"
        style={{ borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.05)" }}
        styles={{ body: { padding: 0 } }}
      >
        <Table
          columns={columns}
          dataSource={users}
          loading={loading}
          rowKey={(record: any) => record.userId || record.Id}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) =>
              `第 ${range[0]}-${range[1]} 条/共 ${total} 条`,
            pageSizeOptions: ["10", "20", "50", "100"],
            onChange: handleTableChange,
            onShowSizeChange: handleTableChange,
            style: { padding: "16px 24px" },
          }}
        />
      </Card>
    </div>
  );
}
