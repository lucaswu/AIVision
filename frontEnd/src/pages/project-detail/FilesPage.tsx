import React, { useState, useEffect, useMemo } from "react";
import {
  Button,
  Table,
  Tree,
  Space,
  Typography,
  Card,
  Row,
  Col,
  Modal,
  message,
  Upload,
  Tag,
  Input,
  Select,
  Image,
  Breadcrumb,
  List,
} from "antd";
import {
  UploadOutlined,
  FolderOutlined,
  FileImageOutlined,
  DownloadOutlined,
  DeleteOutlined,
  PlusOutlined,
  EyeOutlined,
  FolderOpenOutlined,
  InboxOutlined,
} from "@ant-design/icons";
import type {
  TableColumnsType,
  TreeDataNode,
  UploadProps,
  UploadFile,
} from "antd";
import { useParams } from "react-router-dom";
import { useRequest } from "ahooks";
import { fileAPI, directoryAPI, getUserId } from "../../utils/api";
import { FileTreeNode } from "../../utils/data";
import "./FilesPage.css";
import { filePreviewPath } from "@/utils/constans";

const { Title, Text } = Typography;
const { Dragger } = Upload;

interface FilesPageProps {
  projectId: string;
  projectName?: string;
  permission?: string;
}

const FilesPage: React.FC<FilesPageProps> = ({
  projectId,
  projectName = "项目",
  permission = "READ_ONLY",
}) => {
  const isReadOnly = permission === "READ_ONLY";
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [selectedPath, setSelectedPath] = useState<string>("");
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [uploadCategory, setUploadCategory] = useState<string>("PCB图像");
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewImage, setPreviewImage] = useState("");
  // 新增状态管理上传文件列表
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);

  // 获取文件树数据
  const {
    data: filesResponse,
    loading,
    refresh,
  } = useRequest(
    () => {
      return fileAPI.getFiles(projectId);
    },
    {
      refreshDeps: [projectId],
    }
  );

  const allDirectories = filesResponse?.Data || [];

  // 默认选择第一个目录
  useEffect(() => {
    if (allDirectories.length > 0 && !selectedPath) {
      const firstDirectory = allDirectories[0];
      setSelectedPath(firstDirectory.Path);
    }
  }, [allDirectories, selectedPath]);

  // 递归转换为Ant Design树形数据格式（只显示第一层目录）
  const convertToTreeData = (nodes: FileTreeNode[]): TreeDataNode[] => {
    return nodes.map((node) => ({
      title: (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "4px 8px",
            borderRadius: "6px",
            transition: "all 0.2s",
            width: "100%",
          }}
        >
          <Space size={8}>
            <FolderOutlined style={{ color: "#faad14" }} />
            <span style={{ fontSize: "14px", fontWeight: 500 }}>
              {node.Name}
            </span>
          </Space>
        </div>
      ),
      key: node.Id,
      icon: null,
      isLeaf: true, // 第一层目录都是叶子节点，不允许展开
      className: "custom-tree-node",
      children: undefined, // 不显示子节点
      data: node,
    }));
  };

  const treeData = useMemo(() => {
    return convertToTreeData(allDirectories);
  }, [allDirectories]);

  // 获取当前选中路径下的文件列表
  const currentFiles = useMemo(() => {
    if (!selectedPath) {
      return [];
    }

    // 根据选中的路径找到对应的文件
    const selectedDirectory = allDirectories.find(
      (node) => node.Type === "directory" && node.Path === selectedPath
    );

    if (selectedDirectory && selectedDirectory.Children) {
      return selectedDirectory.Children;
    }

    return [];
  }, [allDirectories, selectedPath]);

  // 前端分页
  const paginatedFiles = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    return currentFiles.slice(start, end);
  }, [currentFiles, currentPage, pageSize]);

  // 处理树节点选择
  const handleTreeSelect = (selectedKeys: React.Key[], info: any) => {
    if (selectedKeys.length > 0) {
      const nodeData = info.node?.data;
      if (nodeData && nodeData.Type === "directory") {
        setSelectedPath(nodeData.Path);
        setCurrentPage(1);
      }
    }
  };

  const handlePaginationChange = (page: number, size: number) => {
    setCurrentPage(page);
    setPageSize(size);
  };

  const handleShowSizeChange = (current: number, size: number) => {
    setCurrentPage(1);
    setPageSize(size);
  };

  const handlePreview = (file) => {
    setPreviewImage(file.Id);
    setPreviewVisible(true);
  };

  const handleDelete = async (fileId: string) => {
    Modal.confirm({
      title: "确认删除",
      content: "确定要删除这个文件吗？",
      async onOk() {
        try {
          await fileAPI.deleteFile(fileId, projectId);
          message.success("文件删除成功");
          refresh();
        } catch (error) {
          // 错误已在API层处理
        }
      },
    });
  };

  const handleCreateDirectory = () => {
    let directoryName = "";

    Modal.confirm({
      title: "创建目录",
      content: (
        <div>
          <p>请输入目录名称：</p>
          <Input
            placeholder="请输入目录名称"
            onChange={(e) => {
              directoryName = e.target.value;
            }}
            onPressEnter={() => {
              // 可以通过回车确认
            }}
          />
        </div>
      ),
      async onOk() {
        if (!directoryName.trim()) {
          message.error("目录名称不能为空");
          return;
        }

        try {
          await directoryAPI.createDirectory(projectId, {
            Name: directoryName.trim(),
          });
          message.success("目录创建成功");
          refresh();
        } catch (error) {
          // 错误已在API层处理
        }
      },
    });
  };

  const getSelectedDirectoryId = (path: string): string | undefined => {
    const selectedDirectory = allDirectories.find((dir) => dir.Path === path);
    return selectedDirectory?.Id;
  };

  // 文件上传处理 - 修改为确认后上传
  const handleFileUpload = async () => {
    const selectedDirectoryId = getSelectedDirectoryId(selectedPath);
    if (!selectedDirectoryId) {
      message.error("请先选择一个目录");
      return;
    }

    if (fileList.length === 0) {
      message.error("请选择要上传的文件");
      return;
    }

    setUploading(true);
    try {
      // 创建FileList对象
      const dataTransfer = new DataTransfer();
      fileList.forEach((file) => {
        if (file.originFileObj) {
          dataTransfer.items.add(file.originFileObj);
        }
      });
      const files = dataTransfer.files;

      const result = await fileAPI.uploadFiles(
        projectId,
        selectedDirectoryId,
        files
      );

      message.success(`成功上传 ${result.Data.SuccessCount} 个文件`);
      if (result.Data.FailedCount > 0) {
        message.warning(`${result.Data.FailedCount} 个文件上传失败`);
      }

      // 重置状态
      setFileList([]);
      setUploadModalVisible(false);
      refresh();
    } catch (error) {
      // 错误已在API层处理
    } finally {
      setUploading(false);
    }
  };

  // 取消上传
  const handleCancelUpload = () => {
    setFileList([]);
    setUploadModalVisible(false);
  };

  // 上传配置
  const uploadProps: UploadProps = {
    name: "File",
    multiple: true,
    fileList: fileList,
    onChange: ({ fileList: newFileList }) => {
      setFileList(newFileList);
    },
    beforeUpload: () => {
      return false; // 阻止自动上传
    },
    onRemove: (file) => {
      const index = fileList.indexOf(file);
      const newFileList = fileList.slice();
      newFileList.splice(index, 1);
      setFileList(newFileList);
    },
  };

  const columns: TableColumnsType<(typeof allDirectories)[0]> = [
    {
      title: "文件名",
      dataIndex: "Name",
      key: "Name",
      width: 200,
      render: (text, record) => (
        <Space>
          <FileImageOutlined style={{ color: "#1890ff" }} />
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: "类型",
      dataIndex: "FileType",
      key: "FileType",
      width: 100,
    },
    {
      title: "大小",
      dataIndex: "Size",
      key: "Size",
      width: 120,
      render: (size: number | string) => {
        if (!size) return "-";
        const sizeNum = typeof size === "string" ? parseInt(size) : size;
        const units = ["B", "KB", "MB", "GB"];
        let index = 0;
        let value = sizeNum;
        while (value >= 1024 && index < units.length - 1) {
          value /= 1024;
          index++;
        }
        return `${value.toFixed(1)} ${units[index]}`;
      },
    },
    {
      title: "上传时间",
      dataIndex: "UploadDate",
      key: "UploadDate",
      width: 180,
      render: (time: string) => {
        return time ? new Date(time).toLocaleString("zh-CN") : "-";
      },
    },
    {
      title: "操作",
      key: "action",
      // fixed: "right",
      width: 200,
      render: (_: any, record) => (
        <Space size="small">
          <Button
            size="small"
            type="text"
            icon={<EyeOutlined />}
            onClick={() => handlePreview(record)}
          >
            预览
          </Button>
          <Button
            size="small"
            type="text"
            icon={<DownloadOutlined />}
            onClick={() => {
              const downloadUrl = `${filePreviewPath}?FileId=${record.Id}&ProjectId=${projectId}&UseId=${getUserId()}`;

              // 创建一个隐藏的a标签来触发下载
              const link = document.createElement("a");
              link.href = downloadUrl;
              link.download = record.Name; // 使用原始文件名作为下载文件名
              link.style.display = "none";

              // 添加到DOM，点击然后移除
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);

              message.success(`正在下载 ${record.Name}`);
            }}
          >
            下载
          </Button>
          <Button
            size="small"
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.Id)}
            disabled={isReadOnly}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  const selectedKeys = useMemo(() => {
    const dirId = getSelectedDirectoryId(selectedPath);
    return dirId ? [dirId] : [];
  }, [selectedPath, allDirectories]);

  const breadcrumbItems = [
    { title: "项目管理" },
    { title: projectName },
    { title: "文件管理" },
  ];

  return (
    <div style={{ height: "100%" }}>
      <Breadcrumb items={breadcrumbItems} style={{ marginBottom: "24px" }} />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "24px",
        }}
      >
        <Title level={2} style={{ margin: 0 }}>
          文件管理
        </Title>
        <Space>
          {!isReadOnly && (
            <>
              <Button icon={<PlusOutlined />} onClick={handleCreateDirectory}>
                新建目录
              </Button>
              <Button
                type="primary"
                icon={<UploadOutlined />}
                onClick={() => setUploadModalVisible(true)}
              >
                上传文件
              </Button>
            </>
          )}
        </Space>
      </div>

      <Row gutter={16} style={{ height: "calc(100vh - 200px)" }}>
        <Col span={6}>
          <Card
            title={
              <div style={{ display: "flex", alignItems: "center" }}>
                <FolderOutlined style={{ marginRight: 8, color: "#1890ff" }} />
                <span>目录结构</span>
              </div>
            }
            style={{
              height: "100%",
              borderRadius: "8px",
              boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
            }}
            styles={{ body: { padding: "16px 0" } }}
            loading={loading}
          >
            <Tree
              showIcon={false}
              showLine={false}
              switcherIcon={false}
              treeData={treeData}
              onSelect={handleTreeSelect}
              selectedKeys={selectedKeys}
              className="custom-file-tree"
            />
          </Card>
        </Col>
        <Col span={18}>
          <Card
            title={
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <Space direction="vertical" size={4}>
                  <Space>
                    <FileImageOutlined style={{ color: "#1890ff" }} />
                    <span>文件列表</span>
                    <Tag color="processing">{currentFiles.length} 个文件</Tag>
                  </Space>
                </Space>
              </div>
            }
            style={{
              height: "100%",
              borderRadius: "8px",
              boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
            }}
          >
            <Table
              columns={columns}
              dataSource={paginatedFiles}
              loading={loading}
              rowKey="Id"
              // scroll={{ y: "calc(100vh - 360px)", x: 800 }}
              pagination={{
                pageSize: pageSize,
                current: currentPage,
                total: currentFiles.length,
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total, range) =>
                  `第 ${range?.[0]}-${range?.[1]} 条/共 ${total} 条`,
                pageSizeOptions: ["10", "20", "50", "100"],
                onChange: handlePaginationChange,
                onShowSizeChange: handleShowSizeChange,
              }}
            />
          </Card>
        </Col>
      </Row>

      {/* 上传文件弹窗 */}
      <Modal
        title="上传文件"
        open={uploadModalVisible}
        onCancel={handleCancelUpload}
        onOk={handleFileUpload}
        okText="确认上传"
        cancelText="取消"
        confirmLoading={uploading}
        width={600}
        okButtonProps={{
          disabled: fileList.length === 0,
        }}
      >
        <div style={{ padding: "20px 0" }}>
          <div style={{ marginBottom: 16 }}>
            <Text strong>目标目录：</Text>
            <Select
              value={selectedPath}
              onChange={setSelectedPath}
              style={{ width: "100%", marginTop: 8 }}
              placeholder="请选择目标目录"
            >
              {allDirectories.map((dir) => (
                <Select.Option key={dir.Id} value={dir.Path}>
                  {dir.Name}
                </Select.Option>
              ))}
            </Select>
          </div>

          <div style={{ marginBottom: 16 }}>
            <Text strong>选择文件：</Text>
            <div style={{ marginTop: 8 }}>
              <Dragger {...uploadProps}>
                <p className="ant-upload-drag-icon">
                  <InboxOutlined
                    style={{ fontSize: "48px", color: "#1890ff" }}
                  />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到此区域</p>
                <p className="ant-upload-hint">支持批量上传，仅支持图片格式</p>
              </Dragger>
            </div>
          </div>

          {fileList.length > 0 && (
            <div>
              <Text strong>待上传文件列表：</Text>
              <List
                size="small"
                dataSource={fileList}
                style={{ marginTop: 8, maxHeight: 200, overflow: "auto" }}
                renderItem={(file) => (
                  <List.Item
                    actions={[
                      <Button
                        type="link"
                        size="small"
                        onClick={() => uploadProps.onRemove?.(file)}
                      >
                        移除
                      </Button>,
                    ]}
                  >
                    <List.Item.Meta
                      avatar={
                        <FileImageOutlined style={{ color: "#1890ff" }} />
                      }
                      title={file.name}
                      description={`大小: ${(
                        (file.size || 0) /
                        1024 /
                        1024
                      ).toFixed(2)} MB`}
                    />
                  </List.Item>
                )}
              />
            </div>
          )}
        </div>
      </Modal>

      {/* 图片预览弹窗 */}
      <Modal
        open={previewVisible}
        title="图片预览"
        footer={null}
        onCancel={() => setPreviewVisible(false)}
        width={800}
        centered
      >
        <div style={{ textAlign: "center" }}>
          <Image
            src={`${filePreviewPath}?FileId=${previewImage}&ProjectId=${projectId}&UseId=${getUserId()}`}
            alt="预览图片"
            style={{ maxWidth: "100%", maxHeight: "60vh" }}
            preview={false}
          />
        </div>
      </Modal>
    </div>
  );
};

export default FilesPage;
