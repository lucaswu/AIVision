// API 响应类型 (与后端统一)
export interface ApiResponse<T = any> {
  Code: number;
  Message: string;
  Data: T;
  Total?: number;
}

// 项目接口定义 (基于后端Project实体)
export interface Project {
  Id: string; // UUID格式
  Name: string;
  Description?: string;
  UserId: string;
  CreateTime: string;
  FileCount?: number;
  TaskCount?: number;
}

// 目录接口定义 (基于后端Directory实体)
export interface Directory {
  Id: string; // UUID格式
  Name: string;
  ProjectId: string;
  ParentDirectoryId?: string;
  Path: string;
  Level: number;
  CreateTime: string;
  UpdatedAt: string;
  Children?: Directory[];
  FileCount?: number;
}

// 文件接口定义 (基于后端File实体)
export interface FileEntity {
  Id: string; // UUID格式
  OriginalName: string;
  FileName: string;
  FilePath: string;
  FileSize: number;
  FileType: string;
  ProjectId: string;
  DirectoryId: string;
  UserId: string;
  UploadDate: string;
  Status: "uploaded" | "processing" | "completed" | "failed";
}

// 任务接口定义 (基于后端Task实体)
export interface Task {
  Id: string; // UUID格式
  Name: string;
  Description?: string;
  ProjectId: string;
  UserId: string;
  AlgorithmType: string;
  Status: "pending" | "processing" | "completed" | "failed" | "cancelled";
  Progress: number;
  FileCount: number;
  ProcessedFiles: number;
  SuccessFiles: number;
  FailedFiles: number;
  CreateTime: string;
  UpdatedAt: string;
  ProcessingStartTime?: string;
  ProcessingEndTime?: string;
  TaskFiles?: TaskFile[];
}

// 任务文件关联接口定义 (基于后端TaskFile实体)
export interface TaskFile {
  ErrorMessage?: string;
  TaskFileId: string;
  FileId: string;
  FileName: string;
  Status: "pending" | "processing" | "completed" | "failed";
  VisionResult?: string; // JSON格式的检测结果
  LlmResult?: string; // LLM生成的报告
  ProcessingStartTime?: string;
  ProcessingEndTime?: string;
  LogicalPath?: string;
}

// 文件上传响应
export interface FileUploadResponse {
  SuccessCount: number;
  FailedCount: number;
  SuccessFiles: FileEntity[];
  FailedFiles: any[];
}

// 项目文件树节点 (用于文件树显示)
export interface FileTreeNode {
  Id: string;
  Name: string;
  Type: "directory" | "file";
  ProjectId: string;
  Size?: number;
  FileType?: string;
  UploadDate?: string;
  Children?: FileTreeNode[];
  // 给前端用
  Path: string;
}

// 用户接口定义
export interface User {
  Id: string;
  Username: string;
  Email: string;
  Role: "admin" | "quality_inspector";
  Projects: string[];
  CreateTime: string;
  LastLoginTime: string;
  Status: "active" | "inactive";
}

// 请求参数接口
export interface CreateProjectRequest {
  ProjectName: string;
  Description?: string;
}

export interface CreateDirectoryRequest {
  Name: string;
  ParentDirectoryId?: string;
}

export interface CreateTaskRequest {
  Name: string;
  Description?: string;
  AlgorithmType: string;
  SelectedFiles: { FileId: string }[];
}

// 任务提交相关接口 (根据swagger定义)
export interface SelectedFile {
  FileId: string;
}

export interface TaskSubmitRequest {
  Name: string;
  Description?: string;
  AlgorithmType: string;
  SelectedFiles: SelectedFile[];
}

export interface TaskSubmitResponse {
  TaskId: string;
  Status: string;
  FileCount: number;
  Timestamp: string;
}

// 分页参数接口
export interface PaginationParams {
  page?: number;
  pageSize?: number;
  keyword?: string;
  category?: string;
}

// 任务状态枚举
export const TaskStatus = {
  PENDING: "pending",
  PROCESSING: "processing",
  COMPLETED: "completed",
  FAILED: "failed",
  CANCELLED: "cancelled",
} as const;

// 文件状态枚举
export const FileStatus = {
  UPLOADED: "uploaded",
  PROCESSING: "processing",
  COMPLETED: "completed",
  FAILED: "failed",
} as const;

// 算法类型选项
export const algorithmTypeOptions = [
  { label: "目标检测", value: "object-detection" },
  { label: "图像分类", value: "image-classification" },
  { label: "语义分割", value: "semantic-segmentation" },
];

// 文件类型支持
export const supportedFileTypes = ["jpg", "jpeg", "png", "gif", "bmp", "webp"];

// 项目类型选项
export const projectTypeOptions = [
  { label: "PCB检测", value: "PCB检测" },
  { label: "元件检测", value: "元件检测" },
  { label: "焊接检测", value: "焊接检测" },
  { label: "表面检测", value: "表面检测" },
];
