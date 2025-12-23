import React, { useState, useEffect, useMemo } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  Select,
  Table,
  Space,
  Typography,
  Row,
  Col,
  Modal,
  Tree,
  Progress,
  Tag,
  message,
  Dropdown,
  Checkbox,
  Breadcrumb,
  Pagination,
  List,
  Empty,
  Tooltip,
} from "antd";
import {
  PlusOutlined,
  FileImageOutlined,
  FolderOutlined,
  DeleteOutlined,
  ReloadOutlined,
  FileTextOutlined,
  ProjectOutlined,
  ArrowLeftOutlined,
  UploadOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import type { TableColumnsType, TreeDataNode } from "antd";
import { useRequest } from "ahooks";
import { taskAPI, fileAPI, projectAPI } from "../../utils/api";
import { Task, TaskStatus, FileTreeNode, Project, TaskSubmitRequest } from "../../utils/data";

const { Title, Text, Paragraph } = Typography;

interface TasksPageProps {
  projectId: string;
  projectName?: string;
  permission?: string;
}

const TasksPage: React.FC<TasksPageProps> = ({
  projectId,
  projectName = "项目",
  permission = "READ_ONLY",
}) => {
  const isReadOnly = permission === "READ_ONLY";
  const [view, setView] = useState<"list" | "create">("list");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  
  // 弹窗状态
  const [showRestartModal, setShowRestartModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [actionTask, setActionTask] = useState<Task | null>(null);

  // 1. 获取任务列表
  const {
    data: tasksResponse,
    loading: tasksLoading,
    refresh: refreshTasks,
  } = useRequest(
    () => taskAPI.getTasks(projectId),
    {
      refreshDeps: [projectId],
      pollingInterval: 3000,
    }
  );

  const tasks = tasksResponse?.Data?.Tasks || [];
  const totalTasks = tasksResponse?.Data?.TotalCount || 0;

  // 2. 任务列表列定义
  const columns: TableColumnsType<Task> = [
    {
      title: "任务名称",
      dataIndex: "Name",
      key: "Name",
      width: 200,
      render: (text) => <Text strong>{text}</Text>,
    },
    {
      title: "文件数",
      dataIndex: "FileCount",
      key: "FileCount",
      width: 120,
      render: (count) => `${count}个文件`,
    },
    {
      title: "创建时间",
      dataIndex: "CreateTime",
      key: "CreateTime",
      width: 180,
    },
    {
      title: "结束时间",
      dataIndex: "EndTime",
      key: "EndTime",
      width: 180,
      render: (time) => time || "-",
    },
    {
      title: "状态",
      dataIndex: "Status",
      key: "Status",
      width: 120,
      render: (status) => {
        const config = {
          [TaskStatus.PENDING]: { color: "default", text: "等待中", icon: <SyncOutlined spin /> },
          [TaskStatus.PROCESSING]: { color: "processing", text: "进行中", icon: <SyncOutlined spin /> },
          [TaskStatus.COMPLETED]: { color: "success", text: "已完成", icon: <CheckCircleOutlined /> },
          [TaskStatus.FAILED]: { color: "error", text: "失败", icon: <CloseCircleOutlined /> },
        };
        const item = config[status] || { color: "default", text: status };
        return <Tag color={item.color} icon={item.icon}>{item.text}</Tag>;
      },
    },
    {
      title: "进度",
      dataIndex: "Progress",
      key: "Progress",
      width: 180,
      render: (progress, record) => (
        <div style={{ width: "100%" }}>
          <Progress
            percent={progress}
            size="small"
            status={record.Status === TaskStatus.FAILED ? "exception" : progress === 100 ? "success" : "active"}
            format={(percent) => `${percent}%`}
          />
        </div>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 150,
      render: (_, record) => (
        <Space size="middle">
          {record.Status !== TaskStatus.PROCESSING && (
            <Tooltip title="重新执行">
              <Button 
                type="text" 
                icon={<ReloadOutlined />} 
                onClick={() => {
                  setActionTask(record);
                  setShowRestartModal(true);
                }}
              />
            </Tooltip>
          )}
          {record.Status === TaskStatus.COMPLETED && (
            <Tooltip title="查看报告">
              <Button type="text" icon={<FileTextOutlined />} />
            </Tooltip>
          )}
          {!isReadOnly && (
            <Tooltip title="删除">
              <Button 
                type="text" 
                danger 
                icon={<DeleteOutlined />} 
                onClick={() => {
                  setActionTask(record);
                  setShowDeleteModal(true);
                }}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  // 3. 重跑任务
  const { run: restartTask, loading: restartLoading } = useRequest(
    () => taskAPI.restartTask(actionTask!.Id, projectId),
    {
      manual: true,
      onSuccess: () => {
        message.success("任务已重新开始执行");
        setShowRestartModal(false);
        refreshTasks();
      }
    }
  );

  // 4. 删除任务
  const { run: deleteTask, loading: deleteLoading } = useRequest(
    () => taskAPI.deleteTask(actionTask!.Id, projectId),
    {
      manual: true,
      onSuccess: () => {
        message.success("任务删除成功");
        setShowDeleteModal(false);
        refreshTasks();
      }
    }
  );

  // 渲染主列表视图
  const renderListView = () => (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
        <div>
          <Title level={2} style={{ margin: 0 }}>任务管理</Title>
          <Text type="secondary">创建和管理图像处理任务</Text>
        </div>
        {!isReadOnly && (
          <Button type="primary" size="large" onClick={() => setView("create")}>创建新任务</Button>
        )}
      </div>

      <Card title={
        <Space>
          <FileTextOutlined />
          <span>任务列表</span>
          <Button type="text" icon={<ReloadOutlined />} onClick={refreshTasks} />
        </Space>
      }>
        <Table
          columns={columns}
          dataSource={tasks}
          loading={tasksLoading}
          rowKey="Id"
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            total: totalTasks,
            onChange: (p, s) => { setCurrentPage(p); setPageSize(s); },
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </Card>

      {/* 重新执行确认框 */}
      <Modal
        title={
          <Space>
            <ReloadOutlined style={{ color: "#faad14" }} />
            <span>确认重新执行任务</span>
          </Space>
        }
        open={showRestartModal}
        onOk={restartTask}
        onCancel={() => setShowRestartModal(false)}
        confirmLoading={restartLoading}
        okText="确认重新执行"
        okButtonProps={{ danger: false, type: "primary", style: { backgroundColor: "#faad14", borderColor: "#faad14" } }}
      >
        <div style={{ padding: "12px 0" }}>
          <Paragraph>任务名称：<Text strong>{actionTask?.Name}</Text></Paragraph>
          <div style={{ backgroundColor: "#fffbe6", padding: "16px", borderRadius: "8px", border: "1px solid #ffe58f", marginBottom: 16 }}>
            <Space direction="vertical">
              <Space><Text type="warning"><ReloadOutlined /></Text><Text>将删除该任务的所有执行记录</Text></Space>
              <Space><Text type="warning"><ReloadOutlined /></Text><Text>将删除所有未归档的检测报告</Text></Space>
              <Space><Text type="warning"><ReloadOutlined /></Text><Text>任务将使用相同配置重新执行</Text></Space>
            </Space>
          </div>
          <Row gutter={16}>
            <Col span={12}><Text type="secondary">任务名称：</Text></Col>
            <Col span={12} style={{ textAlign: "right" }}><Text>{actionTask?.Name}</Text></Col>
            <Col span={12}><Text type="secondary">包含文件：</Text></Col>
            <Col span={12} style={{ textAlign: "right" }}><Text>{actionTask?.FileCount}个文件</Text></Col>
          </Row>
        </div>
      </Modal>

      {/* 删除确认框 */}
      <Modal
        title={
          <Space>
            <ExclamationCircleOutlined style={{ color: "#ff4d4f" }} />
            <span>确认删除任务</span>
          </Space>
        }
        open={showDeleteModal}
        onOk={deleteTask}
        onCancel={() => setShowDeleteModal(false)}
        confirmLoading={deleteLoading}
        okText="确认删除"
        okButtonProps={{ danger: true }}
      >
        <div style={{ padding: "12px 0" }}>
          <Paragraph>任务名称：<Text strong>{actionTask?.Name}</Text></Paragraph>
          <div style={{ backgroundColor: "#fff1f0", padding: "16px", borderRadius: "8px", border: "1px solid #ffa39e", marginBottom: 16 }}>
            <Space direction="vertical">
              <Space><Text type="danger"><DeleteOutlined /></Text><Text>将永久删除该任务的所有执行记录</Text></Space>
              <Space><Text type="danger"><DeleteOutlined /></Text><Text>将永久删除所有未归档的检测报告</Text></Space>
              <Space><Text type="danger"><InfoCircleOutlined /></Text><Text strong>此操作不可恢复，请谨慎操作</Text></Space>
            </Space>
          </div>
          <Row gutter={16}>
            <Col span={12}><Text type="secondary">任务名称：</Text></Col>
            <Col span={12} style={{ textAlign: "right" }}><Text>{actionTask?.Name}</Text></Col>
            <Col span={12}><Text type="secondary">包含文件：</Text></Col>
            <Col span={12} style={{ textAlign: "right" }}><Text>{actionTask?.FileCount}个文件</Text></Col>
            <Col span={12}><Text type="secondary">创建时间：</Text></Col>
            <Col span={12} style={{ textAlign: "right" }}><Text>{actionTask?.CreateTime}</Text></Col>
          </Row>
        </div>
      </Modal>
    </>
  );

  // 渲染创建任务视图
  const renderCreateView = () => <CreateTaskView onBack={() => setView("list")} projectId={projectId} onCreated={() => { setView("list"); refreshTasks(); }} />;

  return (
    <div style={{ height: "100%" }}>
      <Breadcrumb style={{ marginBottom: "24px" }}>
        <Breadcrumb.Item>项目</Breadcrumb.Item>
        <Breadcrumb.Item>{projectName}</Breadcrumb.Item>
        <Breadcrumb.Item onClick={() => setView("list")}>任务管理</Breadcrumb.Item>
        {view === "create" && <Breadcrumb.Item>创建新任务</Breadcrumb.Item>}
      </Breadcrumb>
      {view === "list" ? renderListView() : renderCreateView()}
    </div>
  );
};

// --- 创建任务视图组件 ---
interface CreateTaskViewProps {
  onBack: () => void;
  projectId: string;
  onCreated: () => void;
}

const CreateTaskView: React.FC<CreateTaskViewProps> = ({ onBack, projectId, onCreated }) => {
  const [form] = Form.useForm();
  const [showFileModal, setShowFileModal] = useState(false);
  const [selectedItems, setSelectedItems] = useState<{
    files: Set<string>;
    directories: Set<string>;
    projects: Set<string>;
  }>({
    files: new Set(),
    directories: new Set(),
    projects: new Set(),
  });

  const { run: submitTask, loading: submitting } = useRequest(
    (values: any) => {
      const payload: TaskSubmitRequest = {
        Name: values.Name,
        Description: values.Description,
        AlgorithmType: "object-detection",
        SelectedFiles: Array.from(selectedItems.files).map(id => ({ FileId: id })),
        DirectoryIds: Array.from(selectedItems.directories),
        ProjectIds: Array.from(selectedItems.projects),
      };
      return taskAPI.createTask(projectId, payload);
    },
    {
      manual: true,
      onSuccess: () => {
        message.success("任务创建成功并已开始执行");
        onCreated();
      }
    }
  );

  const totalSelectedCount = selectedItems.files.size + selectedItems.directories.size + selectedItems.projects.size;

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto" }}>
      <div style={{ marginBottom: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={onBack} type="text">返回</Button>
        <Title level={2} style={{ marginTop: 16 }}>创建新任务</Title>
        <Text type="secondary">配置检测任务的文件和参数</Text>
      </div>

      <Card title="任务设置" style={{ marginBottom: 24 }}>
        <Form form={form} layout="vertical" initialValues={{ Name: `检测任务_${new Date().getTime().toString().slice(-6)}` }}>
          <Form.Item name="Name" label="任务名称" rules={[{ required: true, message: "请输入任务名称" }]}>
            <Input placeholder="请输入任务名称" size="large" />
          </Form.Item>
          
          <div style={{ marginTop: 24 }}>
            <Text strong style={{ display: "block", marginBottom: 8 }}>选择文件或文件夹</Text>
            <div 
              style={{ 
                border: "1px dashed #d9d9d9", 
                borderRadius: "8px", 
                padding: "40px", 
                textAlign: "center",
                backgroundColor: "#fafafa",
                cursor: "pointer"
              }}
              onClick={() => setShowFileModal(true)}
            >
              <UploadOutlined style={{ fontSize: 32, color: "#bfbfbf", marginBottom: 16 }} />
              <Paragraph>请选择需要处理的文件</Paragraph>
              <Button type="primary" icon={<PlusOutlined />}>浏览文件</Button>
            </div>
          </div>

          {totalSelectedCount > 0 && (
            <div style={{ marginTop: 24 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <Text strong>已选择的文件</Text>
                <Text type="secondary">共 {totalSelectedCount} 项</Text>
              </div>
              <List
                bordered
                dataSource={[
                  ...Array.from(selectedItems.projects).map(id => ({ id, type: 'project', name: `项目: ${id}` })),
                  ...Array.from(selectedItems.directories).map(id => ({ id, type: 'directory', name: `目录: ${id}` })),
                  ...Array.from(selectedItems.files).map(id => ({ id, type: 'file', name: `文件: ${id}` })),
                ]}
                renderItem={(item) => (
                  <List.Item extra={
                    <Button type="text" icon={<DeleteOutlined />} onClick={() => {
                      const newItems = { ...selectedItems };
                      if (item.type === 'file') newItems.files.delete(item.id);
                      else if (item.type === 'directory') newItems.directories.delete(item.id);
                      else if (item.type === 'project') newItems.projects.delete(item.id);
                      setSelectedItems({ ...newItems });
                    }} />
                  }>
                    <Space>
                      {item.type === 'project' ? <ProjectOutlined style={{ color: '#1890ff' }} /> : 
                       item.type === 'directory' ? <FolderOutlined style={{ color: '#faad14' }} /> : 
                       <FileImageOutlined style={{ color: '#8c8c8c' }} />}
                      <Text>{item.name}</Text>
                    </Space>
                  </List.Item>
                )}
                style={{ maxHeight: 300, overflow: "auto", backgroundColor: "#fff" }}
              />
            </div>
          )}
        </Form>
      </Card>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginBottom: 40 }}>
        <Button size="large" onClick={onBack}>取消</Button>
        <Button 
          type="primary" 
          size="large" 
          icon={<ReloadOutlined />} 
          loading={submitting}
          disabled={totalSelectedCount === 0}
          onClick={() => form.validateFields().then(submitTask)}
        >
          启动任务
        </Button>
      </div>

      <FileSelectionModal 
        open={showFileModal} 
        onCancel={() => setShowFileModal(false)} 
        onConfirm={(items) => {
          setSelectedItems(items);
          setShowFileModal(false);
        }}
        initialSelected={selectedItems}
      />
    </div>
  );
};

// --- 文件选择弹窗组件 ---
interface FileSelectionModalProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: (items: { files: Set<string>; directories: Set<string>; projects: Set<string> }) => void;
  initialSelected: { files: Set<string>; directories: Set<string>; projects: Set<string> };
}

const FileSelectionModal: React.FC<FileSelectionModalProps> = ({ open, onCancel, onConfirm, initialSelected }) => {
  const [selectedItems, setSelectedItems] = useState(initialSelected);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);

  useEffect(() => {
    if (open) setSelectedItems(initialSelected);
  }, [open, initialSelected]);

  // 1. 获取所有可选项目
  const { data: projectsResp, loading: projectsLoading } = useRequest(projectAPI.getProjects);
  const projects = projectsResp?.Data || [];

  // 2. 获取当前项目的文件树
  const { data: filesResp, loading: filesLoading, run: fetchFiles } = useRequest(
    (pid: string) => fileAPI.getFiles(pid),
    { manual: true }
  );

  useEffect(() => {
    if (currentProjectId) fetchFiles(currentProjectId);
  }, [currentProjectId]);

  const treeData = useMemo(() => {
    const convert = (nodes: FileTreeNode[]): TreeDataNode[] => {
      return nodes.map(node => ({
        title: (
          <Space>
            {node.Type === 'directory' ? <FolderOutlined style={{ color: '#faad14' }} /> : <FileImageOutlined style={{ color: '#1890ff' }} />}
            <span>{node.Name}</span>
          </Space>
        ),
        key: node.Id,
        isLeaf: node.Type === 'file',
        children: node.Children ? convert(node.Children) : undefined,
        data: node,
      }));
    };
    return convert(filesResp?.Data || []);
  }, [filesResp]);

  const handleCheck = (checkedKeys: any, info: any) => {
    const newSelected = { ...selectedItems };
    const node = info.node.data as FileTreeNode;
    
    // 如果是勾选
    if (info.checked) {
      if (node.Type === 'directory') newSelected.directories.add(node.Id);
      else newSelected.files.add(node.Id);
    } else {
      if (node.Type === 'directory') newSelected.directories.delete(node.Id);
      else newSelected.files.delete(node.Id);
    }
    
    setSelectedItems({ ...newSelected });
  };

  const totalCount = selectedItems.files.size + selectedItems.directories.size + selectedItems.projects.size;

  return (
    <Modal
      title="选择文件"
      open={open}
      onCancel={onCancel}
      onOk={() => onConfirm(selectedItems)}
      width={900}
      okText="确认选择"
      cancelText="取消"
      className="file-selection-modal"
    >
      <div style={{ height: 500, display: "flex" }}>
        {/* 左侧项目列表 */}
        <div style={{ width: 240, borderRight: "1px solid #f0f0f0", padding: "0 16px 0 0", overflowY: "auto" }}>
          <div style={{ marginBottom: 12, padding: "8px 0" }}><Text strong>项目列表</Text></div>
          <List
            loading={projectsLoading}
            dataSource={projects}
            renderItem={(p) => (
              <div 
                style={{ 
                  padding: "10px 12px", 
                  cursor: "pointer", 
                  borderRadius: "6px",
                  backgroundColor: currentProjectId === p.Id ? "#e6f7ff" : "transparent",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 4
                }}
                onClick={() => setCurrentProjectId(p.Id)}
              >
                <Space>
                  <ProjectOutlined style={{ color: currentProjectId === p.Id ? "#1890ff" : "#8c8c8c" }} />
                  <Text ellipsis={{ tooltip: p.Name }} style={{ width: 120 }}>{p.Name}</Text>
                </Space>
                <Checkbox 
                  checked={selectedItems.projects.has(p.Id)}
                  onChange={(e) => {
                    const newItems = { ...selectedItems };
                    if (e.target.checked) newItems.projects.add(p.Id);
                    else newItems.projects.delete(p.Id);
                    setSelectedItems({ ...newItems });
                  }}
                />
              </div>
            )}
          />
        </div>

        {/* 右侧文件树 */}
        <div style={{ flex: 1, padding: "0 0 0 16px", overflowY: "auto" }}>
          {currentProjectId ? (
            <>
              <div style={{ marginBottom: 12, padding: "8px 0", display: "flex", justifyContent: "space-between" }}>
                <Text strong>文件目录</Text>
                <Text type="secondary">{projects.find(p => p.Id === currentProjectId)?.Name}</Text>
              </div>
              {filesLoading ? (
                <div style={{ textAlign: "center", paddingTop: 100 }}><SyncOutlined spin /></div>
              ) : treeData.length > 0 ? (
                <Tree
                  checkable
                  treeData={treeData}
                  onCheck={handleCheck}
                  checkedKeys={[...Array.from(selectedItems.files), ...Array.from(selectedItems.directories)]}
                  height={400}
                  selectable={false}
                />
              ) : (
                <Empty description="该项目下暂无文件" style={{ marginTop: 100 }} />
              )}
            </>
          ) : (
            <div style={{ textAlign: "center", paddingTop: 200 }}>
              <Empty description="请从左侧选择一个项目来浏览文件" />
            </div>
          )}
        </div>
      </div>
      <div style={{ marginTop: 16, borderTop: "1px solid #f0f0f0", paddingTop: 16, display: "flex", alignItems: "center" }}>
        <InfoCircleOutlined style={{ color: "#1890ff", marginRight: 8 }} />
        <Text>已从授权项目中选择 <Text strong>{totalCount}</Text> 个资源</Text>
      </div>
    </Modal>
  );
};

export default TasksPage;
