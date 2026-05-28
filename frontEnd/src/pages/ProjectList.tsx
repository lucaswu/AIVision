import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Typography,
  Modal,
  Form,
  Input,
  message,
  Breadcrumb,
  Alert,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ExclamationCircleOutlined,
  FileOutlined,
  CalendarOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import {
  Project,
} from "@/utils/data";
import { projectAPI } from "@/utils/api";
import { notifyProjectsUpdated } from "@/utils/projectEvents";

const { Title, Text } = Typography;
const { TextArea } = Input;

export default function ProjectList() {
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
  });
  const [searchText, setSearchText] = useState("");
  const [isEditModalVisible, setIsEditModalVisible] = useState(false);
  const [isDeleteModalVisible, setIsDeleteModalVisible] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deletingProject, setDeletingProject] = useState<Project | null>(null);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [form] = Form.useForm();
  const navigate = useNavigate();

  // 使用useRequest获取项目列表
  const {
    data: projectsResponse,
    loading,
    refresh,
  } = useRequest(() => projectAPI.getProjects(), {
    refreshDeps: [],
  });

  const projects = useMemo(() => {
    return (projectsResponse?.Data || []).sort((a, b) => {
      return (
        new Date(b.CreateTime).getTime() - new Date(a.CreateTime).getTime()
      );
    });
  }, [projectsResponse]);

  const filteredProjects = useMemo(() => {
    if (!searchText.trim()) return projects;
    const keyword = searchText.trim().toLowerCase();
    return projects.filter((p) => p.Name.toLowerCase().includes(keyword));
  }, [projects, searchText]);

  const total = filteredProjects.length;
  const handleCreateProject = () => {
    navigate("/projects/create");
  };

  const handleEditProject = (project: Project) => {
    setEditingProject(project);
    setIsEditModalVisible(true);
    form.setFieldsValue({
      ProjectName: project.Name,
      Description: project.Description,
    });
  };

  const handleDeleteProject = (project: Project) => {
    setDeletingProject(project);
    setDeleteConfirmName("");
    setIsDeleteModalVisible(true);
  };

  const handleEditOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingProject) {
        await projectAPI.updateProject(editingProject.Id, values);
        message.success("项目更新成功！");
        setIsEditModalVisible(false);
      form.resetFields();
      setEditingProject(null);
      refresh();
      notifyProjectsUpdated();
      }
    } catch (error) {
      console.log("验证失败:", error);
    }
  };

  const handleDeleteOk = async () => {
    if (deletingProject && deleteConfirmName === deletingProject.Name) {
      try {
        await projectAPI.deleteProject(deletingProject.Id);
        message.success("项目删除成功！");
        setIsDeleteModalVisible(false);
        setDeletingProject(null);
        setDeleteConfirmName("");
        refresh();
        notifyProjectsUpdated();
      } catch (error) {
        // API工具已经处理了错误消息
      }
    } else {
      message.error("输入的项目名称不匹配，请重新输入");
    }
  };

  const handleViewProject = (project: Project) => {
    navigate(`/projects/${project.Id}/files`);
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
      title: "项目名称",
      dataIndex: "Name",
      key: "Name",
      render: (text: string, record: Project) => (
        <Button
          type="link"
          style={{ padding: 0, height: "auto", fontWeight: 500, whiteSpace: "normal", textAlign: "left", lineHeight: "1.5" }}
          onClick={() => handleViewProject(record)}
        >
          {text}
        </Button>
      ),
    },
    {
      title: "创建日期",
      dataIndex: "CreateTime",
      key: "CreateTime",
      width: 180,
      render: (date: string) => date?.split(" ")[0] || "-",
    },
    {
      title: "文件数",
      dataIndex: "FileCount",
      key: "FileCount",
      width: 150,
      render: (count: number) => `${count || 0}个文件`,
    },
    {
      title: "备注",
      dataIndex: "Description",
      key: "Description",
      ellipsis: true,
      render: (text: string) => text || "-",
    },
    {
      title: "操作",
      key: "action",
      width: 120,
      align: "center" as const,
      render: (_: unknown, record: Project) => {
        const canEdit = record.Permission === "OWNER" || record.Permission === "READ_WRITE";
        
        return (
        <Space size="middle">
          <Button
              type="text"
              icon={<EditOutlined style={{ color: canEdit ? "#1890ff" : "#bfbfbf" }} />}
            onClick={() => handleEditProject(record)}
              disabled={!canEdit}
            />
          <Button
              type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteProject(record)}
              disabled={record.Permission !== "OWNER"}
            />
        </Space>
        );
      },
    },
  ];

  // 分页后的数据
  const paginatedData = filteredProjects.slice(
    (pagination.current - 1) * pagination.pageSize,
    pagination.current * pagination.pageSize
  );

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
            项目管理
          </Title>
          <Text type="secondary">管理您的检测项目和文件</Text>
        </div>
        <Space size={12}>
          <Input
            placeholder="搜索项目名称"
            prefix={<SearchOutlined style={{ color: "#bfbfbf" }} />}
            allowClear
            value={searchText}
            onChange={(e) => {
              setSearchText(e.target.value);
              setPagination((p) => ({ ...p, current: 1 }));
            }}
            style={{ width: 260, height: 48, borderRadius: 8 }}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            size="large"
            onClick={handleCreateProject}
            style={{ height: 48, borderRadius: 8, padding: "0 24px" }}
          >
            新增项目
          </Button>
        </Space>
        </div>

      <Card
            variant="borderless"
        style={{ borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.05)" }}
        styles={{ body: { padding: 0 } }}
      >
        <Table
          columns={columns}
          dataSource={paginatedData}
          rowKey="Id"
          loading={loading}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) =>
              `第 ${range[0]}-${range[1]} 项，共 ${total} 项`,
            onChange: handleTableChange,
            onShowSizeChange: handleTableChange,
            style: { padding: "16px 24px" },
          }}
        />
      </Card>

      {/* 编辑项目对话框 */}
      <Modal
        title={
          <div>
            <div style={{ fontSize: 20, fontWeight: 600 }}>编辑项目</div>
            <div style={{ fontSize: 14, fontWeight: 400, color: "#8c8c8c" }}>
              修改项目的基本信息
            </div>
          </div>
        }
        open={isEditModalVisible}
        onOk={handleEditOk}
        onCancel={() => setIsEditModalVisible(false)}
        width={560}
        okText="保存修改"
        cancelText="取消"
        centered
      >
        <div style={{ paddingTop: 16 }}>
          <Form form={form} layout="vertical">
          <Form.Item
            label="项目名称"
            name="ProjectName"
              rules={[{ required: true, message: "请输入项目名称" }]}
          >
              <Input
                placeholder="请输入项目名称"
                style={{ height: 44, borderRadius: 6 }}
              />
          </Form.Item>

            <Form.Item label="项目备注" name="Description">
              <TextArea
                rows={4}
                placeholder="可选填，用于记录项目的详细说明和注意事项"
                style={{ borderRadius: 6 }}
              />
          </Form.Item>
        </Form>

          {editingProject && (
            <div
              style={{
                background: "#f9fafb",
                padding: "16px 20px",
                borderRadius: 8,
                marginTop: 24,
              }}
            >
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <div style={{ color: "#595959" }}>
                  <CalendarOutlined style={{ marginRight: 8 }} />
                  创建日期：{editingProject.CreateTime?.split(" ")[0]}
                </div>
                <div style={{ color: "#595959" }}>
                  <FileOutlined style={{ marginRight: 8 }} />
                  文件数量：{editingProject.FileCount || 0}个文件
                </div>
              </Space>
            </div>
          )}
        </div>
      </Modal>

      {/* 删除确认对话框 */}
      <Modal
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <ExclamationCircleOutlined style={{ color: "#ff4d4f", fontSize: 22 }} />
            <span style={{ fontSize: 18, fontWeight: 600 }}>确认删除项目</span>
          </div>
        }
        open={isDeleteModalVisible}
        onOk={handleDeleteOk}
        onCancel={() => setIsDeleteModalVisible(false)}
        width={480}
        okText="确认删除"
        cancelText="取消"
        okButtonProps={{ danger: true, size: "large", style: { borderRadius: 6 } }}
        cancelButtonProps={{ size: "large", style: { borderRadius: 6 } }}
        centered
      >
        <div style={{ paddingTop: 8 }}>
          <div style={{ marginBottom: 16, fontSize: 16, fontWeight: 500 }}>
            {deletingProject?.Name}
          </div>

          <Alert
            message={
              <div style={{ color: "#cf1322" }}>
                <div style={{ marginBottom: 4 }}>
                  • 将删除项目中的所有文件 ({deletingProject?.FileCount || 0}个文件)
                </div>
                <div style={{ marginBottom: 4 }}>• 将删除所有相关的检测报告</div>
                <div style={{ fontWeight: 600 }}>• 此操作不可恢复，请谨慎操作</div>
              </div>
            }
            type="error"
            style={{
              backgroundColor: "#fff1f0",
              border: "1px solid #ffa39e",
              borderRadius: 8,
              marginBottom: 24,
            }}
          />

          <div style={{ marginBottom: 8, color: "#595959" }}>
            请输入项目名称以确认删除：
          </div>
          <Input
            placeholder={deletingProject?.Name}
            value={deleteConfirmName}
            onChange={(e) => setDeleteConfirmName(e.target.value)}
            style={{ height: 44, borderRadius: 6 }}
          />
        </div>
      </Modal>
    </div>
  );
}
