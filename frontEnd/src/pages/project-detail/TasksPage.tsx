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
import { useNavigate } from "react-router-dom";
import { taskAPI, fileAPI } from "../../utils/api";
import { Task, TaskStatus, FileTreeNode, TaskSubmitRequest } from "../../utils/data";

const { Title, Text, Paragraph, Link } = Typography;

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
  const navigate = useNavigate();
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
      pollingInterval: 1000,
    }
  );

  const tasks = tasksResponse?.Data?.Tasks || [];
  const totalTasks = tasksResponse?.Data?.TotalCount || 0;

  const openReportReview = (taskId: string) => {
    const params = new URLSearchParams({ taskId, view: "review" });
    navigate(`/projects/${projectId}/reports?${params.toString()}`);
  };

  // 2. 任务列表列定义
  const columns: TableColumnsType<Task> = [
    {
      title: "任务名称",
      dataIndex: "Name",
      key: "Name",
      width: 200,
      render: (text, record) =>
        record.Status === TaskStatus.COMPLETED ? (
          <Link strong onClick={() => openReportReview(record.Id)}>
            {text}
          </Link>
        ) : (
          <Text strong>{text}</Text>
        ),
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
            <Tooltip title="审核报告">
              <Button 
                type="text" 
                icon={<FileTextOutlined />} 
                onClick={() => openReportReview(record.Id)}
              />
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
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flexShrink: 0, display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
        <div>
          <Title level={2} style={{ margin: 0 }}>任务管理</Title>
          <Text type="secondary">创建和管理图像处理任务</Text>
        </div>
        {!isReadOnly && (
          <Button type="primary" size="large" onClick={() => setView("create")}>创建新任务</Button>
        )}
      </div>

      <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
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
      </div>

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
    </div>
  );

  // 渲染创建任务视图
  const renderCreateView = () => (
    <CreateTaskView
      onBack={() => setView("list")}
      projectId={projectId}
      projectName={projectName}
      onCreated={() => {
        setView("list");
        refreshTasks();
      }}
    />
  );

  return (
    <div style={{ padding: 24, height: "100%", display: "flex", flexDirection: "column", boxSizing: "border-box" }}>
      <Breadcrumb 
        style={{ marginBottom: "24px", flexShrink: 0 }}
        items={[
          { title: '项目' },
          { title: projectName },
          { 
            title: '任务管理', 
            onClick: () => setView("list"),
            className: "breadcrumb-link"
          },
          ...(view === "create" ? [{ title: '创建新任务' }] : []),
        ]}
      />
      <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
        {view === "list" ? renderListView() : renderCreateView()}
      </div>
    </div>
  );
};

// --- 创建任务视图组件 ---
interface CreateTaskViewProps {
  onBack: () => void;
  projectId: string;
  projectName: string;
  onCreated: () => void;
}

interface SelectedItemMeta {
  name: string;
  path?: string;
}

interface SelectedItemsState {
  files: Map<string, SelectedItemMeta>;
  directories: Map<string, SelectedItemMeta>;
}

interface EffectiveSelectedItem {
  id: string;
  type: "directory" | "file";
  name: string;
  path?: string;
}

const createEmptySelectedItems = (): SelectedItemsState => ({
  files: new Map(),
  directories: new Map(),
});

const getEffectiveDirectoryIds = (selectedItems: SelectedItemsState): string[] => {
  const selectedFilePaths = Array.from(selectedItems.files.values())
    .map((item) => item.path)
    .filter((path): path is string => Boolean(path));

  return Array.from(selectedItems.directories.entries())
    .filter(([, directory]) => {
      if (!directory.path) {
        return true;
      }

      return !selectedFilePaths.some(
        (filePath) => filePath === directory.path || filePath.startsWith(`${directory.path}/`)
      );
    })
    .map(([id]) => id);
};

