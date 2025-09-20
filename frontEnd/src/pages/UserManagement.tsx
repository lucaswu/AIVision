import React, { useState } from "react";
import {
  Table,
  Button,
  Card,
  Space,
  Tag,
  Typography,
  Modal,
  Form,
  Input,
  Select,
  message,
  Avatar,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import { User } from "@/utils/data";
import { userAPI } from "@/utils/api";

const { Title } = Typography;

export default function UserManagement() {
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
  });
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [form] = Form.useForm();

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

  const users = usersResponse?.Data || [];
  const total = usersResponse?.Total || users.length;

  const handleAddUser = () => {
    setEditingUser(null);
    setIsModalVisible(true);
    form.resetFields();
  };

  const handleEditUser = (user: User) => {
    setEditingUser(user);
    setIsModalVisible(true);
    form.setFieldsValue({
      username: user.Username,
      email: user.Email,
      role: user.Role,
      status: user.Status,
    });
  };

  const handleDeleteUser = async (user: User) => {
    Modal.confirm({
      title: "确认删除",
      content: `确定要删除用户 ${user.Username} 吗？`,
      async onOk() {
        try {
          await userAPI.deleteUser(user.Id.toString());
          message.success("用户删除成功！");
          refresh();
        } catch (error) {
          // API工具已经处理了错误消息
        }
      },
    });
  };

  const handleModalOk = async () => {
    try {
      const values = await form.validateFields();

      if (editingUser) {
        // 编辑用户
        await userAPI.updateUser(editingUser.Id.toString(), values);
        message.success("用户更新成功！");
      } else {
        // 添加用户
        await userAPI.createUser(values);
        message.success("用户创建成功！");
      }

      setIsModalVisible(false);
      form.resetFields();
      setEditingUser(null);
      refresh();
    } catch (error) {
      console.log("验证失败:", error);
    }
  };

  const handleModalCancel = () => {
    setIsModalVisible(false);
    form.resetFields();
    setEditingUser(null);
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
      title: "头像",
      dataIndex: "avatar",
      key: "avatar",
      render: (_text: string, record: User) => (
        <Avatar icon={<UserOutlined />} />
      ),
    },
    {
      title: "用户名",
      dataIndex: "Username",
      key: "Username",
    },
    {
      title: "邮箱",
      dataIndex: "Email",
      key: "Email",
    },
    {
      title: "角色",
      dataIndex: "Role",
      key: "Role",
      render: (role: string) => {
        const roleConfig = {
          admin: { color: "red", text: "管理员" },
          quality_inspector: { color: "blue", text: "质检员" },
          user: { color: "green", text: "普通用户" },
          viewer: { color: "green", text: "只读用户" },
        };
        const config = roleConfig[role as keyof typeof roleConfig] || {
          color: "default",
          text: role,
        };
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: "状态",
      dataIndex: "Status",
      key: "Status",
      render: (status: string) => {
        const statusConfig = {
          active: { color: "success", text: "活跃" },
          inactive: { color: "default", text: "非活跃" },
          disabled: { color: "error", text: "禁用" },
        };
        const config = statusConfig[status as keyof typeof statusConfig] || {
          color: "default",
          text: status,
        };
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: "注册时间",
      dataIndex: "CreateTime",
      key: "CreateTime",
      render: (time: string) => {
        return time ? new Date(time).toLocaleDateString("zh-CN") : "-";
      },
    },
    {
      title: "最后登录",
      dataIndex: "LastLoginTime",
      key: "LastLoginTime",
      render: (time: string) => {
        return time ? new Date(time).toLocaleDateString("zh-CN") : "-";
      },
    },
    {
      title: "操作",
      key: "action",
      render: (_: any, record: User) => (
        <Space size="middle">
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEditUser(record)}
          />
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteUser(record)}
          />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <div>
          <Title level={3} style={{ margin: 0 }}>
            用户管理
          </Title>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddUser}>
          添加用户
        </Button>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={users}
          loading={loading}
          rowKey="Id"
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
          }}
        />
      </Card>

      <Modal
        title={editingUser ? "编辑用户" : "添加用户"}
        open={isModalVisible}
        onOk={handleModalOk}
        onCancel={handleModalCancel}
        width={600}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 24 }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input placeholder="请输入用户名" />
          </Form.Item>

          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: "请输入邮箱" },
              { type: "email", message: "请输入正确的邮箱格式" },
            ]}
          >
            <Input placeholder="请输入邮箱" />
          </Form.Item>

          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: "请选择用户角色" }]}
          >
            <Select placeholder="请选择用户角色">
              <Select.Option value="admin">管理员</Select.Option>
              <Select.Option value="user">普通用户</Select.Option>
              <Select.Option value="viewer">只读用户</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="status"
            label="状态"
            rules={[{ required: true, message: "请选择用户状态" }]}
          >
            <Select placeholder="请选择用户状态">
              <Select.Option value="active">活跃</Select.Option>
              <Select.Option value="inactive">非活跃</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
