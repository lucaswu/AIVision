import { message } from "antd";
import {
  Project,
  User,
  Task,
  Directory,
  FileEntity,
  ApiResponse,
  CreateProjectRequest,
  CreateDirectoryRequest,
  UpdateDirectoryRequest,
  CreateTaskRequest,
  TaskSubmitRequest,
  Report,
  TaskStatus,
  FileTreeNode,
  TaskFile,
  UploadConfigResponse,
} from "./data";

import { addPathToFileTreeNodes } from "./fileTreeUtils";

// 分页参数接口
export interface PaginationParams {
  page?: number;
  pageSize?: number;
  keyword?: string;
  category?: string;
}

// API 基础配置
const API_BASE_URL = "";

// 默认用户ID (实际应该从认证系统获取)
export const getUserId = () => localStorage.getItem("userId") || "admin-001";

// 通用请求函数
async function request<T = any>(
  url: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    const userId = getUserId();
    const response = await fetch(`${API_BASE_URL}${url}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "user-id": userId,
        ...options.headers,
      },
    });

    const result = await response.json();

    if (result.Code !== 200) {
      let errorMessage = result.Message || "请求失败";
      message.error(errorMessage);
      throw new Error(errorMessage);
    }

    return result;
  } catch (error) {
    console.error("API请求错误:", error);
    throw error;
  }
}

// 文件上传专用请求函数
interface UploadProgressInfo {
  loaded: number;
  total: number;
  percent: number;
}

interface UploadRequestOptions {
  onProgress?: (info: UploadProgressInfo) => void;
  // 静默模式：不在此处弹出 message.error，由调用方统一汇总（用于分批上传避免逐条刷屏）
  silent?: boolean;
  // 超时（毫秒）。0/未设表示不超时。设置后，请求在读取文件体/网络任一阶段卡住超过该时长会 abort 并 reject，
  // 避免某次请求永久挂起导致整个分批上传停滞。
  timeoutMs?: number;
  uploadSessionId?: string;
  uploadKeys?: string[];
}

async function uploadRequest(
  url: string,
  formData: FormData,
  headers: Record<string, string> = {},
  options: UploadRequestOptions = {}
): Promise<any> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${url}`, true);
    if (options.timeoutMs && options.timeoutMs > 0) {
      xhr.timeout = options.timeoutMs;
    }
    xhr.setRequestHeader("user-id", getUserId());
    if (options.uploadSessionId) {
      xhr.setRequestHeader("upload-session-id", options.uploadSessionId);
    }

    Object.entries(headers).forEach(([key, value]) => {
      xhr.setRequestHeader(key, value);
    });

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !options.onProgress) return;
      options.onProgress({
        loaded: event.loaded,
        total: event.total,
        percent: event.total > 0 ? (event.loaded / event.total) * 100 : 0,
      });
    };

    xhr.onload = () => {
      try {
        const result = JSON.parse(xhr.responseText || "{}");

        if (xhr.status < 200 || xhr.status >= 300) {
          const errorMessage = result.Message || "上传失败";
          if (!options.silent) message.error(errorMessage);
          reject(new Error(errorMessage));
          return;
        }

        if (result.Code !== 200) {
          const errorMessage = result.Message || "上传失败";
          if (!options.silent) message.error(errorMessage);
          reject(new Error(errorMessage));
          return;
        }

        resolve(result);
      } catch (error) {
        console.error("文件上传响应解析失败:", error);
        const parseError = new Error("上传响应解析失败");
        if (!options.silent) message.error(parseError.message);
        reject(parseError);
      }
    };

    xhr.onerror = () => {
      const networkError = new Error("上传失败，请检查网络连接");
      console.error("文件上传错误:", networkError);
      if (!options.silent) message.error(networkError.message);
      reject(networkError);
    };

    xhr.ontimeout = () => {
      const timeoutError = new Error("上传超时，请重试");
      console.error("文件上传超时:", timeoutError);
      if (!options.silent) message.error(timeoutError.message);
      reject(timeoutError);
    };

    xhr.send(formData);
  }).catch((error) => {
    console.error("文件上传错误:", error);
    throw error;
  });
}

