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
  Permission?: "OWNER" | "READ_ONLY" | "READ_WRITE";
}

// 目录接口定义 (基于后端Directory实体)
export interface Directory {
  Id: string; // UUID格式
  Name: string;
  ProjectId: string;
  ParentDirectoryId?: string;
  Path: string;
  Level: number;
  SortOrder?: number;
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
  IsArchived?: boolean;
}

// 报告接口定义
export interface Report {
  ReportId: string;
  TaskId: string;
  TaskName?: string; // 关联的任务名称
  ProjectId: string;
  UserId: string;
  ReportName: string;
  TotalFiles: number;
  ConfirmedFiles: number;
  TotalDefects: number;
  SevereDefects: number;
  NormalDefects: number;
  Status: "PENDING" | "COMPLETED" | "ARCHIVED";
  CreatedAt: string;
  UpdatedAt: string;
}

// 缺陷类型接口定义 (基于后端DefectType实体)
export interface DefectType {
  Code: string;
  Name: string;
  Color: string;
  SortOrder: number;
  Enabled: boolean;
}

// 缺陷记录接口定义 (基于后端DefectRecord实体)
export interface DefectRecord {
  DefectRecordId: string;
  TaskFileId: string;
  DefectName: string;
  Position: string;    // 算法计算的位置（如：左上角、中心等）
  Size: string;
  Grade: string;
  Remark: string;
  Geometry?: string;   // 标注区域的几何坐标 JSON
  CreatedAt?: string;
  UpdatedAt?: string;
}

// 任务文件关联接口定义 (基于后端TaskFile实体)
export interface TaskFile {
  ErrorMessage?: string;
  TaskFileId: string;
  FileId: string;
  FileName: string;
  Status: "pending" | "processing" | "completed" | "failed";
  ReviewStatus: "PENDING" | "CONFIRMED";
  VisionResult?: string; // JSON格式的检测结果
  ManualResult?: string; // 人工修改后的检测结果
  PlateQuality?: string; // 底片质量
  // 新增：底片信息字段
  FilmPixelValue?: string; // 底片像素值
  Resolution?: string;    // 分辨率
  Specification?: string; // 规格
  InspectionDate?: string; // 检验日期
  WeldId?: string;       // 焊口编号
  FilmNumber?: string;   // 片号
  FilmDensity?: string;  // 底片黑度
  Sensitivity?: string;  // 像质计灵敏度
  NormalizedSnr?: string; // 区域归一化信噪比
  // 新增：缺陷记录列表
  DefectRecords?: DefectRecord[];
  ProcessingStartTime?: string;
  ProcessingEndTime?: string;
  LogicalPath?: string;
  // 新增：焊缝底片方向矫正信息（推理时自动计算）
  CorrectionRotation?: number;  // 前端应用的旋转角度: 0 / 90 / 180 / -90
  CorrectionFlip?: boolean;     // 前端是否需要水平翻转
  // 新增：焊缝位置检测结果（B路径，location_0.pt模型检测）
  WeldLocation?: string;        // JSON数组字符串，每条含class/confidence/bbox/keypoints(12个关键点)
  // 新增：缺陷位置检测2结果（D路径，location_1.pt，仅存center_mark原点）
  DefectPosition?: string;      // JSON字符串，含origin_x/origin_y/positioning_type
}

// 文件上传响应
export interface FileUploadResponse {
  SuccessCount: number;
  FailedCount: number;
  SuccessFiles: FileEntity[];
  FailedFiles: any[];
}

export interface UploadConfigResponse {
  MaxFileSizeBytes: number;
  MaxTotalSizeBytes: number;
  BatchMaxFiles: number;
  BatchMaxBytes: number;
  BatchTimeoutBaseMs: number;
  BatchTimeoutMsPerMB: number;
  MaxRetries: number;
  AllowedImageTypes: string[];
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
  SortOrder?: number;
  // 给前端用
  Path: string;
}

// 用户接口定义
export interface User {
  userId: string;
  username: string;
  email: string;
  role: string;
  projects: string[];
  createTime: string;
  lastLoginTime: string;
  status: string;
  projectPermissions?: any[];
}

// 请求参数接口
export interface CreateProjectRequest {
  ProjectName: string;
  Description?: string;
}

export interface CreateDirectoryRequest {
  Name: string;
  ParentDirectoryId?: string;
  SortOrder?: number;
}

export interface UpdateDirectoryRequest {
  Name?: string;
  SortOrder?: number;
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
  SelectedFiles?: SelectedFile[];
  DirectoryIds?: string[];
  ProjectIds?: string[];
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
