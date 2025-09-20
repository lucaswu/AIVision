import {
  UserOutlined,
  SettingOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";

export const rootSidebarItems = [
  {
    key: "projects",
    label: "项目管理",
  },
  {
    key: "users",
    label: "用户管理",
  },
  // {
  //   key: "settings",
  //   label: "设置",
  // },
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
