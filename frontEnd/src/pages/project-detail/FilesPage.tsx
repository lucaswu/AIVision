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
  FolderAddOutlined,
  CaretDownOutlined,
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
  const [uploadType, setUploadType] = useState<"file" | "directory">("file");
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

  // 递归计算目录下的总文件数
  const calculateTotalFiles = (node: FileTreeNode): number => {
    let count = node.Children?.filter((c) => c.Type === "file").length || 0;
    if (node.Children) {
      node.Children.forEach((child) => {
        if (child.Type === "directory") {
          count += calculateTotalFiles(child);
        }
      });
    }
    return count;
  };

  // 递归转换为Ant Design树形数据格式
  const convertToTreeData = (nodes: FileTreeNode[]): TreeDataNode[] => {
    return nodes
      .filter((node) => node.Type === "directory")
      .map((node) => {
        const hasDirectoryChildren = node.Children?.some(
          (c) => c.Type === "directory"
        );
        const totalFiles = calculateTotalFiles(node);
        return {
      title: (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            width: "100%",
          }}
        >
          <Space size={8}>
                <FolderOutlined style={{ color: "#1890ff" }} />
            <span style={{ fontSize: "14px", fontWeight: 500 }}>
              {node.Name}
            </span>
          </Space>
              {totalFiles > 0 && (
                <div
                  style={{
                    background: "#e6f7ff",
                    padding: "0 8px",
                    borderRadius: "10px",
                    fontSize: "11px",
                    color: "#1890ff",
                    fontWeight: 600,
                    lineHeight: "18px",
                    minWidth: "24px",
                    textAlign: "center",
                    border: "1px solid #91d5ff",
                  }}
                >
                  {totalFiles}
                </div>
              )}
        </div>
      ),
      key: node.Id,
          isLeaf: !hasDirectoryChildren,
          children: hasDirectoryChildren
            ? convertToTreeData(node.Children!)
            : undefined,
      data: node,
        };
      });
  };

  const treeData = useMemo(() => {
    return convertToTreeData(allDirectories);
  }, [allDirectories]);

  // 展平所有目录用于下拉选择
  const flattenedDirectories = useMemo(() => {
    const flatten = (nodes: FileTreeNode[]): FileTreeNode[] => {
      let result: FileTreeNode[] = [];
      nodes.forEach((node) => {
        if (node.Type === "directory") {
          result.push(node);
          if (node.Children) {
            result = result.concat(flatten(node.Children));
          }
        }
      });
      return result;
    };
    return flatten(allDirectories);
  }, [allDirectories]);

  // 递归查找指定路径的目录
  const findDirectoryByPath = (
    nodes: FileTreeNode[],
    path: string
  ): FileTreeNode | undefined => {
    for (const node of nodes) {
      if (node.Type === "directory" && node.Path === path) {
        return node;
      }
      if (node.Children) {
        const found = findDirectoryByPath(node.Children, path);
        if (found) return found;
      }
    }
    return undefined;
  };

  // 获取当前选中路径下的文件列表（过滤掉目录）
  const currentFiles = useMemo(() => {
    if (!selectedPath) {
      return [];
    }

    const selectedDirectory = findDirectoryByPath(allDirectories, selectedPath);

    if (selectedDirectory && selectedDirectory.Children) {
      // 只返回类型为文件的节点
      return selectedDirectory.Children.filter((node) => node.Type === "file");
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
    const selectedDirectory = findDirectoryByPath(allDirectories, path);
    return selectedDirectory?.Id;
  };

  // 根据路径在文件树中查找目录ID
  const findDirIdByPath = (
    path: string,
    nodes: FileTreeNode[]
  ): string | undefined => {
    // 统一处理路径格式，移除首尾斜杠并拆分
    const parts = path.split("/").filter(Boolean);
    if (parts.length === 0) return undefined;

    let currentNodes = nodes;
    let foundId: string | undefined = undefined;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const node = currentNodes.find(
        (n) => n.Type === "directory" && n.Name === part
      );
      if (node) {
        foundId = node.Id;
        currentNodes = node.Children || [];
      } else {
        // 如果中间某一层没找到，直接返回 undefined
        return undefined;
      }
    }
    return foundId;
  };

  // 文件上传处理 - 支持文件和目录
  const handleFileUpload = async () => {
    const rootDirectoryId = getSelectedDirectoryId(selectedPath);
    if (!rootDirectoryId && uploadType === "file") {
      message.error("请先选择一个目标目录");
      return;
    }

    if (fileList.length === 0) {
      message.error("请选择要上传的内容");
      return;
    }

    setUploading(true);
    try {
      if (uploadType === "file") {
        // 普通多文件上传
      const dataTransfer = new DataTransfer();
      fileList.forEach((file) => {
        if (file.originFileObj) {
          dataTransfer.items.add(file.originFileObj);
        }
      });
      const result = await fileAPI.uploadFiles(
        projectId,
          rootDirectoryId!,
          dataTransfer.files
      );
      message.success(`成功上传 ${result.Data.SuccessCount} 个文件`);
      } else {
        // 目录上传逻辑
        console.log("开始目录上传，文件列表:", fileList);
        // 1. 按目录分组文件
        const dirMap = new Map<string, File[]>();
        fileList.forEach((file) => {
          const originFile = file.originFileObj as File & {
            webkitRelativePath?: string;
          };
          // webkitRelativePath 格式通常为 "folder/subfolder/file.png"
          const relPath = originFile.webkitRelativePath || "";
          console.log(`处理文件: ${originFile.name}, 相对路径: ${relPath}`);
          const pathParts = relPath.split("/");
          
          if (pathParts.length > 1) {
            // 获取文件所属的相对目录路径（不含文件名）
            const dirPath = pathParts.slice(0, -1).join("/");
            if (!dirMap.has(dirPath)) {
              dirMap.set(dirPath, []);
            }
            dirMap.get(dirPath)!.push(originFile);
          }
        });

        console.log("目录分组结果:", Array.from(dirMap.keys()));

        // 2. 递归创建目录并上传文件
        const pathIdMap = new Map<string, string>();
        
        // 获取所有唯一的目录路径并排序，确保父目录先被处理
        const sortedPaths = Array.from(dirMap.keys()).sort(
          (a, b) => a.split("/").length - b.split("/").length
        );

        console.log("排序后的路径列表:", sortedPaths);

        if (sortedPaths.length === 0) {
          console.warn("未发现有效目录结构，请检查是否选择了文件夹。");
          message.warning("未发现有效目录结构，请确认选择的是文件夹。");
          setUploading(false);
          return;
        }

        let totalSuccess = 0;
        for (const fullPath of sortedPaths) {
          const parts = fullPath.split("/");
          let currentParentId = rootDirectoryId; // 初始父目录为用户当前选中的目录

          console.log(`正在处理目录路径: ${fullPath}, 初始父ID: ${currentParentId}`);

          for (let i = 0; i < parts.length; i++) {
            const part = parts[i];
            const thisPath = parts.slice(0, i + 1).join("/");

            if (pathIdMap.has(thisPath)) {
              currentParentId = pathIdMap.get(thisPath);
            } else {
              // 构建在项目中的绝对逻辑路径用于查找
              const absolutePathInProject = selectedPath
                ? `${selectedPath}/${thisPath}`
                : `/${thisPath}`;
              
              console.log(`查找已存在的目录: ${absolutePathInProject}`);
              const existingId = findDirIdByPath(
                absolutePathInProject,
                allDirectories
              );

              if (existingId) {
                console.log(`找到已存在目录 ID: ${existingId}`);
                pathIdMap.set(thisPath, existingId);
                currentParentId = existingId;
              } else {
                // 目录不存在，创建它
                console.log(`创建新目录: ${part}, 父ID: ${currentParentId}`);
                try {
                  const response = await directoryAPI.createDirectory(
                    projectId,
                    {
                      Name: part,
                      ParentDirectoryId: currentParentId || undefined,
                    }
                  );
                  const newDirId = (response.Data as any).Id || (response.Data as any).DirId;
                  console.log(`目录创建成功，新 ID: ${newDirId}`);
                  pathIdMap.set(thisPath, newDirId);
                  currentParentId = newDirId;
                } catch (err: any) {
                  console.error(`创建目录 ${part} 失败:`, err);
                  throw new Error(`创建目录 ${fullPath} 失败: ${err.message}`);
                }
              }
            }
          }

          // 上传该目录下的所有文件
          const filesInDir = dirMap.get(fullPath) || [];
          console.log(`正在上传目录 ${fullPath} 下的文件，数量: ${filesInDir.length}, 目录ID: ${currentParentId}`);
          if (filesInDir.length > 0 && currentParentId) {
            const dataTransfer = new DataTransfer();
            filesInDir.forEach((f) => {
              // 核心修复：重新包装 File 对象，剥离路径，只保留文件名
              const cleanFileName = f.name.split("/").pop()!;
              const cleanFile = new File([f], cleanFileName, { type: f.type });
              dataTransfer.items.add(cleanFile);
            });
            
            const uploadRes = await fileAPI.uploadFiles(
              projectId,
              currentParentId,
              dataTransfer.files
            );
            console.log(`目录 ${fullPath} 文件上传成功，数量: ${uploadRes.Data.SuccessCount}`);
            totalSuccess += uploadRes.Data.SuccessCount;
          }
        }
        message.success(`目录上传完成，共成功上传 ${totalSuccess} 个文件`);
      }

      // 重置状态并刷新
      setFileList([]);
      setUploadModalVisible(false);
      await refresh(); // 等待数据刷新
    } catch (error: any) {
      console.error("上传过程出错:", error);
      message.error(error.message || "上传过程中发生错误");
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
      render: (text: string) => {
        // 去除目录前缀，只显示文件名
        const fileName = text.split("/").pop() || text;
        return (
        <Space>
          <FileImageOutlined style={{ color: "#1890ff" }} />
            <span>{fileName}</span>
        </Space>
        );
      },
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

  const breadcrumbItems = useMemo(() => {
    const items = [
      { title: "项目管理" },
      { title: projectName },
      { title: "文件管理" },
    ];

    if (selectedPath) {
      const parts = selectedPath.split("/").filter(Boolean);
      parts.forEach((part) => {
        items.push({ title: part });
      });
    }

    return items;
  }, [projectName, selectedPath]);

  return (
    <div style={{ padding: 24, minHeight: "100%" }}>
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
                onClick={() => {
                  setUploadType("file");
                  setUploadModalVisible(true);
                  setFileList([]);
                }}
          >
            上传文件
          </Button>
              <Button
                type="primary"
                icon={<FolderAddOutlined />}
                onClick={() => {
                  setUploadType("directory");
                  setUploadModalVisible(true);
                  setFileList([]);
                }}
              >
                上传目录
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
              blockNode
              showLine={{ showLeafIcon: false }}
              switcherIcon={<CaretDownOutlined />}
              treeData={treeData}
              onSelect={handleTreeSelect}
              selectedKeys={selectedKeys}
              className="custom-file-tree"
              defaultExpandAll
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

      <Modal
        title={uploadType === "file" ? "上传文件" : "上传目录"}
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
              placeholder="请选择目标目录 (根目录可留空)"
              allowClear
            >
              {flattenedDirectories.map((dir) => (
                <Select.Option key={dir.Id} value={dir.Path}>
                  {dir.Path}
                </Select.Option>
              ))}
            </Select>
          </div>

          <div style={{ marginBottom: 16 }}>
            <Text strong>{uploadType === "file" ? "选择文件" : "选择目录"}：</Text>
            <div style={{ marginTop: 8 }}>
              <Dragger
                {...uploadProps}
                directory={uploadType === "directory"}
                showUploadList={false}
              >
                <p className="ant-upload-drag-icon">
                  {uploadType === "file" ? (
                    <InboxOutlined style={{ fontSize: "48px", color: "#1890ff" }} />
                  ) : (
                    <FolderAddOutlined style={{ fontSize: "48px", color: "#faad14" }} />
                  )}
                </p>
                <p className="ant-upload-text">
                  {uploadType === "file" ? "点击或拖拽文件到此区域" : "点击或拖拽文件夹到此区域"}
                </p>
                <p className="ant-upload-hint">
                  {uploadType === "file" ? "支持多文件批量上传" : "将自动创建对应的目录结构"}
                </p>
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
