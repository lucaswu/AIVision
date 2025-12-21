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
  TaskSubmitResponse,
  FileUploadResponse,
  FileTreeNode,
} from "./data";

import { addPathToFileTreeNodes } from "./fileTreeUtils"; // 分页参数接口
export interface PaginationParams {
  page?: number;
  pageSize?: number;
  keyword?: string;
  category?: string;
}

// API 基础配置
const API_BASE_URL = "";

// 默认用户ID (实际应该从认证系统获取)
export const getUserId = () => localStorage.getItem("userId") || "user001";

// 通用请求函数
async function request<T = any>(
  url: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    const userId = getUserId();
    // 添加调试日志
    console.log("API请求详情:", {
      url: `${API_BASE_URL}${url}`,
      method: options.method || "GET",
      headers: {
        "Content-Type": "application/json",
        "user-id": userId,
        ...options.headers,
      },
    });

    const response = await fetch(`${API_BASE_URL}${url}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "user-id": userId,
        ...options.headers,
      },
    });

    const result = await response.json();

    // 添加响应日志
    console.log("API响应详情:", {
      url: `${API_BASE_URL}${url}`,
      status: response.status,
      result,
    });

    if (result.Code !== 200) {
      // 根据不同错误码提供更具体的错误信息
      let errorMessage = result.Message || "请求失败";

      if (result.Code === 404) {
        if (url.includes("/tasks/list")) {
          errorMessage = `项目不存在或您没有访问权限。请检查项目ID是否正确。项目ID: ${
            options.headers?.["project-id"] || "未提供"
          }`;
        } else if (url.includes("/projects/")) {
          errorMessage = `项目不存在。请检查项目ID是否正确。`;
        } else {
          errorMessage = `资源不存在: ${errorMessage}`;
        }
      } else if (result.Code === 403) {
        errorMessage = `访问被拒绝: ${errorMessage}`;
      } else if (result.Code === 400) {
        errorMessage = `请求参数错误: ${errorMessage}`;
      }

      message.error(errorMessage);
      throw new Error(errorMessage);
    }

    return result;
  } catch (error) {
    console.error("API请求错误:", error);
    if (error instanceof TypeError) {
      message.error("网络请求失败，请检查网络连接");
    }
    throw error;
  }
}

// 文件上传专用请求函数
async function uploadRequest(
  url: string,
  formData: FormData,
  headers: Record<string, string> = {}
): Promise<ApiResponse<FileUploadResponse>> {
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
    if (error instanceof Error && !error.message.includes("上传失败")) {
      message.error("文件上传失败，请检查网络连接");
    }
    throw error;
  }
}

// 项目相关API
export const projectAPI = {
  // 获取项目列表
  getProjects: () => request<Project[]>("/api/v1/projects/list"),

  // 获取项目详情
  getProject: (projectId: string) =>
    request<Project>(`/api/v1/projects/${projectId}`),

  // 创建项目
  createProject: (data: CreateProjectRequest) =>
    request<Project>("/api/v1/projects/create", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // 更新项目 (推断的接口)
  updateProject: (projectId: string, data: Partial<CreateProjectRequest>) =>
    request<Project>(`/api/v1/projects/${projectId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // 删除项目 (推断的接口)
  deleteProject: (projectId: string) =>
    request<void>(`/api/v1/projects/${projectId}`, {
      method: "DELETE",
    }),

  // 获取项目文件树
  getProjectFiles: async (projectId: string) => {
    const response = await request<FileTreeNode[]>(
      `/api/v1/projects/${projectId}/files`,
      {
        headers: {
          "project-id": projectId,
        },
      }
    );

    // 自动添加Path属性
    return {
      ...response,
      Data: addPathToFileTreeNodes(response.Data),
    };
  },
};

// 目录相关API
export const directoryAPI = {
  // 创建目录
  createDirectory: (projectId: string, data: CreateDirectoryRequest) =>
    request<Directory>("/api/v1/directories/create", {
      method: "POST",
      headers: {
        "project-id": projectId,
      },
      body: JSON.stringify(data),
    }),

  // 获取目录列表 (推断的接口)
  getDirectories: (projectId: string) =>
    request<Directory[]>("/api/v1/directories/list", {
      headers: {
        "project-id": projectId,
      },
    }),

  // 删除目录 (推断的接口)
  deleteDirectory: (directoryId: string, projectId: string) =>
    request<void>(`/api/v1/directories/${directoryId}`, {
      method: "DELETE",
      headers: {
        "project-id": projectId,
      },
    }),
};

// 文件相关API
export const fileAPI = {
  // 获取项目文件树
  getFiles: (projectId: string) => projectAPI.getProjectFiles(projectId),

  // 多文件上传
  uploadFiles: (projectId: string, directoryId: string, files: FileList) => {
    const formData = new FormData();
    Array.from(files).forEach((file) => {
      formData.append("File", file);
    });

    return uploadRequest("/api/v1/files/upload", formData, {
      "project-id": projectId,
      "directory-id": directoryId,
    });
  },

  // 删除文件 (推断的接口)
  deleteFile: (fileId: string, projectId: string) =>
    request<void>(`/api/v1/files/${fileId}`, {
      method: "DELETE",
      headers: {
        "project-id": projectId,
      },
    }),

  // 获取文件详情 (推断的接口)
  getFile: (fileId: string, projectId: string) =>
    request<FileEntity>(`/api/v1/files/${fileId}`, {
      headers: {
        "project-id": projectId,
      },
    }),
};

// 任务相关API
export const taskAPI = {
  // 获取任务列表 - 使用统一的/api/v1/tasks/list接口
  getTasks: async (projectId: string, params?: PaginationParams) => {
    // 验证projectId是否提供
    if (!projectId) {
      const error = "项目ID不能为空";
      message.error(error);
      throw new Error(error);
    }

    // 验证projectId格式（UUID格式）
    const uuidRegex =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(projectId)) {
      const error = `项目ID格式不正确: ${projectId}`;
      message.error(error);
      throw new Error(error);
    }

    console.log("获取任务列表 - 请求参数:", {
      projectId,
      userId: getUserId(),
      params,
    });

    return request<any>("/api/v1/tasks/list", {
      headers: {
        "project-id": projectId,
        "user-id": getUserId(),
      },
    });
  },

  // 提交检测任务 - 使用/api/v1/tasks/submit接口
  createTask: (projectId: string, data: TaskSubmitRequest) => {
    return request<TaskSubmitResponse>("/api/v1/tasks/submit", {
      method: "POST",
      headers: {
        "project-id": projectId,
        "user-id": getUserId(),
      },
      body: JSON.stringify(data),
    });
  },

  // 获取任务详情 (推断的接口)
  getTask: (taskId: string, projectId: string) => {
    return request<Task>(`/api/v1/tasks/${taskId}`, {
      headers: {
        "project-id": projectId,
        "user-id": getUserId(),
      },
    });
  },

  // 删除任务 (推断的接口)
  deleteTask: (taskId: string, projectId: string) => {
    return request<void>(`/api/v1/tasks/${taskId}`, {
      method: "DELETE",
      headers: {
        "project-id": projectId,
        "user-id": getUserId(),
      },
    });
  },

  // 更新任务 (推断的接口)
  updateTask: (
    taskId: string,
    projectId: string,
    data: Partial<CreateTaskRequest>
  ) => {
    return request<Task>(`/api/v1/tasks/${taskId}`, {
      method: "PUT",
      headers: {
        "project-id": projectId,
        "user-id": getUserId(),
      },
      body: JSON.stringify(data),
    });
  },
};

// 用户相关API (推断的接口)
export const userAPI = {
  // 获取用户列表
  getUsers: (params?: PaginationParams) => {
    const { page = 1, pageSize = 10, ...rest } = params || {};
    // 后端分页从 0 开始，前端从 1 开始，需要减 1
    const query = new URLSearchParams({
      page: (page - 1).toString(),
      size: pageSize.toString(),
      ...rest,
    } as any).toString();
    return request<any>(`/api/v1/users?${query}`);
  },

  // 获取用户详情
  getUser: (userId: string) => request<User>(`/api/v1/users/${userId}`),

  // 创建用户
  createUser: (data: Partial<User>) =>
    request<User>("/api/v1/users", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // 更新用户
  updateUser: (userId: string, data: Partial<User>) =>
    request<User>(`/api/v1/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // 删除用户
  deleteUser: (userId: string) =>
    request<void>(`/api/v1/users/${userId}`, {
      method: "DELETE",
    }),

  // 获取当前用户信息
  getCurrentUser: () => request<User>("/api/v1/users/profile"),

  // 用户登录
  login: (data: any) =>
    request<any>("/api/v1/users/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// 检测结果相关API - 复用/api/v1/tasks/list接口
export const resultAPI = {
  // 获取检测结果列表 - 使用/api/v1/tasks/list接口（报告列表实际就是已完成的任务列表）
  getResults: async (
    projectId: string,
    params?: PaginationParams & { keyword?: string; status?: string }
  ) => {
    return request<any>("/api/v1/tasks/list", {
      headers: {
        "project-id": projectId,
        "user-id": getUserId(),
      },
    });
  },
};