// 项目相关API
export const projectAPI = {
  getProjects: () => request<Project[]>("/api/v1/projects/list"),
  getProject: (projectId: string) => request<Project>(`/api/v1/projects/${projectId}`),
  createProject: (data: CreateProjectRequest) =>
    request<Project>("/api/v1/projects/create", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateProject: (projectId: string, data: Partial<CreateProjectRequest>) =>
    request<Project>(`/api/v1/projects/${projectId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteProject: (projectId: string) =>
    request<void>(`/api/v1/projects/${projectId}`, {
      method: "DELETE",
    }),
  getProjectFiles: async (projectId: string) => {
    const response = await request<FileTreeNode[]>(`/api/v1/projects/${projectId}/files`, {
      headers: { "project-id": projectId },
    });
    return { ...response, Data: addPathToFileTreeNodes(response.Data) };
  },
};

// 目录相关API
export const directoryAPI = {
  createDirectory: (projectId: string, data: CreateDirectoryRequest) =>
    request<Directory>("/api/v1/directories/create", {
      method: "POST",
      headers: { "project-id": projectId },
      body: JSON.stringify(data),
    }),
  updateDirectory: (directoryId: string, projectId: string, data: UpdateDirectoryRequest) =>
    request<void>(`/api/v1/directories/${directoryId}`, {
      method: "PUT",
      headers: { "project-id": projectId },
      body: JSON.stringify(data),
    }),
  deleteDirectory: (directoryId: string, projectId: string) =>
    request<void>(`/api/v1/directories/${directoryId}`, {
      method: "DELETE",
      headers: { "project-id": projectId },
    }),
};

// 文件相关API
export const fileAPI = {
  getFiles: (projectId: string) => projectAPI.getProjectFiles(projectId),
  uploadFiles: (
    projectId: string,
    directoryId: string,
    files: File[],
    options: UploadRequestOptions = {}
  ) => {
    const formData = new FormData();
    files.forEach((file, index) => {
      // 第三参数指定 multipart 文件名：剥离 webkitRelativePath 路径，仅保留文件名。
      // 注意：不要用 new File([file], name) 来改名——那会复制文件字节进内存，
      // 大目录(成百上千个文件/数 GB)上传时会撑爆浏览器标签页内存导致卡死。
      const fileName = (file.name || "").split("/").pop() || file.name;
      formData.append("File", file, fileName);
      formData.append("UploadKey", options.uploadKeys?.[index] || "");
    });
    return uploadRequest("/api/v1/files/upload", formData, {
      "project-id": projectId,
      "directory-id": directoryId,
    }, options);
  },
  getUploadConfig: () => request<UploadConfigResponse>("/api/v1/files/upload-config"),
  deleteFile: (fileId: string, projectId: string) =>
    request<void>(`/api/v1/files/${fileId}`, {
      method: "DELETE",
      headers: { "project-id": projectId },
    }),
};

// 任务相关API
export const taskAPI = {
  getTasks: async (projectId: string) => {
    return request<any>("/api/v1/tasks/list", {
      headers: { "project-id": projectId },
    });
  },
  createTask: (projectId: string, data: TaskSubmitRequest) => {
    return request<any>("/api/v1/tasks/submit", {
      method: "POST",
      headers: { "project-id": projectId },
      body: JSON.stringify(data),
    });
  },
  restartTask: (taskId: string, projectId: string) => {
    return request<void>(`/api/v1/tasks/${taskId}/restart`, {
      method: "POST",
      headers: { "project-id": projectId },
    });
  },
  deleteTask: (taskId: string, projectId: string) => {
    return request<void>(`/api/v1/tasks/${taskId}`, {
      method: "DELETE",
      headers: { "project-id": projectId },
    });
  },
  updateTask: (taskId: string, projectId: string, data: Partial<CreateTaskRequest>) => {
    return request<Task>(`/api/v1/tasks/${taskId}`, {
      method: "PUT",
      headers: { "project-id": projectId },
      body: JSON.stringify(data),
    });
  },
};

// 报告相关API
export const reportAPI = {
  getReports: (projectId: string) =>
    request<Report[]>("/api/v1/reports/list", {
      headers: { "project-id": projectId },
    }),
  getReportDetail: (taskId: string) =>
    request<Report>(`/api/v1/reports/${taskId}/detail`),
  getReportFiles: (taskId: string, status: "all" | "has_defects" | "no_defects" = "all") =>
    request<TaskFile[]>(`/api/v1/reports/${taskId}/files?status=${status}`),
  reviewFile: (taskFileId: string, data: {
    ManualResult: string;
    PlateQuality: string;
    FilmPixelValue?: string;
    Resolution?: string;
    Specification?: string;
    InspectionDate?: string;
    WeldId?: string;
    FilmNumber?: string;
    FilmDensity?: string;
    Sensitivity?: string;
    NormalizedSnr?: string;
  }) =>
    request<void>(`/api/v1/reports/files/${taskFileId}/review`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  batchConfirmFiles: (taskFileIds: string[]) =>
    request<void>("/api/v1/reports/files/batch-confirm", {
      method: "POST",
      body: JSON.stringify(taskFileIds),
    }),
  updateFileLocation: (taskFileId: string, data: { WeldLocation?: string; DefectPosition?: string }) =>
    request<void>(`/api/v1/reports/files/${taskFileId}/location`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  archiveReport: (reportId: string, archived: boolean) =>
    request<void>(`/api/v1/reports/${reportId}/archive?archived=${archived}`, {
      method: "PUT",
    }),
  downloadReport: (reportId: string) => `/api/v1/reports/${reportId}/download`,
};

// 历史遗留兼容：检测结果相关API (内部复用 reportAPI)
export const resultAPI = {
  getResults: async (projectId: string, params?: any) => {
    const response = await reportAPI.getReports(projectId);
    // 适配旧版 ResultsPage 预期的数据结构
    return {
      ...response,
      Data: {
        Tasks: response.Data || [],
        TotalCount: response.Data?.length || 0,
      },
    };
  },
};

// 用户相关API
export const userAPI = {
  getUsers: (params?: PaginationParams) => {
    const { page = 1, pageSize = 10, ...rest } = params || {};
    const query = new URLSearchParams({ page: (page - 1).toString(), size: pageSize.toString(), ...rest } as any).toString();
    return request<any>(`/api/v1/users?${query}`);
  },
  getUser: (userId: string) => request<User>(`/api/v1/users/${userId}`),
  createUser: (data: Partial<User>) =>
    request<User>("/api/v1/users", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateUser: (userId: string, data: Partial<User>) =>
    request<User>(`/api/v1/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteUser: (userId: string) =>
    request<void>(`/api/v1/users/${userId}`, {
      method: "DELETE",
    }),
  login: (data: any) =>
    request<any>("/api/v1/users/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  ssoJwtLogin: (data: { token: string }) =>
    request<any>("/api/v1/users/sso-login-jwt", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// 缺陷类型相关API
export const defectTypeAPI = {
  getDefectTypes: () => request<any[]>("/api/v1/defect-types"),
};

// 缺陷记录相关API
export const defectRecordAPI = {
  getByTaskFileId: (taskFileId: string) =>
    request<any[]>(`/api/v1/defect-records/task-file/${taskFileId}`),
  create: (data: any) =>
    request<any>("/api/v1/defect-records", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  createBatch: (data: any[]) =>
    request<any>("/api/v1/defect-records/batch", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (defectRecordId: string, data: any) =>
    request<any>(`/api/v1/defect-records/${defectRecordId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  replace: (taskFileId: string, data: any[]) =>
    request<any>(`/api/v1/defect-records/task-file/${taskFileId}/replace`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  delete: (defectRecordId: string) =>
    request<void>(`/api/v1/defect-records/${defectRecordId}`, {
      method: "DELETE",
    }),
  deleteByTaskFileId: (taskFileId: string) =>
    request<void>(`/api/v1/defect-records/task-file/${taskFileId}`, {
      method: "DELETE",
    }),
};

// 训练数据相关API
export const trainingDataAPI = {
  getSummary: (projectId: string) =>
    request<any>(`/api/v1/training-data/summary?projectId=${projectId}`),
  getDataSources: (projectId: string) =>
    request<any[]>(`/api/v1/training-data/sources?projectId=${projectId}`),
  uploadDataSource: (projectId: string, name: string, files: File[]) => {
    const formData = new FormData();
    formData.append("name", name);
    files.forEach((file) => formData.append("files", file));
    return uploadRequest(`/api/v1/training-data/sources?projectId=${projectId}`, formData);
  },
  deleteDataSource: (projectId: string, sourceId: string) =>
    request<void>(`/api/v1/training-data/sources/${sourceId}?projectId=${projectId}`, {
      method: "DELETE",
    }),
  getDatasets: (projectId: string) =>
    request<any[]>(`/api/v1/training-data/datasets?projectId=${projectId}`),
  createDataset: (projectId: string, data: any) =>
    request<any>(`/api/v1/training-data/datasets?projectId=${projectId}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteDataset: (projectId: string, datasetId: string) =>
    request<void>(`/api/v1/training-data/datasets/${datasetId}?projectId=${projectId}`, {
      method: "DELETE",
    }),
};

export interface OcrRecognizeResult {
  text: string;
  confidence: number;
  raw_results: { text: string; confidence: number }[];
}

export interface RegionSnrResult {
  ok: boolean;
  status: "ok" | "error";
  result_code: number;
  result_name: string;
  message: string;
  snr_m: number | null;
  snr_n: number | null;
  sr_b_um: number;
  gray_mean: number | null;
  gray_std: number | null;
  width: number;
  height: number;
  area_pixels: number;
  area_limit_pixels: number;
  timings_ms: Record<string, number>;
}

// OCR 识别API
export const ocrAPI = {
  recognizeRegion: async (
    base64WithPrefix: string,
    taskId?: string,
    fieldName?: string,
  ): Promise<OcrRecognizeResult> => {
    const base64 = base64WithPrefix.startsWith('data:')
      ? base64WithPrefix.split(',')[1]
      : base64WithPrefix;
    const body: Record<string, string> = { base64 };
    if (taskId) body['task_id'] = taskId;
    if (fieldName) body['field_name'] = fieldName;
    const result = await request<OcrRecognizeResult>(
      '/api/v1/ocr/recognize',
      { method: 'POST', body: JSON.stringify(body) }
    );
    return result.Data;
  },
};

export const snrAPI = {
  computeRegion: async (
    base64WithPrefix: string,
    taskId?: string,
    fieldName?: string,
  ): Promise<RegionSnrResult> => {
    const base64 = base64WithPrefix.startsWith('data:')
      ? base64WithPrefix.split(',')[1]
      : base64WithPrefix;
    const body: Record<string, string> = { base64 };
    if (taskId) body['task_id'] = taskId;
    if (fieldName) body['field_name'] = fieldName;
    const result = await request<RegionSnrResult>(
      '/api/v1/ocr/region-snr',
      { method: 'POST', body: JSON.stringify(body) }
    );
    return result.Data;
  },
};
