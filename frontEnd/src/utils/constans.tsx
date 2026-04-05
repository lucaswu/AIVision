import {
  ProjectOutlined,
  SettingOutlined,
  UserOutlined,
  CloudServerOutlined,
  FolderOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";

export const rootSidebarItems = [
  {
    key: "projects-group",
    label: "项目管理",
    icon: <ProjectOutlined />,
    children: [
      {
        key: "projects",
        label: "全部项目",
      },
    ],
  },
  {
    key: "system-group",
    label: "系统管理",
    icon: <SettingOutlined />,
    children: [
  {
    key: "users",
    label: "用户管理",
        icon: <UserOutlined />,
  },
      {
        key: "models",
        label: "模型管理",
        icon: <CloudServerOutlined />,
      },
    ],
  },
];

export const projectSidebarItems = [
  {
    key: "back",
    label: "← 返回项目列表",
  },
  {
    key: "files",
    label: "文件管理",
  },
  {
    key: "tasks",
    label: "任务管理",
  },
  {
    key: "reports",
    label: "报告管理",
  },
];

// 用户下拉菜单
export const userMenuItems: MenuProps["items"] = [
  {
    key: "profile",
    icon: <UserOutlined />,
    label: "个人资料",
  },
  {
    key: "settings",
    icon: <SettingOutlined />,
    label: "设置",
  },
  {
    type: "divider",
  },
  {
    key: "logout",
    icon: <LogoutOutlined />,
    label: "退出",
  },
];

export const filePreviewPath = "/api/v1/files/preview";
export const fileThumbnailPath = "/api/v1/files/thumbnail";

