import { useState, useEffect } from "react";
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
  Select,
  message,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import {
  Project,
  CreateProjectRequest,
  projectTypeOptions,
} from "@/utils/data";
import { projectAPI } from "@/utils/api";

const { Title } = Typography;
const { TextArea } = Input;

export default function ProjectList() {
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
  });
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
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

  const projects = projectsResponse?.Data || [];
  const total = projects.length;

  const handleCreateProject = () => {
    setEditingProject(null);
    setIsModalVisible(true);
    form.resetFields();
  };

  const handleEditProject = (project: Project) => {
    setEditingProject(project);
    setIsModalVisible(true);
    form.setFieldsValue({
      ProjectName: project.Name,
      Description: project.Description,
    });
  };

  const handleDeleteProject = async (project: Project) => {
    Modal.confirm({
      title: "确认删除",
      content: `确定要删除项目 ${project.Name} 吗？`,
      async onOk() {
        try {
          await projectAPI.deleteProject(project.Id);
          message.success("项目删除成功！");
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

      if (editingProject) {
        // 编辑项目
        await projectAPI.updateProject(editingProject.Id, values);
        message.success("项目更新成功！");
      } else {
        // 创建项目
        await projectAPI.createProject(values as CreateProjectRequest);
        message.success("项目创建成功！");
      }

      setIsModalVisible(false);
      form.resetFields();
      setEditingProject(null);
      refresh();
    } catch (error) {
      console.log("验证失败:", error);
    }
  };

  const handleModalCancel = () => {
    setIsModalVisible(false);
    form.resetFields();
    setEditingProject(null);
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

  // 格式化显示日期
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("zh-CN");
  };

  // 格式化文件数量显示
  const formatFileCount = (count?: number) => {
    return count ? `${count}个` : "0个";
  };

  // 格式化存储大小显示
  const formatStorageSize = (size?: string) => {
    return size || "0 MB";
  };

  const columns = [
    {
      title: "项目名称",
      dataIndex: "Name",
      key: "Name",
      render: (text: string, record: Project) => (
        <Button
          type="link"
          style={{ padding: 0, height: "auto" }}
          onClick={() => handleViewProject(record)}
        >
          {text}
        </Button>
      ),
    },
    {
      title: "项目描述",
      dataIndex: "Description",
      key: "Description",
      ellipsis: true,
      render: (text: string) => text || "-",
    },
    {
      title: "创建时间",
      dataIndex: "CreateTime",
      key: "CreateTime",
      width: 250,
    },
    {
      title: "文件数",
      dataIndex: "FileCount",
      key: "FileCount",
      render: (count: number) => formatFileCount(count),
    },
    {
      title: "任务数",
      dataIndex: "TaskCount",
      key: "TaskCount",
      render: (count: number) => formatFileCount(count),
    },
    {
      title: "操作",
      key: "action",
      render: (_: unknown, record: Project) => (
        <Space size="middle">
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEditProject(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteProject(record)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  // 分页后的数据
  const paginatedData = projects.slice(
    (pagination.current - 1) * pagination.pageSize,
    pagination.current * pagination.pageSize
  );

  return (
    <div style={{ padding: 24 }}>
      <Card>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <Title level={3} style={{ margin: 0 }}>
            项目管理
          </Title>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleCreateProject}
          >
            新建项目
          </Button>
        </div>

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
          }}
        />
      </Card>

      {/* 创建/编辑项目对话框 */}
      <Modal
        title={editingProject ? "编辑项目" : "新建项目"}
        open={isModalVisible}
        onOk={handleModalOk}
        onCancel={handleModalCancel}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            ProjectName: "",
            Description: "",
          }}
        >
          <Form.Item
            label="项目名称"
            name="ProjectName"
            rules={[
              { required: true, message: "请输入项目名称" },
              { max: 100, message: "项目名称不能超过100个字符" },
            ]}
          >
            <Input placeholder="请输入项目名称" />
          </Form.Item>

          <Form.Item
            label="项目描述"
            name="Description"
            rules={[{ max: 500, message: "项目描述不能超过500个字符" }]}
          >
            <TextArea rows={4} placeholder="请输入项目描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
