import { useEffect, useMemo, useRef, useState } from "react";
import {
  Card,
  Typography,
  Space,
  Button,
  Breadcrumb,
  Table,
  Tag,
  Modal,
  Input,
  Divider,
  message,
  Alert,
  Radio,
  Tree,
  Checkbox,
} from "antd";
import {
  FolderOutlined,
  DatabaseOutlined,
  EyeOutlined,
  TagsOutlined,
  DeleteOutlined,
  PlusOutlined,
  ExclamationCircleOutlined,
  SaveOutlined,
  ExperimentOutlined,
  FolderOpenOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { trainingDataAPI } from "@/utils/api";

const { Title, Text } = Typography;

type DataSource = {
  id: string;
  name: string;
  path: string;
  fileCount: number;
  labeledCount: number;
  size: string;
  createdAt: string;
  color: string;
  usedByDatasets: string[];
  usedByExperiments: string[];
};

type Dataset = {
  id: string;
  name: string;
  type: "训练集" | "测试集";
  count: number;
  source: string;
  sourceIds: string[];
  createdAt: string;
  inUseExperiments: string[];
};

const datasetTypeColor: Record<Dataset["type"], string> = {
  训练集: "geekblue",
  测试集: "red",
};

const sourceColors = ["#dbe8ff", "#ffe6c7", "#d9f7e8", "#fff1b8", "#f0f5ff", "#fde3cf"];

export default function DataManagementPage({
  projectId,
  projectName,
}: {
  projectId: string;
  projectName: string;
}) {
  const [addSourceOpen, setAddSourceOpen] = useState(false);
  const [saveDatasetOpen, setSaveDatasetOpen] = useState(false);
  const [deleteSourceOpen, setDeleteSourceOpen] = useState(false);
  const [deleteSourceBlockedOpen, setDeleteSourceBlockedOpen] = useState(false);
  const [deleteDatasetOpen, setDeleteDatasetOpen] = useState(false);
  const [deleteDatasetBlockedOpen, setDeleteDatasetBlockedOpen] = useState(false);
  const [confirmSourceName, setConfirmSourceName] = useState("");
  const [selectedSource, setSelectedSource] = useState<DataSource | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [rawCount, setRawCount] = useState(0);
  const [labeledCount, setLabeledCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const [sourceName, setSourceName] = useState("");
  const [sourcePath, setSourcePath] = useState("");
  const [datasetName, setDatasetName] = useState("");
  const [datasetType, setDatasetType] = useState<"TRAIN" | "TEST">("TRAIN");
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes <= 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex += 1;
    }
    return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
  };

  const imageExtensions = ["jpg", "jpeg", "png", "bmp", "gif", "webp", "tif", "tiff"];

  const selectedStats = useMemo(() => {
    if (!selectedFiles.length) {
      return { totalCount: 0, totalBytes: 0, imageCount: 0 };
    }
    let totalBytes = 0;
    let imageCount = 0;
    selectedFiles.forEach((file) => {
      totalBytes += file.size || 0;
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (ext && imageExtensions.includes(ext)) {
        imageCount += 1;
      }
    });
    return { totalCount: selectedFiles.length, totalBytes, imageCount };
  }, [selectedFiles]);

  const fileTreeData = useMemo(() => {
    if (!selectedFiles.length) return [];
    const root: any = { key: "root", title: "", children: [] as any[] };
    selectedFiles.forEach((file) => {
      const relative = (file as any).webkitRelativePath || file.name;
      const parts = relative.split("/").filter(Boolean);
      let current = root;
      let pathKey = "";
      parts.forEach((part, index) => {
        pathKey = pathKey ? `${pathKey}/${part}` : part;
        let child = current.children.find((item: any) => item.key === pathKey);
        if (!child) {
          child = { key: pathKey, title: part };
          if (index < parts.length - 1) {
            child.children = [];
          }
          current.children.push(child);
        }
        if (child.children) {
          current = child;
        }
      });
    });
    return root.children;
  }, [selectedFiles]);

  const refreshData = async () => {
    setLoading(true);
    try {
      const [summaryRes, sourcesRes, datasetsRes] = await Promise.all([
        trainingDataAPI.getSummary(projectId),
        trainingDataAPI.getDataSources(projectId),
        trainingDataAPI.getDatasets(projectId),
      ]);

      const summary = summaryRes.Data;
      setRawCount(summary?.RawCount ?? 0);
      setLabeledCount(summary?.LabeledCount ?? 0);

      const mappedSources: DataSource[] = (sourcesRes.Data || []).map((item, index) => ({
        id: item.Id,
        name: item.Name,
        path: item.Path,
        fileCount: item.FileCount ?? 0,
        labeledCount: item.LabeledCount ?? 0,
        size: formatBytes(item.SizeBytes ?? 0),
        createdAt: item.CreateTime || "",
        color: sourceColors[index % sourceColors.length],
        usedByDatasets: item.UsedByDatasets || [],
        usedByExperiments: item.UsedByExperiments || [],
      }));

      const mappedDatasets: Dataset[] = (datasetsRes.Data || []).map((item) => ({
        id: item.Id,
        name: item.Name,
        type: item.Type,
        count: item.Count ?? 0,
        source: item.Source || "-",
        sourceIds: item.SourceIds || [],
        createdAt: item.CreateTime || "",
        inUseExperiments: item.InUseExperiments || [],
      }));

      setDataSources(mappedSources);
      setDatasets(mappedDatasets);
    } catch (error) {
      message.error("加载数据管理信息失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) {
      refreshData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (!fileInputRef.current) return;
    const input = fileInputRef.current;
    input.setAttribute("webkitdirectory", "");
    input.setAttribute("directory", "");
    input.setAttribute("multiple", "");
  }, []);

  const handleSelectFolder = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) {
      message.warning("未选择任何文件");
      return;
    }
    const files = Array.from(fileList);
    setSelectedFiles(files);
    const firstFile: any = files[0];
    const relativePath = firstFile.webkitRelativePath || firstFile.name;
    const folderName = relativePath.split("/")[0];
    if (folderName && !sourceName.trim()) {
      setSourceName(folderName);
    }
    setSourcePath(folderName || "");
  };

  const handleDeleteSource = (source: DataSource) => {
    setSelectedSource(source);
    setConfirmSourceName("");
    if (source.usedByDatasets.length > 1 || source.usedByExperiments.length) {
      setDeleteSourceBlockedOpen(true);
      return;
    }
    setDeleteSourceOpen(true);
  };

  const handleDeleteDataset = (dataset: Dataset) => {
    setSelectedDataset(dataset);
    if (dataset.inUseExperiments.length) {
      setDeleteDatasetBlockedOpen(true);
      return;
    }
    setDeleteDatasetOpen(true);
  };

  const handleCreateSource = async () => {
    const trimmedName = sourceName.trim();
    try {
      if (!trimmedName) {
        message.error("请输入数据源名称");
        return;
      }
      if (selectedFiles.length === 0) {
        message.error("请选择需要上传的文件夹");
        return;
      }

      await trainingDataAPI.uploadDataSource(projectId, trimmedName, selectedFiles);

      message.success("数据源已添加");
      setAddSourceOpen(false);
      setSourceName("");
      setSourcePath("");
      setSelectedFiles([]);
      await refreshData();
    } catch (error) {
      // 错误提示由 API 层统一处理
    }
  };

  const handleCreateDataset = async () => {
    const trimmedName = datasetName.trim();
    if (!trimmedName) {
      message.error("请输入数据集名称");
      return;
    }
    if (selectedSourceIds.length === 0) {
      message.error("请选择至少一个数据源");
      return;
    }

    try {
      await trainingDataAPI.createDataset(projectId, {
        Name: trimmedName,
        Type: datasetType,
        SourceIds: selectedSourceIds,
      });

      message.success("数据集已保存");
      setSaveDatasetOpen(false);
      setDatasetName("");
      setDatasetType("TRAIN");
      setSelectedSourceIds([]);
      await refreshData();
    } catch (error) {
      // 错误提示由 API 层统一处理
    }
  };

  const handleConfirmDeleteSource = async () => {
    if (!selectedSource) {
      return;
    }
    if (confirmSourceName !== selectedSource.name) {
      message.error("输入的数据源名称不匹配");
      return;
    }
    try {
      await trainingDataAPI.deleteDataSource(projectId, selectedSource.id);
      message.success("数据源已删除");
      setDeleteSourceOpen(false);
      setSelectedSource(null);
      setConfirmSourceName("");
      await refreshData();
    } catch (error) {
      // 错误提示由 API 层统一处理
    }
  };

  const handleConfirmDeleteDataset = async () => {
    if (!selectedDataset) {
      return;
    }
    try {
      await trainingDataAPI.deleteDataset(projectId, selectedDataset.id);
      message.success("数据集已删除");
      setDeleteDatasetOpen(false);
      setSelectedDataset(null);
      await refreshData();
    } catch (error) {
      // 错误提示由 API 层统一处理
    }
  };

  const dataSourceColumns = [
    {
      title: "数据源名称",
      dataIndex: "name",
      key: "name",
      render: (_: string, record: DataSource) => (
        <Space>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: record.color,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <FolderOutlined />
          </div>
          <div>
            <Text strong>{record.name}</Text>
            <div style={{ color: "#8c8c8c", fontSize: 12 }}>{record.path}</div>
          </div>
        </Space>
      ),
    },
    {
      title: "文件数",
      dataIndex: "fileCount",
      key: "fileCount",
    },
    {
      title: "大小",
      dataIndex: "size",
      key: "size",
    },
    {
      title: "创建时间",
      dataIndex: "createdAt",
      key: "createdAt",
    },
    {
      title: "操作",
      key: "actions",
      align: "right" as const,
      render: (_: any, record: DataSource) => (
        <Space size={8}>
          <Button size="small" icon={<EyeOutlined />} onClick={() => message.info("查看数据源")}>
            查看
          </Button>
          <Button size="small" icon={<TagsOutlined />} onClick={() => message.info("进入标注")}>
            标注
          </Button>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteSource(record)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  const datasetColumns = [
    {
      title: "数据集名称",
      dataIndex: "name",
      key: "name",
      render: (_: string, record: Dataset) => (
        <Space direction="vertical" size={2}>
          <Space>
            <Text strong>{record.name}</Text>
            <Tag color={datasetTypeColor[record.type]}>{record.type}</Tag>
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.type}
          </Text>
        </Space>
      ),
    },
    {
      title: "数据量",
      dataIndex: "count",
      key: "count",
    },
    {
      title: "数据源",
      dataIndex: "source",
      key: "source",
    },
    {
      title: "创建时间",
      dataIndex: "createdAt",
      key: "createdAt",
    },
    {
      title: "操作",
      key: "actions",
      align: "right" as const,
      render: (_: any, record: Dataset) => (
        <Space size={8}>
          <Button size="small" icon={<EyeOutlined />} onClick={() => message.info("查看数据集")}>
            查看
          </Button>
          <Button size="small" icon={<TagsOutlined />} onClick={() => message.info("进入标注")}>
            标注
          </Button>
          <Button size="small" icon={<SaveOutlined />} onClick={() => message.info("使用数据集")}>
            使用
          </Button>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteDataset(record)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: "24px", maxWidth: 1200, margin: "0 auto" }}>
      <Breadcrumb
        items={[
          { title: "项目管理" },
          { title: projectName },
          { title: "数据管理" },
        ]}
        style={{ marginBottom: 16 }}
      />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <Title level={2} style={{ margin: "0 0 4px 0" }}>
            数据管理
          </Title>
          <Text type="secondary">管理项目中的训练数据源和数据集</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddSourceOpen(true)}>
          添加数据
        </Button>
      </div>

      <Space size={16} style={{ marginBottom: 24, width: "100%" }} wrap>
        <Card style={{ flex: 1, minWidth: 240 }}>
          <Space align="center">
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 12,
                background: "#e8f1ff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <DatabaseOutlined style={{ color: "#1677ff" }} />
            </div>
            <div>
              <Text type="secondary">原始数据</Text>
              <div style={{ fontSize: 22, fontWeight: 600 }}>{rawCount.toLocaleString()}</div>
            </div>
          </Space>
        </Card>
        <Card style={{ flex: 1, minWidth: 240 }}>
          <Space align="center">
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 12,
                background: "#e6f7f1",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <TagsOutlined style={{ color: "#2ecc71" }} />
            </div>
            <div>
              <Text type="secondary">已标注数据</Text>
              <div style={{ fontSize: 22, fontWeight: 600 }}>{labeledCount.toLocaleString()}</div>
            </div>
          </Space>
        </Card>
        <Card style={{ flex: 1, minWidth: 240 }}>
          <Space align="center">
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 12,
                background: "#fff2e8",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <DatabaseOutlined style={{ color: "#fa8c16" }} />
            </div>
            <div>
              <Text type="secondary">数据集</Text>
              <div style={{ fontSize: 22, fontWeight: 600 }}>{datasets.length}</div>
            </div>
          </Space>
        </Card>
      </Space>

      <Card
        title={
          <Space>
            <FolderOutlined />
            <span>数据源管理</span>
          </Space>
        }
        variant="borderless"
        style={{ borderRadius: 12, marginBottom: 24 }}
      >
        <Table
          columns={dataSourceColumns}
          dataSource={dataSources}
          rowKey="id"
          pagination={false}
          loading={loading}
        />
      </Card>

      <Card
        title={
          <Space>
            <DatabaseOutlined />
            <span>数据集管理</span>
          </Space>
        }
        extra={
          <Button icon={<SaveOutlined />} onClick={() => setSaveDatasetOpen(true)}>
            保存为数据集
          </Button>
        }
        variant="borderless"
        style={{ borderRadius: 12 }}
      >
        <Table
          columns={datasetColumns}
          dataSource={datasets}
          rowKey="id"
          pagination={false}
          loading={loading}
        />
      </Card>

      <Modal
        title={
          <Space>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "rgba(24, 144, 255, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#1677ff",
              }}
            >
              <FolderOpenOutlined />
            </div>
            <div>
              <div style={{ fontWeight: 600 }}>添加数据源</div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                选择本地文件夹或配置远程存储
              </Text>
            </div>
          </Space>
        }
        open={addSourceOpen}
        onCancel={() => {
          setAddSourceOpen(false);
          setSourceName("");
          setSourcePath("");
          setSelectedFiles([]);
        }}
        onOk={handleCreateSource}
        okText="添加数据源"
        cancelText="取消"
        width={860}
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <div>
            <Space size={6}>
              <Text strong>数据源名称</Text>
              <Tag color="red">必填</Tag>
            </Space>
            <Input
              placeholder="例如: images_batch_004"
              style={{ marginTop: 8 }}
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              使用有意义的名称，便于后续识别
            </Text>
          </div>
          <div
            style={{
              border: "1px solid #f0f0f0",
              borderRadius: 12,
              padding: 16,
              background: "#fafcff",
            }}
          >
            <Space align="center">
              <FolderOutlined style={{ color: "#1677ff" }} />
              <Text strong>本地路径配置</Text>
            </Space>
            <div style={{ marginTop: 12 }}>
              <Space size={6}>
                <Text>文件夹路径</Text>
                <Tag color="red">必填</Tag>
              </Space>
              <Space style={{ marginTop: 8, width: "100%" }} align="start">
                <Input
                  placeholder="例如: data/train"
                  style={{ width: 520 }}
                  value={sourcePath}
                  onChange={(e) => setSourcePath(e.target.value)}
                />
                <Button
                  type="primary"
                  onClick={() => {
                    if (!fileInputRef.current) return;
                    fileInputRef.current.value = "";
                    fileInputRef.current.click();
                  }}
                  icon={<FolderOpenOutlined />}
                >
                  浏览
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  style={{ display: "none" }}
                  onChange={(e) => handleSelectFolder(e.target.files)}
                />
              </Space>
            </div>
            <Divider style={{ margin: "16px 0" }} />
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <Text strong>选择文件夹</Text>
              <Button icon={<ReloadOutlined />} type="text">
                刷新
              </Button>
            </div>
            <Card style={{ marginTop: 8 }}>
              {fileTreeData.length ? (
                <div style={{ maxHeight: 220, overflowY: "auto" }}>
                  <Tree treeData={fileTreeData} defaultExpandAll />
                </div>
              ) : (
                <div style={{ padding: "12px 0", color: "#8c8c8c" }}>
                  请选择本地文件夹后显示目录结构
                </div>
              )}
            </Card>
            <div
              style={{
                marginTop: 16,
                background: "#f0f5ff",
                borderRadius: 8,
                padding: 12,
              }}
            >
              <Space direction="vertical" size={4} style={{ width: "100%" }}>
                <Space>
                  <Text type="secondary">已选择路径：</Text>
                  <Text>{sourcePath || "-"}</Text>
                </Space>
                <Divider style={{ margin: "8px 0" }} />
                <Space size={24}>
                  <div>
                    <Text type="secondary">文件总数</Text>
                    <div style={{ fontSize: 16, fontWeight: 600 }}>{selectedStats.totalCount}</div>
                  </div>
                  <div>
                    <Text type="secondary">总大小</Text>
                    <div style={{ fontSize: 16, fontWeight: 600 }}>
                      {selectedStats.totalBytes
                        ? `${Math.round((selectedStats.totalBytes / 1024 / 1024) * 10) / 10} MB`
                        : "0 MB"}
                    </div>
                  </div>
                  <div>
                    <Text type="secondary">图片文件</Text>
                    <div style={{ fontSize: 16, fontWeight: 600 }}>{selectedStats.imageCount}</div>
                  </div>
                </Space>
              </Space>
            </div>
          </div>
        </Space>
      </Modal>

      <Modal
        title="保存为数据集"
        open={saveDatasetOpen}
        onCancel={() => setSaveDatasetOpen(false)}
        onOk={handleCreateDataset}
        okText="保存数据集"
        cancelText="取消"
        width={720}
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <div>
            <Text strong>数据集名称 *</Text>
            <Input
              placeholder="filtered_dataset_001"
              style={{ marginTop: 8 }}
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
            />
          </div>
          <div>
            <Text strong>数据集类型 *</Text>
            <Radio.Group
              value={datasetType}
              style={{ marginTop: 8 }}
              onChange={(e) => setDatasetType(e.target.value)}
            >
              <Space direction="vertical" size={12}>
                <Radio value="TRAIN">
                  <Space direction="vertical" size={0}>
                    <Text strong>训练集</Text>
                    <Text type="secondary">用于模型训练，系统默认划分10%作为验证集</Text>
                  </Space>
                </Radio>
                <Radio value="TEST">
                  <Space direction="vertical" size={0}>
                    <Text strong>测试集</Text>
                    <Text type="secondary">用于模型评估，生成测试集报告</Text>
                  </Space>
                </Radio>
              </Space>
            </Radio.Group>
          </div>
          <div>
            <Text strong>数据集描述（可选）</Text>
            <Input.TextArea rows={3} placeholder="添加数据集的用途说明..." style={{ marginTop: 8 }} />
          </div>
          <Card>
            <Text strong>数据源绑定</Text>
            <div style={{ marginTop: 12 }}>
              <Checkbox.Group
                style={{ width: "100%" }}
                value={selectedSourceIds}
                onChange={(values) => setSelectedSourceIds(values as string[])}
              >
                <Space direction="vertical" style={{ width: "100%" }}>
                  {dataSources.map((source) => (
                    <Checkbox key={source.id} value={source.id}>
                      <Space>
                        <div
                          style={{
                            width: 36,
                            height: 36,
                            borderRadius: 8,
                            background: source.color,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          <FolderOutlined />
                        </div>
                        <div>
                          <Text strong>{source.name}</Text>
                          <div style={{ color: "#8c8c8c", fontSize: 12 }}>
                            {source.path} · {source.fileCount} 张图片
                          </div>
                        </div>
                      </Space>
                    </Checkbox>
                  ))}
                </Space>
              </Checkbox.Group>
            </div>
          </Card>
          <Alert
            type="info"
            showIcon
            message="保存后可在数据集列表中查看和使用"
          />
        </Space>
      </Modal>

      <Modal
        title="确认删除数据源"
        open={deleteSourceOpen}
        onCancel={() => setDeleteSourceOpen(false)}
        onOk={handleConfirmDeleteSource}
        okText="确认删除"
        okButtonProps={{ danger: true }}
        cancelText="取消"
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Alert
            type="error"
            showIcon
            message="删除影响说明"
            description={
              <div>
                <div>• 永久删除所有原始图片数据</div>
                <div>• 删除所有相关的标注信息</div>
                <div>• 清除相关的元数据信息</div>
              </div>
            }
          />
          <Text>请输入数据源名称以确认删除：</Text>
          <Input
            placeholder={selectedSource?.name}
            value={confirmSourceName}
            onChange={(e) => setConfirmSourceName(e.target.value)}
          />
          <Text type="danger">此操作不可恢复，请确认已备份重要数据</Text>
        </Space>
      </Modal>

      <Modal
        title="无法删除数据源"
        open={deleteSourceBlockedOpen}
        onCancel={() => setDeleteSourceBlockedOpen(false)}
        footer={[
          <Button key="close" type="primary" onClick={() => setDeleteSourceBlockedOpen(false)}>
            我知道了
          </Button>,
        ]}
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Alert
            type="error"
            showIcon
            message="该数据源正在被使用"
            description={
              <div>
                <Text>请先删除或迁移相关数据集后再操作</Text>
              </div>
            }
          />
          <div>
            <Text strong>相关数据集</Text>
            <div style={{ marginTop: 8 }}>
              {(selectedSource?.usedByDatasets || []).map((name) => (
                <Card key={name} size="small" style={{ marginBottom: 8 }}>
                  <Space>
                    <DatabaseOutlined />
                    <Text>{name}</Text>
                    <Tag color="green">使用中</Tag>
                  </Space>
                </Card>
              ))}
            </div>
          </div>
          <Card style={{ background: "#fff7e6" }}>
            <Space direction="vertical">
              <Text strong>解决建议</Text>
              <Text>1. 先删除或迁移依赖此数据源的数据集</Text>
              <Text>2. 或编辑数据集，更换为其他数据源</Text>
            </Space>
          </Card>
        </Space>
      </Modal>

      <Modal
        title="确认删除数据集"
        open={deleteDatasetOpen}
        onCancel={() => setDeleteDatasetOpen(false)}
        onOk={handleConfirmDeleteDataset}
        okText="确认删除"
        okButtonProps={{ danger: true }}
        cancelText="取消"
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Card>
            <Space>
              <DatabaseOutlined />
              <div>
                <Text strong>{selectedDataset?.name}</Text>
                <div style={{ color: "#8c8c8c", fontSize: 12 }}>
                  {selectedDataset?.type} · {selectedDataset?.count} 张
                </div>
              </div>
            </Space>
          </Card>
          <Alert
            type="info"
            showIcon
            message="删除影响说明"
            description={
              <div>
                <div>• 仅删除数据集配置和筛选条件</div>
                <div>• 原始数据不会受影响</div>
                <div>• 训练记录会保留，但数据集引用失效</div>
              </div>
            }
          />
          <Alert
            type="warning"
            showIcon
            message="删除后无法恢复数据集配置"
          />
        </Space>
      </Modal>

      <Modal
        title="无法删除数据集"
        open={deleteDatasetBlockedOpen}
        onCancel={() => setDeleteDatasetBlockedOpen(false)}
        footer={[
          <Button key="close" type="primary" onClick={() => setDeleteDatasetBlockedOpen(false)}>
            我知道了
          </Button>,
        ]}
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Alert
            type="error"
            showIcon
            message="该数据集正在被训练任务使用"
          />
          <div>
            {(selectedDataset?.inUseExperiments || []).map((expName) => (
              <Card key={expName} size="small" style={{ marginBottom: 8 }}>
                <Space>
                  <ExperimentOutlined />
                  <Text>{expName}</Text>
                  <Tag color="orange">运行中</Tag>
                </Space>
              </Card>
            ))}
          </div>
          <Card style={{ background: "#fff7e6" }}>
            <Space direction="vertical">
              <Text strong>解决建议</Text>
              <Text>1. 等待训练任务完成后再删除</Text>
              <Text>2. 或停止相关训练任务后删除</Text>
              <Text>3. 在实验管理中更换数据集后删除</Text>
            </Space>
          </Card>
        </Space>
      </Modal>
    </div>
  );
}
