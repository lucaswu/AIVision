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
  Statistic,
  Pagination,
  List,
  Drawer,
} from "antd";
import {
  PlusOutlined,
  FileImageOutlined,
  FolderOutlined,
  MoreOutlined,
  DeleteOutlined,
  EyeOutlined,
  EditOutlined,
} from "@ant-design/icons";
import type { TableColumnsType, TreeDataNode, MenuProps } from "antd";
import { useParams } from "react-router-dom";
import { Project } from "@/utils/data";
import { useRequest } from "ahooks";
import { taskAPI, fileAPI } from "../../utils/api";
import { Task, CreateTaskRequest, TaskStatus } from "../../utils/data";

const { Title, Text } = Typography;
const { TextArea } = Input;

// 树形节点数据结构
interface TreeNode {
  id: string;
  name: string;
  type: "directory" | "file";
  size?: string;
  uploadDate?: string;
  path: string;
  projectId: string;
  children?: TreeNode[];
  fileType?: string;
  category?: string;
}

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
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [deletingTask, setDeletingTask] = useState<Task | null>(null);
  const [viewingTask, setViewingTask] = useState<Task | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  // 文件选择相关状态
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
  const [fileTreeModalVisible, setFileTreeModalVisible] = useState(false);
  const [fileCurrentPage, setFileCurrentPage] = useState(1);
  const [filePageSize, setFilePageSize] = useState(10);
  const [selectedDirectoryPath, setSelectedDirectoryPath] =
    useState<string>("");

  const {
    data: tasksResponse,
    loading: tasksLoading,
    refresh: refreshTasks,
  } = useRequest(
    () => {
      return taskAPI.getTasks(projectId, { page: currentPage, pageSize });
    },
    {
      refreshDeps: [currentPage, pageSize, projectId],
      pollingInterval: 3000, // 每3秒轮询一次任务状态
      pollingWhenHidden: false, // 页面隐藏时停止轮询
    }
  );

  const tasks = tasksResponse?.Data?.Tasks || [];
  const total = tasksResponse?.Data?.TotalCount || 0;

  const handlePaginationChange = (page: number, size: number) => {
    setCurrentPage(page);
    setPageSize(size);
  };

  const handleShowSizeChange = (current: number, size: number) => {
    setCurrentPage(1);
    setPageSize(size);
  };

  const { run: createTask, loading: createLoading } = useRequest(
    (data: any) => {
      return taskAPI.createTask(projectId, data);
    },
    {
      manual: true,
      onSuccess: () => {
        message.success("任务创建成功");
        setShowCreateModal(false);
        createForm.resetFields();
        setSelectedFileIds([]);
        refreshTasks();
      },
      onError: () => {
        message.error("任务创建失败");
      },
    }
  );

  const { run: updateTask, loading: updateLoading } = useRequest(
    ({
      taskId,
      data,
    }: {
      taskId: string;
      data: Partial<CreateTaskRequest>;
    }) => {
      return taskAPI.updateTask(taskId, projectId, data);
    },
    {
      manual: true,
      onSuccess: () => {
        message.success("任务更新成功");
        setShowEditModal(false);
        setEditingTask(null);
        editForm.resetFields();
        refreshTasks();
      },
      onError: () => {
        message.error("任务更新失败");
      },
    }
  );

  const { run: deleteTask, loading: deleteLoading } = useRequest(
    (taskId: string) => taskAPI.deleteTask(taskId, projectId),
    {
      manual: true,
      onSuccess: () => {
        message.success("任务删除成功");
        setShowDeleteModal(false);
        setDeletingTask(null);
        refreshTasks();
      },
      onError: () => {
        message.error("任务删除失败");
      },
    }
  );

  const handleViewDetail = (task: Task) => {
    setViewingTask(task);
    setShowDetailModal(true);
  };

  const handleEdit = (task: Task) => {
    setEditingTask(task);
    editForm.setFieldsValue({
      Name: task.Name,
      Description: task.Description,
      AlgorithmType: task.AlgorithmType,
    });
    setShowEditModal(true);
  };

  const handleDelete = (task: Task) => {
    setDeletingTask(task);
    setShowDeleteModal(true);
  };

  const handleCreateSubmit = async () => {
    try {
      const values = await createForm.validateFields();
      // 将选中的文件ID转换为API需要的格式
      const taskData: CreateTaskRequest = {
        ...values,
        SelectedFiles: selectedFileIds.map((fileId) => ({ FileId: fileId })),
      };
      createTask(taskData);
    } catch (error) {
      console.error("表单验证失败:", error);
    }
  };

  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();
      if (editingTask) {
        updateTask({ taskId: editingTask.Id, data: values });
      }
    } catch (error) {
      console.error("表单验证失败:", error);
    }
  };

  const handleDeleteConfirm = () => {
    if (deletingTask) {
      deleteTask(deletingTask.Id);
    }
  };

  const getStatusTag = (status: Task["Status"]) => {
    const statusConfig = {
      [TaskStatus.PENDING]: { color: "default", text: "等待中" },
      [TaskStatus.PROCESSING]: { color: "processing", text: "处理中" },
      [TaskStatus.COMPLETED]: { color: "success", text: "已完成" },
      [TaskStatus.FAILED]: { color: "error", text: "失败" },
      [TaskStatus.CANCELLED]: { color: "warning", text: "已取消" },
    };

    const config = statusConfig[status] || { color: "default", text: status };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const getActionMenuItems = (task: Task): MenuProps["items"] => {
    const items: MenuProps["items"] = [
      {
        key: "view",
        icon: <EyeOutlined />,
        label: "查看详情",
        onClick: () => handleViewDetail(task),
      },
    ];

    if (!isReadOnly) {
      items.push({
        key: "delete",
        icon: <DeleteOutlined />,
        label: "删除",
        onClick: () => handleDelete(task),
      });
    }

    return items;
  };

  const columns: TableColumnsType<Task> = [
    {
      title: "任务名称",
      dataIndex: "Name",
      key: "Name",
      width: 200,
    },
    {
      title: "算法类型",
      dataIndex: "AlgorithmType",
      key: "AlgorithmType",
      width: 150,
    },
    {
      title: "文件数量",
      dataIndex: "FileCount",
      key: "FileCount",
      width: 100,
    },
    {
      title: "状态",
      dataIndex: "Status",
      key: "Status",
      width: 120,
      render: (status) => getStatusTag(status),
    },
    {
      title: "进度",
      dataIndex: "Progress",
      key: "Progress",
      width: 150,
      render: (progress) => (
        <Progress
          percent={progress || 0}
          size="small"
          status={progress === 100 ? "success" : "active"}
        />
      ),
    },
    {
      title: "创建时间",
      dataIndex: "CreateTime",
      key: "CreateTime",
      width: 150,
    },
    {
      title: "操作",
      key: "action",
      width: 200,
      render: (_, record) => (
        <Space size="small">
          <Dropdown
            menu={{ items: getActionMenuItems(record) }}
            trigger={["click"]}
          >
            <Button type="text" icon={<MoreOutlined />}>
              操作
            </Button>
          </Dropdown>
        </Space>
      ),
    },
  ];

  const stats = {
    total: tasks.length,
    running: tasks.filter((t) => t.Status === TaskStatus.PROCESSING).length,
    completed: tasks.filter((t) => t.Status === TaskStatus.COMPLETED).length,
    failed: tasks.filter((t) => t.Status === TaskStatus.FAILED).length,
  };

  // 获取文件树数据
  const { data: filesResponse, loading: filesLoading } = useRequest(
    () => {
      return fileAPI.getFiles(projectId);
    },
    {
      refreshDeps: [projectId],
    }
  );

  const fileTreeData = filesResponse?.Data || [];

  // 将FileTreeNode转换为TreeNode
  const convertFileTreeNodeToTreeNode = (nodes): TreeNode[] => {
    return nodes.map((node) => ({
      id: node.Id,
      name: node.Name,
      type: node.Type as "directory" | "file",
      size: typeof node.Size === "number" ? node.Size.toString() : node.Size,
      uploadDate: node.UploadDate || "",
      path: node.Path,
      projectId: node.ProjectId,
      children: node.Children
        ? convertFileTreeNodeToTreeNode(node.Children)
        : undefined,
      fileType: node.FileType,
      category: node.Type,
    }));
  };

  const convertedFileTreeData = useMemo(
    () => convertFileTreeNodeToTreeNode(fileTreeData),
    [fileTreeData, projectId]
  );

  // 获取所有文件（扁平化）
  const getAllFiles = (nodes: TreeNode[]): TreeNode[] => {
    const files: TreeNode[] = [];
    const traverse = (nodeList: TreeNode[]) => {
      nodeList.forEach((node) => {
        if (node.type === "file") {
          files.push(node);
        }
        if (node.children) {
          traverse(node.children);
        }
      });
    };
    traverse(nodes);
    return files;
  };

  // 递归转换为Ant Design树形数据格式
  const convertToTreeData = (nodes: TreeNode[]): TreeDataNode[] => {
    return nodes
      .filter((node) => node.type === "directory") // 只显示目录
      .map((node) => ({
        title: (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Space size={8}>
              <FolderOutlined style={{ color: "#faad14" }} />
              <span>{node.name}</span>
            </Space>
            <Text
              type="secondary"
              style={{ fontSize: "12px", marginLeft: "16px" }}
            >
              {/* 显示目录下文件数量 */}
              {node.children ? getAllFiles([node]).length : 0} 个文件
            </Text>
          </div>
        ),
        key: node.id,
        isLeaf: false,
        children: node.children ? convertToTreeData(node.children) : undefined,
        data: node,
      }));
  };

  const treeData = useMemo(
    () => convertToTreeData(convertedFileTreeData),
    [convertedFileTreeData]
  );

  const allFiles = useMemo(
    () => getAllFiles(convertedFileTreeData),
    [convertedFileTreeData]
  );

  // 根据选择的目录获取文件
  const getFilesInDirectory = (
    nodes: TreeNode[],
    targetPath: string
  ): TreeNode[] => {
    if (!targetPath) {
      return getAllFiles(nodes); // 如果没有选择目录，返回所有文件
    }

    const files: TreeNode[] = [];
    const findDirectory = (
      nodeList: TreeNode[],
      path: string
    ): TreeNode | null => {
      for (const node of nodeList) {
        if (node.path === path && node.type === "directory") {
          return node;
        }
        if (node.children) {
          const found = findDirectory(node.children, path);
          if (found) return found;
        }
      }
      return null;
    };

    const targetDirectory = findDirectory(nodes, targetPath);
    if (targetDirectory && targetDirectory.children) {
      return getAllFiles([targetDirectory]);
    }
    return [];
  };

  const filteredFiles = useMemo(
    () => getFilesInDirectory(convertedFileTreeData, selectedDirectoryPath),
    [convertedFileTreeData, selectedDirectoryPath]
  );

  // 默认选择第一个目录
  useEffect(() => {
    if (convertedFileTreeData.length > 0 && !selectedDirectoryPath) {
      const getFirstDirectory = (nodes: TreeNode[]): TreeNode | null => {
        for (const node of nodes) {
          if (node.type === "directory") {
            return node;
          }
          if (node.children) {
            const found = getFirstDirectory(node.children);
            if (found) return found;
          }
        }
        return null;
      };

      const firstDirectory = getFirstDirectory(convertedFileTreeData);
      if (firstDirectory) {
        setSelectedDirectoryPath(firstDirectory.path);
        setExpandedKeys([firstDirectory.id]); // 展开第一个目录
      }
    }
  }, [convertedFileTreeData, selectedDirectoryPath]);

  // 分页处理
  const paginatedFiles = useMemo(() => {
    const startIndex = (fileCurrentPage - 1) * filePageSize;
    const endIndex = startIndex + filePageSize;
    return filteredFiles.slice(startIndex, endIndex);
  }, [filteredFiles, fileCurrentPage, filePageSize]);

  // 处理文件选择
  const handleFileSelect = (fileId: string, checked: boolean) => {
    if (checked) {
      setSelectedFileIds((prev) => [...prev, fileId]);
    } else {
      setSelectedFileIds((prev) => prev.filter((id) => id !== fileId));
    }
  };

  // 处理全选/取消全选
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const allFileIds = filteredFiles.map((file) => file.id);
      setSelectedFileIds((prev) => [...new Set([...prev, ...allFileIds])]);
    } else {
      const filteredFileIds = filteredFiles.map((file) => file.id);
      setSelectedFileIds((prev) =>
        prev.filter((id) => !filteredFileIds.includes(id))
      );
    }
  };

  // 获取选中文件的详细信息
  const getSelectedFilesInfo = () => {
    return selectedFileIds
      .map((id) => {
        const file = allFiles.find((f) => f.id === id);
        if (!file) return null;

        // 构建显示路径：移除项目根路径，只显示相对路径
        const displayPath = file.path.startsWith("/")
          ? file.path.substring(1)
          : file.path;

        return {
          value: file.id,
          label: `${displayPath}/${file.name}`,
          fileName: file.name,
        };
      })
      .filter(Boolean);
  };

  // 处理目录选择
  const handleDirectorySelect = (selectedKeys: React.Key[]) => {
    if (selectedKeys.length > 0) {
      const selectedKey = selectedKeys[0] as string;
      // 根据key找到对应的目录节点
      const findNodeByKey = (
        nodes: TreeNode[],
        key: string
      ): TreeNode | null => {
        for (const node of nodes) {
          if (node.id === key) {
            return node;
          }
          if (node.children) {
            const found = findNodeByKey(node.children, key);
            if (found) return found;
          }
        }
        return null;
      };

      const selectedNode = findNodeByKey(convertedFileTreeData, selectedKey);
      if (selectedNode) {
        setSelectedDirectoryPath(selectedNode.path);
        setFileCurrentPage(1); // 重置页码
      }
    }
    // 移除了取消选择的逻辑，确保始终有目录被选中
  };

  return (
    <div>
      <Breadcrumb style={{ marginBottom: "24px" }}>
        <Breadcrumb.Item>项目管理</Breadcrumb.Item>
        <Breadcrumb.Item>{projectName}</Breadcrumb.Item>
        <Breadcrumb.Item>任务管理</Breadcrumb.Item>
      </Breadcrumb>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "24px",
        }}
      >
        <Title level={2} style={{ margin: 0 }}>
          任务管理
        </Title>
        {!isReadOnly && (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setShowCreateModal(true)}
          >
            创建任务
          </Button>
        )}
      </div>

      <Row gutter={16} style={{ marginBottom: "24px" }}>
        <Col span={6}>
          <Card>
            <Statistic title="总任务数" value={stats.total} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="处理中"
              value={stats.running}
              valueStyle={{ color: "#1890ff" }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="已完成"
              value={stats.completed}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="失败"
              value={stats.failed}
              valueStyle={{ color: "#ff4d4f" }}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Table
          columns={columns}
          dataSource={tasks}
          loading={tasksLoading}
          rowKey="Id"
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) =>
              `第 ${range[0]}-${range[1]} 条/共 ${total} 条`,
            pageSizeOptions: ["10", "20", "50", "100"],
            onChange: handlePaginationChange,
            onShowSizeChange: handleShowSizeChange,
          }}
        />
      </Card>

      <Drawer
        title="创建新任务"
        placement="right"
        width={800}
        visible={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          createForm.resetFields();
          setSelectedFileIds([]);
        }}
        footer={
          <div style={{ textAlign: "right" }}>
            <Space>
              <Button
                onClick={() => {
                  setShowCreateModal(false);
                  createForm.resetFields();
                  setSelectedFileIds([]);
                }}
              >
                取消
              </Button>
              <Button type="primary" onClick={handleCreateSubmit}>
                创建
              </Button>
            </Space>
          </div>
        }
      >
        <Form form={createForm} layout="vertical" style={{ marginTop: "24px" }}>
          <Form.Item
            name="Name"
            label="任务名称"
            rules={[{ required: true, message: "请输入任务名称" }]}
          >
            <Input placeholder="请输入任务名称" />
          </Form.Item>

          <Form.Item name="Description" label="任务描述">
            <TextArea rows={3} placeholder="请输入任务描述（可选）" />
          </Form.Item>

          <Form.Item
            name="AlgorithmType"
            label="算法类型"
            rules={[{ required: true, message: "请选择算法类型" }]}
          >
            <Select placeholder="请选择算法类型">
              <Select.Option value="object-detection">目标检测</Select.Option>
              <Select.Option value="defect-detection">缺陷检测</Select.Option>
              <Select.Option value="classification">图像分类</Select.Option>
              <Select.Option value="segmentation">图像分割</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="SelectedFiles"
            label="选择文件"
            required
            rules={[
              {
                required: true,
                validator: () => {
                  if (selectedFileIds.length === 0) {
                    return Promise.reject(new Error("请选择要处理的文件"));
                  }
                  return Promise.resolve();
                },
              },
            ]}
          >
            <div
              style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}
            >
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    minHeight: "32px",
                    border: "1px solid #d9d9d9",
                    borderRadius: "6px",
                    padding: "4px 11px",
                    backgroundColor:
                      selectedFileIds.length > 0 ? "#f6ffed" : "#fafafa",
                  }}
                >
                  {selectedFileIds.length > 0 ? (
                    <Space wrap>
                      {getSelectedFilesInfo().map((file: any) => (
                        <Tag
                          key={file.value}
                          closable
                          onClose={() => handleFileSelect(file.value, false)}
                        >
                          {file.label}
                        </Tag>
                      ))}
                    </Space>
                  ) : (
                    <Text type="secondary">请选择要处理的文件</Text>
                  )}
                </div>
                {selectedFileIds.length > 0 && (
                  <Text
                    type="secondary"
                    style={{
                      fontSize: "12px",
                      marginTop: "4px",
                      display: "block",
                    }}
                  >
                    已选择 {selectedFileIds.length} 个文件
                  </Text>
                )}
              </div>
              <Button
                icon={<FolderOutlined />}
                onClick={() => setFileTreeModalVisible(true)}
              >
                选择文件
              </Button>
            </div>
          </Form.Item>
        </Form>
      </Drawer>



      <Modal
        title="删除任务"
        open={showDeleteModal}
        onOk={handleDeleteConfirm}
        onCancel={() => {
          setShowDeleteModal(false);
          setDeletingTask(null);
        }}
        confirmLoading={deleteLoading}
      >
        <p>确定要删除任务 "{deletingTask?.Name}" 吗？此操作不可撤销。</p>
      </Modal>

      {/* 任务详情模态框 */}
      <Modal
        title="任务详情"
        open={showDetailModal}
        onCancel={() => {
          setShowDetailModal(false);
          setViewingTask(null);
        }}
        footer={[
          <Button key="close" onClick={() => {
            setShowDetailModal(false);
            setViewingTask(null);
          }}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {viewingTask && (
          <div>
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Card size="small" title="基本信息">
                  <p><strong>任务名称：</strong>{viewingTask.Name}</p>
                  <p><strong>算法类型：</strong>{viewingTask.AlgorithmType}</p>
                  <p><strong>任务描述：</strong>{viewingTask.Description || '无'}</p>
                  <p><strong>状态：</strong>{getStatusTag(viewingTask.Status)}</p>
                </Card>
              </Col>
              <Col span={12}>
                <Card size="small" title="执行信息">
                  <p><strong>创建时间：</strong>{viewingTask.CreateTime}</p>
                  <p><strong>更新时间：</strong>{viewingTask.UpdatedAt}</p>
                  <p><strong>开始时间：</strong>{viewingTask.ProcessingStartTime || '未开始'}</p>
                  <p><strong>结束时间：</strong>{viewingTask.ProcessingEndTime || '未结束'}</p>
                </Card>
              </Col>
            </Row>
            
            <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
              <Col span={12}>
                <Card size="small" title="文件统计">
                  <p><strong>总文件数：</strong>{viewingTask.FileCount}</p>
                  <p><strong>已处理：</strong>{viewingTask.ProcessedFiles}</p>
                  <p><strong>成功：</strong>{viewingTask.SuccessFiles}</p>
                  <p><strong>失败：</strong>{viewingTask.FailedFiles}</p>
                </Card>
              </Col>
              <Col span={12}>
                <Card size="small" title="执行进度">
                  <Progress 
                    percent={viewingTask.Progress || 0} 
                    status={viewingTask.Progress === 100 ? "success" : "active"}
                    strokeWidth={8}
                  />
                  <p style={{ textAlign: 'center', marginTop: 8 }}>
                    {viewingTask.Progress || 0}% 完成
                  </p>
                </Card>
              </Col>
            </Row>

            {viewingTask.TaskFiles && viewingTask.TaskFiles.length > 0 && (
              <Card size="small" title="任务文件详情" style={{ marginTop: 16 }}>
                <Table
                  dataSource={viewingTask.TaskFiles}
                  rowKey="TaskFileId"
                  size="small"
                  pagination={false}
                  scroll={{ y: 300 }}
                  columns={[
                    {
                      title: '文件名',
                      dataIndex: 'FileName',
                      key: 'FileName',
                      width: 200,
                    },
                    {
                      title: '状态',
                      dataIndex: 'Status',
                      key: 'Status',
                      width: 100,
                      render: (status) => getStatusTag(status),
                    },
                    {
                      title: '开始时间',
                      dataIndex: 'ProcessingStartTime',
                      key: 'ProcessingStartTime',
                      width: 150,
                      render: (time) => time || '-',
                    },
                    {
                      title: '结束时间',
                      dataIndex: 'ProcessingEndTime',
                      key: 'ProcessingEndTime',
                      width: 150,
                      render: (time) => time || '-',
                    },
                    {
                      title: '错误信息',
                      dataIndex: 'ErrorMessage',
                      key: 'ErrorMessage',
                      render: (error) => error || '-',
                    }
                  ]}
                />
              </Card>
            )}
          </div>
        )}
      </Modal>

      {/* 文件选择模态框 */}
      <Modal
        title="选择文件"
        visible={fileTreeModalVisible}
        onCancel={() => setFileTreeModalVisible(false)}
        onOk={() => {
          // 处理确认选择
          console.log("选中的文件:", getSelectedFilesInfo());
          setFileTreeModalVisible(false);
        }}
        width={1000}
        className="file-selection-modal"
      >
        <div style={{ display: "flex", gap: "16px" }}>
          {/* 左侧文件树 */}
          <div
            style={{
              width: "350px",
              borderRight: "1px solid #f0f0f0",
              paddingRight: "16px",
            }}
          >
            <div style={{ marginBottom: "16px" }}>
              <Text strong>文件目录</Text>
            </div>
            <Tree
              treeData={treeData}
              expandedKeys={expandedKeys}
              selectedKeys={
                selectedDirectoryPath
                  ? [
                      // 根据path找到对应的key
                      (() => {
                        const findKeyByPath = (
                          nodes: TreeNode[],
                          path: string
                        ): string => {
                          for (const node of nodes) {
                            if (node.path === path) {
                              return node.id;
                            }
                            if (node.children) {
                              const found = findKeyByPath(node.children, path);
                              if (found) return found;
                            }
                          }
                          return "";
                        };
                        return findKeyByPath(
                          convertedFileTreeData,
                          selectedDirectoryPath
                        );
                      })(),
                    ]
                  : []
              }
              onExpand={setExpandedKeys}
              onSelect={handleDirectorySelect}
              showIcon={false}
              blockNode
              height={400}
              style={{ overflow: "auto" }}
            />
          </div>

          {/* 右侧文件列表 */}
          <div style={{ flex: 1 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "16px",
              }}
            >
              <Space>
                <Text strong>文件列表</Text>
                <Text type="secondary">
                  当前目录: {filteredFiles.length} 个文件
                </Text>
              </Space>
              <Space>
                <Checkbox
                  checked={
                    filteredFiles.length > 0 &&
                    filteredFiles.every((file) =>
                      selectedFileIds.includes(file.id)
                    )
                  }
                  indeterminate={
                    filteredFiles.some((file) =>
                      selectedFileIds.includes(file.id)
                    ) &&
                    !filteredFiles.every((file) =>
                      selectedFileIds.includes(file.id)
                    )
                  }
                  onChange={(e) => handleSelectAll(e.target.checked)}
                >
                  全选当前页
                </Checkbox>
                <Text type="secondary">
                  已选择 {selectedFileIds.length} 个文件
                </Text>
              </Space>
            </div>

            {/* 文件列表 */}
            <div
              style={{
                maxHeight: "320px",
                overflow: "auto",
                border: "1px solid #f0f0f0",
                borderRadius: "6px",
              }}
            >
              <List
                dataSource={paginatedFiles}
                renderItem={(file) => (
                  <List.Item
                    key={file.id}
                    style={{
                      padding: "12px 16px",
                      borderBottom: "1px solid #f5f5f5",
                    }}
                  >
                    <List.Item.Meta
                      avatar={
                        <Checkbox
                          checked={selectedFileIds.includes(file.id)}
                          onChange={(e) =>
                            handleFileSelect(file.id, e.target.checked)
                          }
                        />
                      }
                      title={
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                          }}
                        >
                          <FileImageOutlined
                            style={{ color: "#1890ff", fontSize: "16px" }}
                          />
                          <Text>{file.name}</Text>
                        </div>
                      }
                      description={
                        <Space>
                          <Text type="secondary" style={{ fontSize: "12px" }}>
                            {file.size}
                          </Text>
                          <Text type="secondary" style={{ fontSize: "12px" }}>
                            {file.uploadDate}
                          </Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            </div>

            {/* 分页 */}
            {filteredFiles.length > filePageSize && (
              <div style={{ marginTop: "16px", textAlign: "center" }}>
                <Pagination
                  current={fileCurrentPage}
                  pageSize={filePageSize}
                  total={filteredFiles.length}
                  onChange={(page, size) => {
                    setFileCurrentPage(page);
                    setFilePageSize(size || 10);
                  }}
                  showSizeChanger
                  showQuickJumper
                  showTotal={(total, range) =>
                    `第 ${range[0]}-${range[1]} 项，共 ${total} 项`
                  }
                />
              </div>
            )}
          </div>
        </div>

        {/* 底部已选文件显示区域 */}
        {selectedFileIds.length > 0 && (
          <div
            style={{
              marginTop: "24px",
              padding: "16px",
              backgroundColor: "#f6ffed",
              border: "1px solid #b7eb8f",
              borderRadius: "6px",
            }}
          >
            <div style={{ marginBottom: "12px" }}>
              <Text strong>已选文件 ({selectedFileIds.length} 个)</Text>
              <Button
                type="link"
                size="small"
                style={{ padding: 0, marginLeft: "8px" }}
                onClick={() => setSelectedFileIds([])}
              >
                清空选择
              </Button>
            </div>
            <div
              style={{
                maxHeight: "120px",
                overflow: "auto",
                display: "flex",
                flexWrap: "wrap",
                gap: "8px",
              }}
            >
              {getSelectedFilesInfo().map((file: any) => (
                <Tag
                  key={file.value}
                  closable
                  onClose={() => handleFileSelect(file.value, false)}
                  style={{
                    marginBottom: "4px",
                    padding: "4px 8px",
                    borderRadius: "4px",
                    backgroundColor: "#ffffff",
                    border: "1px solid #52c41a",
                    color: "#389e0d",
                  }}
                >
                  {file.label}
                </Tag>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default TasksPage;