const getEffectiveSelectedItems = (
  selectedItems: SelectedItemsState
): EffectiveSelectedItem[] => {
  const effectiveDirectoryIdSet = new Set(getEffectiveDirectoryIds(selectedItems));
  const fileItems = Array.from<[string, SelectedItemMeta]>(selectedItems.files.entries()).map(
    ([id, item]) => ({
      id,
      type: "file" as const,
      name: item.name,
      path: item.path,
    })
  );
  const directoryItems = Array.from<[string, SelectedItemMeta]>(
    selectedItems.directories.entries()
  )
    .filter(([id]) => effectiveDirectoryIdSet.has(id))
    .map(([id, item]) => ({
      id,
      type: "directory" as const,
      name: item.name,
      path: item.path,
    }));

  return [...directoryItems, ...fileItems];
};

const buildDirectoryPathIdMap = (
  nodes: FileTreeNode[],
  map: Map<string, string> = new Map()
): Map<string, string> => {
  nodes.forEach((node) => {
    if (node.Type === "directory") {
      map.set(node.Path, node.Id);
      if (node.Children?.length) {
        buildDirectoryPathIdMap(node.Children, map);
      }
    }
  });

  return map;
};

const getAncestorDirectoryIdsForFiles = (
  files: Map<string, SelectedItemMeta>,
  directoryPathIdMap: Map<string, string>
): string[] => {
  const directoryIds = new Set<string>();

  Array.from(files.values()).forEach((file) => {
    if (!file.path) {
      return;
    }

    const parts = file.path.split("/").filter(Boolean);
    let currentPath = "";

    for (let i = 0; i < parts.length - 1; i += 1) {
      currentPath += `/${parts[i]}`;
      const directoryId = directoryPathIdMap.get(currentPath);
      if (directoryId) {
        directoryIds.add(directoryId);
      }
    }
  });

  return Array.from(directoryIds);
};

const clearDirectorySubtreeSelections = (
  node: FileTreeNode,
  selectedItems: SelectedItemsState
) => {
  selectedItems.directories.delete(node.Id);

  node.Children?.forEach((child) => {
    if (child.Type === "directory") {
      clearDirectorySubtreeSelections(child, selectedItems);
      return;
    }

    selectedItems.files.delete(child.Id);
  });
};

const addDirectorySubtreeFileSelections = (
  node: FileTreeNode,
  selectedItems: SelectedItemsState
): number => {
  if (node.Type === "file") {
    selectedItems.files.set(node.Id, { name: node.Name, path: node.Path });
    return 1;
  }

  let selectedFileCount = 0;
  node.Children?.forEach((child) => {
    selectedFileCount += addDirectorySubtreeFileSelections(child, selectedItems);
  });

  if (selectedFileCount === 0) {
    selectedItems.directories.set(node.Id, { name: node.Name, path: node.Path });
  } else {
    selectedItems.directories.delete(node.Id);
  }

  return selectedFileCount;
};

const removeAncestorDirectorySelections = (
  filePath: string | undefined,
  selectedItems: SelectedItemsState
) => {
  if (!filePath) {
    return;
  }

  Array.from(selectedItems.directories.entries()).forEach(([id, directory]) => {
    if (
      directory.path &&
      (filePath === directory.path || filePath.startsWith(`${directory.path}/`))
    ) {
      selectedItems.directories.delete(id);
    }
  });
};

