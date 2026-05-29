import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
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
  InputNumber,
  Select,
  Breadcrumb,
  List,
  Spin,
  Progress,
  Alert,
  Tooltip,
} from "antd";
import {
  UploadOutlined,
  FolderOutlined,
  FileImageOutlined,
  DownloadOutlined,
  DeleteOutlined,
  PlusOutlined,
  EyeOutlined,
  InboxOutlined,
  FolderAddOutlined,
  CaretDownOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import type {
  TableColumnsType,
  TreeDataNode,
  UploadProps,
  UploadFile,
} from "antd";
import { useRequest } from "ahooks";
import { fileAPI, directoryAPI, getUserId } from "../../utils/api";
import { FileTreeNode, UploadConfigResponse } from "../../utils/data";
import "./FilesPage.css";
import { filePreviewPath } from "@/utils/constans";
import HighBitPreviewImage from "@/components/HighBitPreviewImage";

const { Title, Text } = Typography;
const { Dragger } = Upload;
const DEFAULT_DIRECTORY_SORT_ORDER = 99;
const ROOT_DIRECTORY_PATH = "";

const FALLBACK_UPLOAD_CONFIG: UploadConfigResponse = {
  MaxFileSizeBytes: 200 * 1024 * 1024,
  MaxTotalSizeBytes: 10 * 1024 * 1024 * 1024,
  BatchMaxFiles: 10,
  BatchMaxBytes: 500 * 1024 * 1024,
  BatchTimeoutBaseMs: 60 * 1000,
  BatchTimeoutMsPerMB: 1500,
  MaxRetries: 1,
  AllowedImageTypes: [
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "webp",
    "tif",
    "tiff",
    "dcm",
    "dicom",
    "dic",
    "diconde",
  ],
};
// 待上传列表最多渲染的条目数；避免上千 DOM 节点导致渲染卡顿
const MAX_DISPLAYED_UPLOAD_ITEMS = 50;

function getFileExtension(fileName: string): string {
  const lastDot = fileName.lastIndexOf(".");
  return lastDot >= 0 ? fileName.slice(lastDot + 1).toLowerCase() : "";
}

function makeUploadSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function getFileRelativePath(file: File): string {
  return ((file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name || "").replace(/^\/+/, "");
}

function buildUploadKey(file: File): string {
  return `${getFileRelativePath(file)}::${file.size}::${file.lastModified}`;
}

function createBatches(files: File[], maxFiles: number, maxBytes: number): File[][] {
  const batches: File[][] = [];
  let current: File[] = [];
  let currentBytes = 0;
  const safeMaxFiles = Math.max(maxFiles || 1, 1);
  const safeMaxBytes = Math.max(maxBytes || Number.MAX_SAFE_INTEGER, 1);

  files.forEach((file) => {
    const wouldExceedFiles = current.length >= safeMaxFiles;
    const wouldExceedBytes = current.length > 0 && currentBytes + file.size > safeMaxBytes;
    if (wouldExceedFiles || wouldExceedBytes) {
      batches.push(current);
      current = [];
      currentBytes = 0;
    }
    current.push(file);
    currentBytes += file.size;
  });

  if (current.length > 0) {
    batches.push(current);
  }
  return batches;
}

function getBatchTimeoutMs(batchBytes: number, config: UploadConfigResponse): number {
  const mb = Math.ceil(batchBytes / 1024 / 1024);
  return Math.max(
    config.BatchTimeoutBaseMs,
    config.BatchTimeoutBaseMs + mb * config.BatchTimeoutMsPerMB
  );
}

function formatUploadSize(size: number): string {
  if (size >= 1024 * 1024 * 1024) {
    return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(2)} MB`;
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(2)} KB`;
  }
  return `${size} B`;
}

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
  const [uploadTargetPath, setUploadTargetPath] = useState<string>(ROOT_DIRECTORY_PATH);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewFile, setPreviewFile] = useState<any | null>(null);
  // 新增状态管理上传文件列表
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadProgressText, setUploadProgressText] = useState("");
  const [uploadProgressDetail, setUploadProgressDetail] = useState("");
  // 选择阶段被过滤掉的文件名，按本批选择汇总后统一提示
  const skippedFilesRef = useRef<{ nonImage: string[]; tooLarge: string[] }>({
    nonImage: [],
    tooLarge: [],
  });
  // 进度更新节流状态，避免 onprogress 高频 setState 拖垮主线程
  const progressThrottleRef = useRef<{ lastPercent: number; lastTime: number }>({
    lastPercent: -1,
    lastTime: 0,
  });
  const [createDirectoryVisible, setCreateDirectoryVisible] = useState(false);
  const [createDirectoryName, setCreateDirectoryName] = useState("");
  const [createDirectorySortOrder, setCreateDirectorySortOrder] = useState<number>(DEFAULT_DIRECTORY_SORT_ORDER);
  const [creatingDirectory, setCreatingDirectory] = useState(false);
  const [editDirectoryVisible, setEditDirectoryVisible] = useState(false);
  const [editingDirectory, setEditingDirectory] = useState<FileTreeNode | null>(null);
  const [editDirectoryName, setEditDirectoryName] = useState("");
  const [editDirectorySortOrder, setEditDirectorySortOrder] = useState<number>(DEFAULT_DIRECTORY_SORT_ORDER);
  const [updatingDirectory, setUpdatingDirectory] = useState(false);
  const [deleteDirectoryVisible, setDeleteDirectoryVisible] = useState(false);
  const [deletingDirectory, setDeletingDirectory] = useState<FileTreeNode | null>(null);
  const [deleteDirectoryConfirmName, setDeleteDirectoryConfirmName] = useState("");
  const [deleteDirectoryLoading, setDeleteDirectoryLoading] = useState(false);

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

  const { data: uploadConfigResponse } = useRequest(() => fileAPI.getUploadConfig());
  const uploadConfig = uploadConfigResponse?.Data || FALLBACK_UPLOAD_CONFIG;
  const allowedImageExtensions = useMemo(
    () => new Set(uploadConfig.AllowedImageTypes.map((ext) => ext.toLowerCase())),
    [uploadConfig]
  );
  const uploadAccept = useMemo(
    () => uploadConfig.AllowedImageTypes.map((ext) => `.${ext}`).join(","),
    [uploadConfig]
  );
  const isAllowedImageFile = useCallback(
    (fileName: string) => allowedImageExtensions.has(getFileExtension(fileName)),
    [allowedImageExtensions]
  );

  const allDirectories = filesResponse?.Data || [];

  // 递归查找指定路径的目录
  const findDirectoryByPath = useCallback((
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
  }, []);

  // 默认选择第一个目录，或在当前目录被删除后重新落到可用目录
  useEffect(() => {
    if (allDirectories.length === 0) {
      if (selectedPath) {
        setSelectedPath("");
      }
      return;
    }

    if (!selectedPath || !findDirectoryByPath(allDirectories, selectedPath)) {
      const firstDirectory = allDirectories[0];
      setSelectedPath(firstDirectory.Path);
    }
  }, [allDirectories, findDirectoryByPath, selectedPath]);

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

  const sortDirectoryNodes = (nodes: FileTreeNode[]): FileTreeNode[] => {
    return [...nodes].sort((a, b) => {
      const sortOrderA = a.SortOrder ?? DEFAULT_DIRECTORY_SORT_ORDER;
      const sortOrderB = b.SortOrder ?? DEFAULT_DIRECTORY_SORT_ORDER;
      if (sortOrderA !== sortOrderB) {
        return sortOrderA - sortOrderB;
      }
      return a.Name.localeCompare(b.Name, "zh-CN");
    });
  };

  function handleOpenCreateDirectory() {
    setCreateDirectoryVisible(true);
    setCreateDirectoryName("");
    setCreateDirectorySortOrder(DEFAULT_DIRECTORY_SORT_ORDER);
  }

  function handleOpenEditDirectory(directory: FileTreeNode) {
    setEditingDirectory(directory);
    setEditDirectoryName(directory.Name);
    setEditDirectorySortOrder(directory.SortOrder ?? DEFAULT_DIRECTORY_SORT_ORDER);
    setEditDirectoryVisible(true);
  }

  function handleOpenDeleteDirectory(directory: FileTreeNode) {
    setDeletingDirectory(directory);
    setDeleteDirectoryConfirmName("");
    setDeleteDirectoryVisible(true);
  }

  // 递归转换为Ant Design树形数据格式
  const convertToTreeData = (nodes: FileTreeNode[]): TreeDataNode[] => {
    return sortDirectoryNodes(nodes.filter((node) => node.Type === "directory"))
      .map((node) => {
        const hasDirectoryChildren = node.Children?.some(
          (c) => c.Type === "directory"
        );
        const totalFiles = calculateTotalFiles(node);
        return {
          title: (
            <div className="custom-tree-node">
              <Space size={8} className="custom-tree-node-name">
                <FolderOutlined style={{ color: "#1890ff" }} />
                <span title={node.Name}>{node.Name}</span>
              </Space>
              <Space size={4} className="custom-tree-node-meta" onClick={(event) => event.stopPropagation()}>
                {totalFiles > 0 && (
                  <span className="custom-tree-file-count">
                    {totalFiles}
                  </span>
                )}
                {!isReadOnly && (
                  <span className="custom-tree-node-actions">
                    <Tooltip title="编辑目录">
                      <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => handleOpenEditDirectory(node)}
                      />
                    </Tooltip>
                    <Tooltip title="删除目录">
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleOpenDeleteDirectory(node)}
                      />
                    </Tooltip>
                  </span>
                )}
              </Space>
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
  }, [allDirectories, convertToTreeData]);

  // 展平所有目录用于下拉选择
  const flattenedDirectories = useMemo(() => {
    const flatten = (nodes: FileTreeNode[]): FileTreeNode[] => {
      let result: FileTreeNode[] = [];
      sortDirectoryNodes(nodes.filter((node) => node.Type === "directory")).forEach((node) => {
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
  }, [allDirectories, sortDirectoryNodes]);

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
  }, [allDirectories, findDirectoryByPath, selectedPath]);

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

  const closePreview = useCallback(() => {
    setPreviewVisible(false);
    setPreviewFile(null);
  }, []);

  const handlePreview = useCallback((file: any) => {
    setPreviewFile(file);
    setPreviewVisible(true);
  }, []);

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

  const handleCreateDirectory = async () => {
    const directoryName = createDirectoryName.trim();
    if (!directoryName) {
      message.error("目录名称不能为空");
      return;
    }

    setCreatingDirectory(true);
    try {
      await directoryAPI.createDirectory(projectId, {
        Name: directoryName,
        SortOrder: createDirectorySortOrder,
      });
      message.success("目录创建成功");
      setCreateDirectoryName("");
      setCreateDirectorySortOrder(DEFAULT_DIRECTORY_SORT_ORDER);
      await refresh();
    } catch (error) {
      // 错误已在API层处理
    } finally {
      setCreatingDirectory(false);
    }
  };

  const handleUpdateDirectory = async () => {
    if (!editingDirectory) return;

    const directoryName = editDirectoryName.trim();
    if (!directoryName) {
      message.error("目录名称不能为空");
      return;
    }

    setUpdatingDirectory(true);
    try {
      const oldPath = editingDirectory.Path;
      const parentPath = getParentDirectoryPath(oldPath);
      const newPath = parentPath ? `${parentPath}/${directoryName}` : `/${directoryName}`;

      await directoryAPI.updateDirectory(editingDirectory.Id, projectId, {
        Name: directoryName,
        SortOrder: editDirectorySortOrder,
      });
      message.success("目录更新成功");
      setEditDirectoryVisible(false);
      setEditingDirectory(null);
      if (selectedPath === oldPath || selectedPath.startsWith(`${oldPath}/`)) {
        setSelectedPath(selectedPath.replace(oldPath, newPath));
      }
      await refresh();
    } catch (error) {
      // 错误已在API层处理
    } finally {
      setUpdatingDirectory(false);
    }
  };

  const getParentDirectoryPath = (path: string): string => {
    const parts = path.split("/").filter(Boolean);
    if (parts.length <= 1) {
      return "";
    }
    return `/${parts.slice(0, -1).join("/")}`;
  };

  const handleDeleteDirectory = async () => {
    if (!deletingDirectory) return;

    if (deleteDirectoryConfirmName.trim() !== deletingDirectory.Name) {
      message.error("请输入正确的目录名称以确认删除");
      return;
    }

    setDeleteDirectoryLoading(true);
    try {
      await directoryAPI.deleteDirectory(deletingDirectory.Id, projectId);
      message.success("目录删除成功");
      setDeleteDirectoryVisible(false);
      setDeleteDirectoryConfirmName("");
      if (selectedPath === deletingDirectory.Path || selectedPath.startsWith(`${deletingDirectory.Path}/`)) {
        setSelectedPath(getParentDirectoryPath(deletingDirectory.Path));
        setCurrentPage(1);
      }
      setDeletingDirectory(null);
      await refresh();
    } catch (error) {
      // 错误已在API层处理
    } finally {
      setDeleteDirectoryLoading(false);
    }
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

  const getUploadFileSize = (file: UploadFile): number => {
    return file.originFileObj?.size || file.size || 0;
  };

  const resetUploadProgress = useCallback(() => {
    setUploadProgress(0);
    setUploadProgressText("");
    setUploadProgressDetail("");
    progressThrottleRef.current = { lastPercent: -1, lastTime: 0 };
  }, []);

  const updateUploadProgress = useCallback((
    uploadedBytes: number,
    totalBytes: number,
    completedFiles: number,
    totalFiles: number,
    statusText: string,
    options?: {
      isFinal?: boolean;
      waitingForServer?: boolean;
    }
  ) => {
    const safeUploadedBytes = Math.min(Math.max(uploadedBytes, 0), totalBytes || uploadedBytes);
    const isFinal = options?.isFinal ?? false;
    const waitingForServer = options?.waitingForServer ?? false;
    const estimatedFiles = totalBytes > 0
      ? Math.floor((safeUploadedBytes / totalBytes) * totalFiles)
      : 0;
    const displayFiles = isFinal
      ? totalFiles
      : totalFiles > 0
        ? Math.min(
            waitingForServer ? totalFiles - 1 : totalFiles,
            Math.max(Math.min(completedFiles, totalFiles), estimatedFiles)
          )
        : 0;
    const rawPercent = totalBytes > 0
      ? Math.round((safeUploadedBytes / totalBytes) * 100)
      : totalFiles > 0
        ? Math.min(100, Math.round((Math.min(completedFiles, totalFiles) / totalFiles) * 100))
        : 0;
    const percent = isFinal ? 100 : Math.min(99, rawPercent);

    // 节流：xhr.upload.onprogress 触发非常频繁，且 detail 文案每次都带新的字节数（字符串每次都变，
    // 必然触发整页重渲染）。若百分比未变且距上次提交不足 200ms，直接跳过，避免高频重渲染拖垮主线程
    // （大目录上传时这正是导致页面卡死、上传停滞的原因）。
    const now = Date.now();
    const throttle = progressThrottleRef.current;
    if (!isFinal && percent === throttle.lastPercent && now - throttle.lastTime < 200) {
      return;
    }
    throttle.lastPercent = percent;
    throttle.lastTime = now;

    setUploadProgress(percent);
    setUploadProgressText(statusText);

    if (totalFiles > 0) {
      if (totalBytes > 0) {
        setUploadProgressDetail(
          `${isFinal ? "已完成" : "约已传输"} ${displayFiles}/${totalFiles} 个文件 · ${formatUploadSize(safeUploadedBytes)} / ${formatUploadSize(totalBytes)}`
        );
      } else {
        setUploadProgressDetail(`${isFinal ? "已完成" : "约已传输"} ${displayFiles}/${totalFiles} 个文件`);
      }
    } else {
      setUploadProgressDetail("");
    }
  }, []);

  const openUploadModal = (type: "file" | "directory") => {
    const selectedDirectoryExists = Boolean(getSelectedDirectoryId(selectedPath));
    const firstDirectoryPath = flattenedDirectories[0]?.Path ?? ROOT_DIRECTORY_PATH;

    setUploadType(type);
    setUploadModalVisible(true);
    setUploadTargetPath(
      type === "file"
        ? selectedDirectoryExists
          ? selectedPath
          : firstDirectoryPath
        : selectedDirectoryExists
          ? selectedPath
          : ROOT_DIRECTORY_PATH
    );
    setFileList([]);
    resetUploadProgress();
  };

  // 文件上传处理 - 支持文件和目录（上传前过滤 + 小批次上传 + 逐批容错）
  const handleFileUpload = async () => {
    const isRootUploadTarget = uploadTargetPath === ROOT_DIRECTORY_PATH;
    const rootDirectoryId = isRootUploadTarget
      ? undefined
      : getSelectedDirectoryId(uploadTargetPath);

    if (!rootDirectoryId && uploadType === "file") {
      message.error("上传文件必须选择已创建的目标目录");
      return;
    }

    if (!isRootUploadTarget && !rootDirectoryId) {
      message.error("目标目录不存在，请重新选择");
      return;
    }

    if (fileList.length === 0) {
      message.error("请选择要上传的内容");
      return;
    }

    // 1. 上传前过滤：只保留受支持的图片类型，且单文件不超过后端配置上限
    //    —— 非图片/超大文件在前端就被剔除，避免触发后端 multipart 200MB 限制导致整批 500
    const acceptedFileList: UploadFile[] = [];
    const skippedNonImage: string[] = [];
    const skippedTooLarge: string[] = [];
    fileList.forEach((file) => {
      const fileName = file.name || file.originFileObj?.name || "";
      if (!isAllowedImageFile(fileName)) {
        skippedNonImage.push(fileName);
        return;
      }
      if (getUploadFileSize(file) > uploadConfig.MaxFileSizeBytes) {
        skippedTooLarge.push(fileName);
        return;
      }
      acceptedFileList.push(file);
    });

    const skipSummaryParts: string[] = [];
    if (skippedNonImage.length > 0) {
      skipSummaryParts.push(`${skippedNonImage.length} 个非图片文件`);
    }
    if (skippedTooLarge.length > 0) {
      skipSummaryParts.push(`${skippedTooLarge.length} 个超过 ${formatUploadSize(uploadConfig.MaxFileSizeBytes)} 的文件`);
    }
    const skipSummary = skipSummaryParts.join("、");

    if (acceptedFileList.length === 0) {
      message.warning(
        skipSummary
          ? `没有可上传的图片文件（已跳过 ${skipSummary}）`
          : "没有可上传的图片文件"
      );
      return;
    }
    if (skipSummary) {
      message.warning(`已跳过 ${skipSummary}，将继续上传 ${acceptedFileList.length} 个文件`);
    }

    const totalFiles = acceptedFileList.length;
    const totalBytes = acceptedFileList.reduce((sum, file) => sum + getUploadFileSize(file), 0);
    const uploadSessionId = makeUploadSessionId();

    // 全局累计量（跨目录、跨批次）
    let uploadedBytes = 0;
    let uploadedFiles = 0;
    let totalSuccess = 0;
    let totalFailed = 0;
    const failedNames: string[] = [];

    // 将一组文件按“文件数 + 批次总大小”双阈值分批上传到指定目录。
    // 单个批次失败（网络/服务器错误）只把该批计为失败并继续后续批次，不再连累整个目录。
    const uploadGroupInBatches = async (
      dirId: string,
      files: File[],
      label: string
    ) => {
      const batches = createBatches(files, uploadConfig.BatchMaxFiles, uploadConfig.BatchMaxBytes);
      for (const batch of batches) {
        const batchBytes = batch.reduce((sum, f) => sum + f.size, 0);
        const batchUploadKeys = batch.map(buildUploadKey);
        const batchTimeoutMs = getBatchTimeoutMs(batchBytes, uploadConfig);

        // 单批最多按后端配置重试；每个文件带幂等键，避免响应超时后的重试重复入库。
        let succeeded = false;
        for (let attempt = 0; attempt <= uploadConfig.MaxRetries && !succeeded; attempt++) {
          try {
            const res = await fileAPI.uploadFiles(projectId, dirId, batch, {
              silent: true, // 失败由本函数统一汇总，避免逐批弹窗刷屏
              timeoutMs: batchTimeoutMs,
              uploadSessionId,
              uploadKeys: batchUploadKeys,
              onProgress: ({ loaded, total }) => {
                const batchLoaded =
                  total > 0 ? Math.min(batchBytes, (loaded / total) * batchBytes) : 0;
                const waitingForServer = total > 0 && loaded >= total;
                updateUploadProgress(
                  uploadedBytes + batchLoaded,
                  totalBytes,
                  uploadedFiles,
                  totalFiles,
                  waitingForServer
                    ? `${label}当前批次已上传，服务器处理中，请稍候...`
                    : attempt > 0
                      ? `正在重试${label}（第 ${attempt} 次）...`
                      : `正在上传${label}...`,
                  { waitingForServer }
                );
              },
            });
            totalSuccess += res.Data.SuccessCount;
            totalFailed += res.Data.FailedCount ?? 0;
            // 后端逐文件失败明细（如不支持的类型）
            (res.Data.FailedFiles as Array<{ OriginalName?: string }> | undefined)?.forEach(
              (f) => f?.OriginalName && failedNames.push(f.OriginalName)
            );
            succeeded = true;
          } catch (err) {
            if (attempt < uploadConfig.MaxRetries) {
              console.warn(`批次上传失败，重试 ${attempt + 1}/${uploadConfig.MaxRetries}（${label}）:`, err);
              await new Promise((r) => setTimeout(r, 500 * (attempt + 1))); // 退避
            } else {
              console.error(`批次上传最终失败（${label}）:`, err);
              totalFailed += batch.length;
              batch.forEach((f) => failedNames.push(f.name));
            }
          }
        }

        uploadedBytes += batchBytes;
        uploadedFiles += batch.length;
        // 单批结束只刷新累计进度，不显示“已完成”——整组可能还有后续批次，
        // 真正的“上传完成”由全部上传结束后的 isFinal 更新负责
        updateUploadProgress(
          uploadedBytes,
          totalBytes,
          uploadedFiles,
          totalFiles,
          `正在上传${label}...`
        );
      }
    };

    setUploading(true);
    updateUploadProgress(0, totalBytes, 0, totalFiles, "正在准备上传...");
    try {
      if (uploadType === "file") {
        // 普通多文件上传：直接分批上传到目标目录
        const files = acceptedFileList
          .map((file) => file.originFileObj)
          .filter((f): f is NonNullable<typeof f> => Boolean(f));
        await uploadGroupInBatches(rootDirectoryId!, files, "文件");
      } else {
        // 目录上传：按相对目录分组 -> 递归创建目录 -> 分批上传
        const dirMap = new Map<string, File[]>();
        acceptedFileList.forEach((file) => {
          const originFile = file.originFileObj as
            | (File & { webkitRelativePath?: string })
            | undefined;
          if (!originFile) return;
          // webkitRelativePath 格式通常为 "folder/subfolder/file.png"
          const relPath = getFileRelativePath(originFile);
          const pathParts = relPath.split("/");
          if (pathParts.length > 1) {
            const dirPath = pathParts.slice(0, -1).join("/");
            if (!dirMap.has(dirPath)) {
              dirMap.set(dirPath, []);
            }
            dirMap.get(dirPath)!.push(originFile);
          }
        });

        // 父目录先于子目录处理
        const pathIdMap = new Map<string, string>();
        const sortedPaths = Array.from(dirMap.keys()).sort(
          (a, b) => a.split("/").length - b.split("/").length
        );

        if (sortedPaths.length === 0) {
          message.warning("未发现有效目录结构，请确认选择的是文件夹。");
          return;
        }

        for (const fullPath of sortedPaths) {
          const parts = fullPath.split("/");
          let currentParentId = rootDirectoryId; // 初始父目录为用户当前选中的目录

          updateUploadProgress(
            uploadedBytes,
            totalBytes,
            uploadedFiles,
            totalFiles,
            `正在准备目录 ${fullPath}...`
          );

          for (let i = 0; i < parts.length; i++) {
            const part = parts[i];
            const thisPath = parts.slice(0, i + 1).join("/");

            if (pathIdMap.has(thisPath)) {
              currentParentId = pathIdMap.get(thisPath);
            } else {
              // 构建在项目中的绝对逻辑路径用于查找
              const absolutePathInProject = uploadTargetPath
                ? `${uploadTargetPath}/${thisPath}`
                : `/${thisPath}`;
              const existingId = findDirIdByPath(absolutePathInProject, allDirectories);

              if (existingId) {
                pathIdMap.set(thisPath, existingId);
                currentParentId = existingId;
              } else {
                // 目录不存在，创建它
                try {
                  const response = await directoryAPI.createDirectory(projectId, {
                    Name: part,
                    ParentDirectoryId: currentParentId || undefined,
                  });
                  const newDirId =
                    (response.Data as any).Id || (response.Data as any).DirId;
                  pathIdMap.set(thisPath, newDirId);
                  currentParentId = newDirId;
                } catch (err: any) {
                  console.error(`创建目录 ${part} 失败:`, err);
                  throw new Error(`创建目录 ${fullPath} 失败: ${err.message}`);
                }
              }
            }
          }

          // 上传该目录下的所有文件（直接传原始 File 对象，文件名剥离由 uploadFiles 用
          // FormData 第三参数完成，避免 new File() 克隆数据撑爆内存）
          const filesInDir = dirMap.get(fullPath) || [];
          if (filesInDir.length > 0 && currentParentId) {
            await uploadGroupInBatches(currentParentId, filesInDir, `目录 ${fullPath}`);
          }
        }
      }

      updateUploadProgress(totalBytes, totalBytes, totalFiles, totalFiles, "上传完成", {
        isFinal: true,
      });

      // 汇总结果
      let summary = `成功上传 ${totalSuccess} 个文件`;
      if (totalFailed > 0) {
        // 附上最多 3 个失败文件名，便于定位
        const preview = failedNames.slice(0, 3).join("、");
        const more = failedNames.length > 3 ? " 等" : "";
        summary += `，${totalFailed} 个失败${preview ? `（${preview}${more}）` : ""}`;
      }
      if (skipSummary) {
        summary += `，已跳过 ${skipSummary}`;
      }

      // 重置状态并刷新
      setFileList([]);
      setUploadModalVisible(false);
      resetUploadProgress();
      if (totalFailed > 0) {
        message.warning(summary);
      } else {
        message.success(summary);
      }
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
    if (uploading) {
      message.info("文件正在上传，请等待当前任务完成");
      return;
    }
    setFileList([]);
    setUploadModalVisible(false);
    resetUploadProgress();
  };

  // 上传配置
  const uploadProps: UploadProps = {
    name: "File",
    multiple: true,
    accept: uploadAccept,
    fileList: fileList,
    onChange: ({ fileList: newFileList }) => {
      if (uploading) return;
      setFileList(newFileList);
    },
    // 选择阶段就过滤：非图片 / 超过后端配置大小的文件直接从列表中剔除，并在本批选择结束时统一提示
    beforeUpload: (file, batch) => {
      if (uploading) return Upload.LIST_IGNORE;

      let ignored = false;
      if (!isAllowedImageFile(file.name)) {
        skippedFilesRef.current.nonImage.push(file.name);
        ignored = true;
      } else if (file.size > uploadConfig.MaxFileSizeBytes) {
        skippedFilesRef.current.tooLarge.push(file.name);
        ignored = true;
      }

      // antd 会对本批每个文件依次调用 beforeUpload，到最后一个时统一弹一次提示，避免刷屏
      if (file === batch[batch.length - 1]) {
        const { nonImage, tooLarge } = skippedFilesRef.current;
        const parts: string[] = [];
        if (nonImage.length > 0) parts.push(`${nonImage.length} 个非图片文件`);
        if (tooLarge.length > 0) parts.push(`${tooLarge.length} 个超过 ${formatUploadSize(uploadConfig.MaxFileSizeBytes)} 的文件`);
        if (parts.length > 0) {
          message.warning(`已自动忽略 ${parts.join("、")}`);
        }
        skippedFilesRef.current = { nonImage: [], tooLarge: [] };
      }

      return ignored ? Upload.LIST_IGNORE : false; // 合法文件保留在列表，手动上传
    },
    onRemove: (file) => {
      if (uploading) return false;
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
              const downloadUrl = `${filePreviewPath}?FileId=${record.Id}&ProjectId=${projectId}&UserId=${getUserId()}`;

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

  const canConfirmUpload =
    fileList.length > 0 &&
    !uploading &&
    (uploadType === "directory" || Boolean(getSelectedDirectoryId(uploadTargetPath)));

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
              <Button icon={<PlusOutlined />} onClick={handleOpenCreateDirectory}>
                新建目录
              </Button>
              <Button
                type="primary"
                icon={<UploadOutlined />}
                onClick={() => openUploadModal("file")}
              >
                上传文件
              </Button>
              <Button
                type="primary"
                icon={<FolderAddOutlined />}
                onClick={() => openUploadModal("directory")}
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
        title={
          <Space>
            <ExclamationCircleOutlined style={{ color: "#faad14" }} />
            <span>创建目录</span>
          </Space>
        }
        open={createDirectoryVisible}
        onOk={handleCreateDirectory}
        onCancel={() => setCreateDirectoryVisible(false)}
        okText="确定"
        cancelText="取消"
        confirmLoading={creatingDirectory}
        destroyOnClose
        centered
      >
        <Space direction="vertical" size={12} style={{ width: "100%", paddingTop: 8 }}>
          <div>
            <Text>请输入目录名称：</Text>
            <Input
              placeholder="请输入目录名称"
              value={createDirectoryName}
              onChange={(event) => setCreateDirectoryName(event.target.value)}
              onPressEnter={handleCreateDirectory}
              style={{ marginTop: 8 }}
              autoFocus
            />
          </div>
          <div>
            <Text>请输入排序号：</Text>
            <InputNumber
              placeholder="请输入排序号"
              min={0}
              precision={0}
              value={createDirectorySortOrder}
              onChange={(value) => setCreateDirectorySortOrder(value ?? DEFAULT_DIRECTORY_SORT_ORDER)}
              onPressEnter={handleCreateDirectory}
              style={{ width: "100%", marginTop: 8 }}
            />
          </div>
        </Space>
      </Modal>

      <Modal
        title={
          <Space>
            <EditOutlined style={{ color: "#1890ff" }} />
            <span>编辑目录</span>
          </Space>
        }
        open={editDirectoryVisible}
        onOk={handleUpdateDirectory}
        onCancel={() => setEditDirectoryVisible(false)}
        okText="保存"
        cancelText="取消"
        confirmLoading={updatingDirectory}
        destroyOnClose
        centered
      >
        <Space direction="vertical" size={12} style={{ width: "100%", paddingTop: 8 }}>
          <div>
            <Text>目录名称：</Text>
            <Input
              placeholder="请输入目录名称"
              value={editDirectoryName}
              onChange={(event) => setEditDirectoryName(event.target.value)}
              onPressEnter={handleUpdateDirectory}
              style={{ marginTop: 8 }}
              autoFocus
            />
          </div>
          <div>
            <Text>排序号：</Text>
            <InputNumber
              placeholder="请输入排序号"
              min={0}
              precision={0}
              value={editDirectorySortOrder}
              onChange={(value) => setEditDirectorySortOrder(value ?? DEFAULT_DIRECTORY_SORT_ORDER)}
              onPressEnter={handleUpdateDirectory}
              style={{ width: "100%", marginTop: 8 }}
            />
          </div>
        </Space>
      </Modal>

      <Modal
        title={
          <Space>
            <ExclamationCircleOutlined style={{ color: "#ff4d4f", fontSize: 22 }} />
            <span>确认删除目录</span>
          </Space>
        }
        open={deleteDirectoryVisible}
        onOk={handleDeleteDirectory}
        onCancel={() => setDeleteDirectoryVisible(false)}
        okText="确认删除"
        cancelText="取消"
        confirmLoading={deleteDirectoryLoading}
        okButtonProps={{
          danger: true,
          disabled: deleteDirectoryConfirmName.trim() !== deletingDirectory?.Name,
        }}
        centered
      >
        <div style={{ paddingTop: 8 }}>
          <div style={{ marginBottom: 16, fontSize: 16, fontWeight: 500 }}>
            {deletingDirectory?.Name}
          </div>
          <Alert
            type="error"
            style={{
              backgroundColor: "#fff1f0",
              border: "1px solid #ffa39e",
              borderRadius: 8,
              marginBottom: 24,
            }}
            message={
              <div style={{ color: "#cf1322" }}>
                <div style={{ marginBottom: 4 }}>
                  • 将删除目录中的所有文件 ({deletingDirectory ? calculateTotalFiles(deletingDirectory) : 0}个文件)
                </div>
                <div style={{ marginBottom: 4 }}>• 将删除所有子目录</div>
                <div style={{ fontWeight: 600 }}>• 此操作不可恢复，请谨慎操作</div>
              </div>
            }
          />
          <div style={{ marginBottom: 8, color: "#595959" }}>
            请输入目录名称以确认删除：
          </div>
          <Input
            placeholder={deletingDirectory?.Name}
            value={deleteDirectoryConfirmName}
            onChange={(event) => setDeleteDirectoryConfirmName(event.target.value)}
            onPressEnter={handleDeleteDirectory}
            style={{ height: 44, borderRadius: 6 }}
          />
        </div>
      </Modal>

      <Modal
        title={uploadType === "file" ? "上传文件" : "上传目录"}
        open={uploadModalVisible}
        onCancel={handleCancelUpload}
        onOk={handleFileUpload}
        okText="确认上传"
        cancelText="取消"
        confirmLoading={uploading}
        width={600}
        closable={!uploading}
        maskClosable={!uploading}
        keyboard={!uploading}
        okButtonProps={{
          disabled: !canConfirmUpload,
        }}
        cancelButtonProps={{
          disabled: uploading,
        }}
      >
        <div style={{ padding: "20px 0" }}>
          <div style={{ marginBottom: 16 }}>
            <Text strong>目标目录：</Text>
            <Select
              value={uploadTargetPath}
              onChange={setUploadTargetPath}
              style={{ width: "100%", marginTop: 8 }}
              placeholder={uploadType === "file" ? "请选择已创建的目标目录" : "请选择目标目录"}
              disabled={uploading}
            >
              <Select.Option
                key="root"
                value={ROOT_DIRECTORY_PATH}
                disabled={uploadType === "file"}
              >
                /（根目录，仅支持上传目录）
              </Select.Option>
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
                disabled={uploading}
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

          {uploading && (
            <div style={{ marginBottom: 16, padding: "12px 16px", background: "#fafafa", border: "1px solid #f0f0f0", borderRadius: 8 }}>
              <Text strong>{uploadProgressText || "正在上传..."}</Text>
              <Progress
                percent={uploadProgress}
                status="active"
                strokeColor="#1890ff"
                style={{ margin: "8px 0 4px" }}
              />
              {uploadProgressDetail && (
                <Text type="secondary">{uploadProgressDetail}</Text>
              )}
            </div>
          )}

          {fileList.length > 0 && (
            <div>
              <Text strong>待上传文件列表（共 {fileList.length} 个）：</Text>
              {/* 仅渲染前若干项：上千个 List.Item 全量渲染会产生海量 DOM，
                  叠加上传进度的频繁重渲染会卡死主线程，进而导致上传停滞 */}
              <List
                size="small"
                dataSource={fileList.slice(0, MAX_DISPLAYED_UPLOAD_ITEMS)}
                style={{ marginTop: 8, maxHeight: 200, overflow: "auto" }}
                footer={
                  fileList.length > MAX_DISPLAYED_UPLOAD_ITEMS ? (
                    <Text type="secondary">
                      仅显示前 {MAX_DISPLAYED_UPLOAD_ITEMS} 个，其余 {fileList.length - MAX_DISPLAYED_UPLOAD_ITEMS} 个已省略
                    </Text>
                  ) : null
                }
                renderItem={(file) => (
                  <List.Item
                    actions={[
                      <Button
                        type="link"
                        size="small"
                        disabled={uploading}
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
        onCancel={closePreview}
        width={800}
        centered
      >
        <div style={{ textAlign: "center", minHeight: 200, position: 'relative' }}>
          {previewFile ? (
            <HighBitPreviewImage
              src={`${filePreviewPath}?FileId=${previewFile.Id}&ProjectId=${projectId}&UserId=${getUserId()}`}
              fileName={previewFile.Name || previewFile.FileName}
              alt="预览图片"
              style={{
                maxWidth: "100%",
                maxHeight: "60vh",
                display: 'block',
                margin: '0 auto',
              }}
            />
          ) : (
            <div style={{ display: "flex", flexDirection: 'column', justifyContent: "center", alignItems: "center", height: 200, gap: 12, color: "#999" }}>
              <Spin size="large" />
              <span style={{ fontSize: 13 }}>图片加载中...</span>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};

export default FilesPage;
