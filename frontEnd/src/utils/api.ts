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
  CreateTaskRequest,
  TaskSubmitRequest,
  Report,
  TaskStatus,
  FileTreeNode,
  TaskFile,
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
async function uploadRequest(
  url: string,
  formData: FormData,
  headers: Record<string, string> = {}
): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}${url}`, {
      method: "POST",
      headers: {
        "user-id": getUserId(),
        ...headers,
      },
      body: formData,
    });

    const result = await response.json();

    if (result.Code !== 200) {
      message.error(result.Message || "上传失败");
      throw new Error(result.Message || "上传失败");
    }

    return result;
  } catch (error) {
    console.error("文件上传错误:", error);
    throw error;
  }
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
  deleteDirectory: (directoryId: string, projectId: string) =>
    request<void>(`/api/v1/directories/${directoryId}`, {
      method: "DELETE",
      headers: { "project-id": projectId },
    }),
};

// 文件相关API
export const fileAPI = {
  getFiles: (projectId: string) => projectAPI.getProjectFiles(projectId),
  uploadFiles: (projectId: string, directoryId: string, files: FileList) => {
    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append("File", file));
    return uploadRequest("/api/v1/files/upload", formData, {
      "project-id": projectId,
      "directory-id": directoryId,
    });
  },
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
  reviewFile: (taskFileId: string, data: { ManualResult: string; PlateQuality: string }) =>
    request<void>(`/api/v1/reports/files/${taskFileId}/review`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  batchConfirmFiles: (taskFileIds: string[]) =>
    request<void>("/api/v1/reports/files/batch-confirm", {
      method: "POST",
      body: JSON.stringify(taskFileIds),
    }),
  archiveReport: (reportId: string, archived: boolean) =>
    request<void>(`/api/v1/reports/${reportId}/archive?archived=${archived}`, {
      method: "PUT",
    }),
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
};