const getDirectoryCheckState = (
  nodes: FileTreeNode[],
  selectedItems: SelectedItemsState
) => {
  const checkedDirectoryIds = new Set<string>();
  const halfCheckedDirectoryIds = new Set<string>();

  const walk = (node: FileTreeNode): { totalFiles: number; selectedFiles: number; hasSelection: boolean } => {
    if (node.Type === "file") {
      const selected = selectedItems.files.has(node.Id);
      return {
        totalFiles: 1,
        selectedFiles: selected ? 1 : 0,
        hasSelection: selected,
      };
    }

    let totalFiles = 0;
    let selectedFiles = 0;
    let hasSelection = selectedItems.directories.has(node.Id);

    node.Children?.forEach((child) => {
      const childState = walk(child);
      totalFiles += childState.totalFiles;
      selectedFiles += childState.selectedFiles;
      hasSelection = hasSelection || childState.hasSelection;
    });

    if (totalFiles === 0) {
      if (selectedItems.directories.has(node.Id)) {
        checkedDirectoryIds.add(node.Id);
      }
    } else if (selectedFiles === totalFiles) {
      checkedDirectoryIds.add(node.Id);
    } else if (selectedFiles > 0 || hasSelection) {
      halfCheckedDirectoryIds.add(node.Id);
    }

    return { totalFiles, selectedFiles, hasSelection };
  };

  nodes.forEach(walk);

  checkedDirectoryIds.forEach((id) => halfCheckedDirectoryIds.delete(id));

  return {
    checkedDirectoryIds: Array.from(checkedDirectoryIds),
    halfCheckedDirectoryIds: Array.from(halfCheckedDirectoryIds),
  };
};

