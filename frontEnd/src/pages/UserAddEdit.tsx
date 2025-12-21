import React, { useState, useEffect, useMemo } from "react";
import {
  Card,
  Form,
  Input,
  Button,
  Typography,
  Space,
  Breadcrumb,
  message,
  Radio,
  Divider,
  Switch,
  Table,
  Select,
  Modal,
} from "antd";
import {
  DeleteOutlined,
  PlusOutlined,
  ArrowLeftOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useNavigate, useParams } from "react-router-dom";
import { userAPI, projectAPI } from "@/utils/api";
import { Project } from "@/utils/data";

const { Title, Text } = Typography;

const UserAddEdit: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<any[]>([]);
  const [isProjectModalVisible, setIsProjectModalVisible] = useState(false);
  const [projectToSelect, setProjectToSelect] = useState<string | null>(null);

  const sortedProjects = useMemo(() => {
    return [...projects].sort((a, b) => {
      return (
        new Date(b.CreateTime).getTime() - new Date(a.CreateTime).getTime()
      );
    });
  }, [projects]);

  useEffect(() => {
    fetchProjects();
    if (isEdit) {
      fetchUserDetail();
    }
  }, [id]);

  const fetchProjects = async () => {
    try {
      const res = await projectAPI.getProjects();
      if (res.Code === 200) {
        setProjects(res.Data);
      }
    } catch (error) {
      console.error("Fetch projects error:", error);
    }
  };

  const fetchUserDetail = async () => {
    setLoading(true);
    try {
      const res = await userAPI.getUser(id!);
      if (res.Code === 200) {
        const userData = res.Data;
        form.setFieldsValue({
          username: userData.username,
          email: userData.email,
          role: userData.role === "ADMIN" ? "admin" : "inspector",
          status: userData.status === "ACTIVE",
        });
        
        // 处理权限转换
        const perms = (userData.permissions || []).map((p: any) => ({
          projectId: p.projectId,
          projectName: p.projectName,
          permission: p.permission === "READ_ONLY" ? "read" : "edit",
        }));
        setSelectedProjects(perms);
      }
    } catch (error) {
      console.error("Fetch user detail error:", error);
    } finally {
      setLoading(true); // 这里应该是 false，但在 API 完成前先保持 loading 以防止表单闪烁
      setLoading(false);
    }
  };

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      // 组装权限数据
      const projectPermissions = selectedProjects.map((p) => ({
        projectId: p.projectId,
        permission: p.permission === "read" ? "READ_ONLY" : "READ_WRITE",
      }));

      const payload = {
        username: values.username,
        password: values.password,
        email: values.email,
        role: values.role === "admin" ? "ADMIN" : "INSPECTOR",
        status: values.status === false ? "DISABLED" : "ACTIVE",
        projectPermissions,
      };

      let res;
      if (isEdit) {
        res = await userAPI.updateUser(id!, payload);
      } else {
        res = await userAPI.createUser(payload);
      }

      if (res.Code === 200) {
        message.success(isEdit ? "用户更新成功" : "用户创建成功");
        navigate("/users");
      }
    } catch (error) {
      console.error("Save user error:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddProject = () => {
    setIsProjectModalVisible(true);
  };

  const confirmAddProject = () => {
    if (!projectToSelect) {
      message.warning("请选择一个项目");
      return;
    }

    const project = projects.find((p) => p.Id === projectToSelect);
    if (project) {
      // 检查是否已经存在
      if (selectedProjects.some((p) => p.projectId === project.Id)) {
        message.warning("该项目已在列表中");
        return;
      }

      setSelectedProjects([
        ...selectedProjects,
        {
          projectId: project.Id,
          projectName: project.Name,
          permission: "read",
        },
      ]);
    }
    setIsProjectModalVisible(false);
    setProjectToSelect(null);
  };

  const removeProject = (projectId: string) => {
    setSelectedProjects(selectedProjects.filter((p) => p.projectId !== projectId));
  };

  const updatePermission = (projectId: string, permission: string) => {
    setSelectedProjects(
      selectedProjects.map((p) =>
        p.projectId === projectId ? { ...p, permission } : p
      )
    );
  };

  const columns = [
    {
      title: "项目名称",
      dataIndex: "projectName",
      key: "projectName",
    },
    {
      title: "权限",
      key: "permission",
      width: 250,
      render: (_: any, record: any) => (
        <Radio.Group
          value={record.permission}
          onChange={(e) => updatePermission(record.projectId, e.target.value)}
        >
          <Radio value="read">只读</Radio>
          <Radio value="edit">可编辑</Radio>
        </Radio.Group>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 80,
      render: (_: any, record: any) => (
        <Button
          type="text"
          danger
          icon={<DeleteOutlined />}
          onClick={() => removeProject(record.projectId)}
        />
      ),
    },
  ];

  return (
    <div style={{ padding: "24px", maxWidth: "1200px", margin: "0 auto" }}>
      <Breadcrumb
        items={[
          { title: "系统管理" },
          { title: "用户管理", href: "/users" },
          { title: isEdit ? "编辑用户" : "添加用户" },
        ]}
        style={{ marginBottom: "16px" }}
      />

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "24px",
        }}
      >
        <div>
          <Title level={2} style={{ margin: "0 0 4px 0" }}>
            {isEdit ? "编辑用户" : "添加用户"}
          </Title>
          <Text type="secondary">
            {isEdit ? "修改用户信息和权限设置" : "创建新用户账号并设置权限"}
          </Text>
        </div>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/users")}>
          返回列表
        </Button>
      </div>

      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        initialValues={{ role: "inspector", status: true }}
        size="large"
      >
        <Space direction="vertical" size={24} style={{ width: "100%" }}>
          <Card title="基本信息" variant="none" style={{ borderRadius: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}>
            {isEdit && (
              <Form.Item label="用户ID">
                <Input value={id} disabled style={{ borderRadius: 8 }} />
              </Form.Item>
            )}
            
            <Form.Item
              label="姓名"
              name="username"
              rules={[{ required: true, message: "请输入用户姓名" }]}
            >
              <Input placeholder="请输入用户姓名" style={{ borderRadius: 8 }} />
            </Form.Item>

            <Form.Item
              label="邮箱"
              name="email"
              rules={[{ type: "email", message: "请输入正确的邮箱格式" }]}
            >
              <Input placeholder="请输入邮箱地址" style={{ borderRadius: 8 }} />
            </Form.Item>

            {!isEdit ? (
              <>
                <Form.Item
                  label="密码"
                  name="password"
                  rules={[{ required: true, message: "请输入初始密码" }]}
                >
                  <Input.Password placeholder="请输入初始密码" style={{ borderRadius: 8 }} />
                </Form.Item>
                <Form.Item
                  label="确认密码"
                  name="confirmPassword"
                  dependencies={["password"]}
                  rules={[
                    { required: true, message: "请确认密码" },
                    ({ getFieldValue }) => ({
                      validator(_, value) {
                        if (!value || getFieldValue("password") === value) {
                          return Promise.resolve();
                        }
                        return Promise.reject(new Error("两次输入的密码不一致"));
                      },
                    }),
                  ]}
                >
                  <Input.Password placeholder="请再次输入密码" style={{ borderRadius: 8 }} />
                </Form.Item>
              </>
            ) : (
              <Form.Item label="密码">
                <Button icon={<ReloadOutlined />}>重置密码</Button>
              </Form.Item>
            )}
          </Card>

          <Card title="角色与权限" variant="none" style={{ borderRadius: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}>
            <Form.Item
              label="用户角色"
              name="role"
              rules={[{ required: true, message: "请选择用户角色" }]}
            >
              <Radio.Group>
                <Radio value="admin">管理员</Radio>
                <Radio value="inspector">质检员</Radio>
              </Radio.Group>
            </Form.Item>

            {isEdit && (
              <Form.Item label="账号状态" name="status" valuePropName="checked">
                <Space>
                  <Switch />
                  <Text>{form.getFieldValue("status") ? "活跃" : "禁用"}</Text>
                </Space>
              </Form.Item>
            )}

            <Divider />

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 16,
              }}
            >
              <Title level={5} style={{ margin: 0 }}>
                项目权限
              </Title>
              <Button icon={<PlusOutlined />} onClick={handleAddProject}>
                添加项目
              </Button>
            </div>

            <Table
              dataSource={selectedProjects}
              columns={columns}
              rowKey="projectId"
              pagination={false}
              locale={{ emptyText: "暂无分配的项目权限" }}
            />
          </Card>

          <div style={{ textAlign: "right", marginTop: 12 }}>
            <Space size={16}>
              <Button onClick={() => navigate("/users")} style={{ borderRadius: 8, minWidth: 100 }}>
                取消
              </Button>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                style={{ borderRadius: 8, minWidth: 100 }}
              >
                保存
              </Button>
            </Space>
          </div>
        </Space>
      </Form>

      <Modal
        title="添加项目"
        open={isProjectModalVisible}
        onOk={confirmAddProject}
        onCancel={() => setIsProjectModalVisible(false)}
        okText="确认"
        cancelText="取消"
      >
        <div style={{ padding: "16px 0" }}>
          <Text strong>选择项目 *</Text>
          <Select
            placeholder="选择一个项目"
            style={{ width: "100%", marginTop: 8 }}
            onChange={(value) => setProjectToSelect(value)}
            value={projectToSelect}
          >
            {sortedProjects.map((p) => (
              <Select.Option key={p.Id} value={p.Id}>
                {p.Name}
              </Select.Option>
            ))}
          </Select>
        </div>
      </Modal>
    </div>
  );
};

export default UserAddEdit;