const CreateTaskView: React.FC<CreateTaskViewProps> = ({
  onBack,
  projectId,
  projectName,
  onCreated,
}) => {
  const [form] = Form.useForm();
  const [showFileModal, setShowFileModal] = useState(false);
  const [selectedItems, setSelectedItems] = useState<SelectedItemsState>(createEmptySelectedItems());
  const effectiveSelectedItems = useMemo(
    () => getEffectiveSelectedItems(selectedItems),
    [selectedItems]
  );

  const { run: submitTask, loading: submitting } = useRequest(
    (values: any) => {
      const effectiveDirectoryIds = getEffectiveDirectoryIds(selectedItems);
      const payload: TaskSubmitRequest = {
        Name: values.Name,
        Description: values.Description,
        AlgorithmType: "object-detection",
        SelectedFiles: Array.from<string>(selectedItems.files.keys()).map((id) => ({ FileId: id })),
        DirectoryIds: effectiveDirectoryIds,
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

  const totalSelectedCount = effectiveSelectedItems.length;

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", width: "100%", height: "100%", display: "flex", flexDirection: "column" }}>
      <div style={{ flexShrink: 0, marginBottom: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={onBack} type="text">返回</Button>
        <Title level={2} style={{ marginTop: 16 }}>创建新任务</Title>
        <Text type="secondary">配置检测任务的文件和参数</Text>
      </div>

      <div style={{ flex: 1, overflowY: "auto", minHeight: 0, paddingRight: 8 }}>
        <Card title="任务设置" style={{ marginBottom: 16 }}>
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
                <Text strong>已选择的内容</Text>
                <Text type="secondary">共 {totalSelectedCount} 项</Text>
              </div>
              <List
                bordered
                dataSource={effectiveSelectedItems}
                renderItem={(item) => (
                  <List.Item extra={
                    <Button type="text" icon={<DeleteOutlined />} onClick={() => {
                      const newItems: SelectedItemsState = {
                        files: new Map(selectedItems.files),
                        directories: new Map(selectedItems.directories),
                      };
                      if (item.type === 'file') newItems.files.delete(item.id);
                      else newItems.directories.delete(item.id);
                      setSelectedItems(newItems);
                    }} />
                  }>
                    <Space>
                      {item.type === 'directory' ? (
                        <FolderOutlined style={{ color: '#faad14' }} />
                      ) : (
                        <FileImageOutlined style={{ color: '#8c8c8c' }} />
                      )}
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
      </div>

      <div style={{ flexShrink: 0, display: "flex", justifyContent: "flex-end", gap: 12, paddingTop: 16, paddingBottom: 16 }}>
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
        projectId={projectId}
        projectName={projectName}
        initialSelected={selectedItems}
      />
    </div>
  );
};

// --- 文件选择弹窗组件 ---
interface FileSelectionModalProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: (items: SelectedItemsState) => void;
  projectId: string;
  projectName: string;
  initialSelected: SelectedItemsState;
}

const FileSelectionModal: React.FC<FileSelectionModalProps> = ({
  open,
  onCancel,
  onConfirm,
  projectId,
  projectName,
  initialSelected,
}) => {
  const [selectedItems, setSelectedItems] = useState<SelectedItemsState>(initialSelected);

  useEffect(() => {
    if (!open) return;

    setSelectedItems({
      files: new Map(initialSelected.files),
      directories: new Map(initialSelected.directories),
    });
  }, [open, initialSelected, projectId]);

  // 2. 获取当前项目的文件树
  const { data: filesResp, loading: filesLoading, run: fetchFiles } = useRequest(
    (pid: string) => fileAPI.getFiles(pid),
    { manual: true }
  );

  useEffect(() => {
    if (open) {
      fetchFiles(projectId);
    }
  }, [open, projectId]);

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

  const directoryPathIdMap = useMemo(
    () => buildDirectoryPathIdMap(filesResp?.Data || []),
    [filesResp]
  );

  const directoryCheckState = useMemo(
    () => getDirectoryCheckState(filesResp?.Data || [], selectedItems),
    [filesResp, selectedItems]
  );

  const ancestorDirectoryIdsForFiles = useMemo(
    () => getAncestorDirectoryIdsForFiles(selectedItems.files, directoryPathIdMap),
    [selectedItems.files, directoryPathIdMap]
  );

  const treeCheckedKeys = useMemo(() => ({
    checked: Array.from(new Set([
      ...Array.from<string>(selectedItems.files.keys()),
      ...Array.from<string>(selectedItems.directories.keys()),
      ...directoryCheckState.checkedDirectoryIds,
      ...ancestorDirectoryIdsForFiles,
    ])),
    halfChecked: directoryCheckState.halfCheckedDirectoryIds.filter(
      (id) => !ancestorDirectoryIdsForFiles.includes(id)
    ),
  }), [
    selectedItems.files,
    selectedItems.directories,
    directoryCheckState,
    ancestorDirectoryIdsForFiles,
  ]);

  const handleCheck = (checkedKeys: any, info: any) => {
    const newSelected: SelectedItemsState = {
      files: new Map(selectedItems.files),
      directories: new Map(selectedItems.directories),
    };
    const node = info.node.data as FileTreeNode;

    if (info.checked) {
      if (node.Type === 'directory') {
        addDirectorySubtreeFileSelections(node, newSelected);
      } else {
        removeAncestorDirectorySelections(node.Path, newSelected);
        newSelected.files.set(node.Id, { name: node.Name, path: node.Path });
      }
    } else {
      if (node.Type === 'directory') {
        clearDirectorySubtreeSelections(node, newSelected);
      } else {
        removeAncestorDirectorySelections(node.Path, newSelected);
        newSelected.files.delete(node.Id);
      }
    }
    
    setSelectedItems(newSelected);
  };

  const totalCount = getEffectiveSelectedItems(selectedItems).length;

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
      <div style={{ height: 500, overflowY: "auto" }}>
        <div style={{ marginBottom: 12, padding: "8px 0", display: "flex", justifyContent: "space-between" }}>
          <Text strong>文件目录</Text>
          <Text type="secondary">{projectName}</Text>
        </div>
        {filesLoading ? (
          <div style={{ textAlign: "center", paddingTop: 100 }}><SyncOutlined spin /></div>
        ) : treeData.length > 0 ? (
          <Tree
            checkable
            checkStrictly={true}
            treeData={treeData}
            onCheck={handleCheck}
            checkedKeys={treeCheckedKeys}
            height={420}
            selectable={false}
          />
        ) : (
          <Empty description="该项目下暂无文件" style={{ marginTop: 100 }} />
        )}
      </div>
      <div style={{ marginTop: 16, borderTop: "1px solid #f0f0f0", paddingTop: 16, display: "flex", alignItems: "center" }}>
        <InfoCircleOutlined style={{ color: "#1890ff", marginRight: 8 }} />
        <Text>已从当前项目中选择 <Text strong>{totalCount}</Text> 个资源</Text>
      </div>
    </Modal>
  );
};

export default TasksPage;
