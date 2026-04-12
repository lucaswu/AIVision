import { useState } from "react";
import {
  Routes,
  Route,
  Navigate,
  useParams,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { LeftOutlined, RightOutlined } from "@ant-design/icons";
import { Layout, Menu, Typography, Card, Spin, Alert, Button, Tooltip } from "antd";
import { useRequest } from "ahooks";
import { projectSidebarItems } from "../utils/constans";
import { projectAPI } from "../utils/api";
import { FilesPage, TasksPage, ReportsPage } from "./project-detail";

const { Sider, Content } = Layout;
const { Title } = Typography;

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [isProjectSidebarCollapsed, setIsProjectSidebarCollapsed] = useState(false);

  const projectSidebarWidth = 150;
  const collapsedProjectSidebarWidth = 24;
  const actualProjectSidebarWidth = isProjectSidebarCollapsed
    ? collapsedProjectSidebarWidth
    : projectSidebarWidth;

  // 获取项目信息
  const {
    data: projectsResponse,
    loading,
    error,
  } = useRequest(() => projectAPI.getProjects(), {
    refreshDeps: [],
  });

  const project = projectsResponse?.Data.find((project) => project.Id === id);

  // 加载状态
  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  // 错误状态
  if (error || !project) {
    return (
      <div style={{ padding: 24 }}>
        <Card>
          <Alert
            message="项目加载失败"
            description={error?.message || "项目不存在或已被删除"}
            type="error"
            showIcon
          />
        </Card>
      </div>
    );
  }

  // 获取当前选中的菜单项
  const getSelectedKeys = () => {
    const path = location.pathname;
    if (path.includes("/files")) return ["files"];
    if (path.includes("/tasks")) return ["tasks"];
    if (path.includes("/reports")) return ["reports"];
    return ["files"]; // 默认选中文件管理
  };

  // 处理菜单点击
  const handleMenuClick = ({ key }: { key: string }) => {
    if (key === "back") {
      navigate("/projects");
    } else {
      navigate(`/projects/${id}/${key}`);
    }
  };

  return (
    <Layout style={{ height: "calc(100vh - 64px)", overflow: "hidden" }}>
      <Sider
        width={actualProjectSidebarWidth}
        style={{
          background: isProjectSidebarCollapsed ? "#fafafa" : "#fff",
          borderRight: "1px solid #f0f0f0",
          overflow: "hidden",
          transition: "all 0.2s ease",
          flex: `0 0 ${actualProjectSidebarWidth}px`,
          maxWidth: actualProjectSidebarWidth,
          minWidth: actualProjectSidebarWidth,
        }}
      >
        {isProjectSidebarCollapsed ? (
          <div
            style={{
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Tooltip title="展开项目列表" placement="right">
              <Button
                type="text"
                size="small"
                icon={<RightOutlined />}
                onClick={() => setIsProjectSidebarCollapsed(false)}
                style={{
                  width: 18,
                  height: 72,
                  padding: 0,
                  borderRadius: 999,
                  color: "#8c8c8c",
                }}
              />
            </Tooltip>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                padding: "8px 8px 0 8px",
                flexShrink: 0,
              }}
            >
              <Tooltip title="收起项目列表" placement="right">
                <Button
                  type="text"
                  size="small"
                  icon={<LeftOutlined />}
                  onClick={() => setIsProjectSidebarCollapsed(true)}
                  style={{
                    color: "#8c8c8c",
                    width: 24,
                    minWidth: 24,
                    height: 24,
                    padding: 0,
                    borderRadius: 12,
                  }}
                />
              </Tooltip>
            </div>
            <Menu
              mode="inline"
              selectedKeys={getSelectedKeys()}
              style={{ height: "100%", borderRight: 0 }}
              items={projectSidebarItems}
              onClick={handleMenuClick}
            />
          </div>
        )}
      </Sider>

      <Layout style={{ height: "100%", overflow: "hidden" }}>
        <Content
          style={{
            backgroundColor: "#f0f2f5",
            padding: 0,
            margin: 0,
            height: "100%",
            overflow: "hidden",
          }}
        >
          <Routes>
            <Route path="/" element={<Navigate to="files" replace />} />
            <Route
              path="/files"
              element={<FilesPage projectId={id!} projectName={project.Name} permission={project.Permission} />}
            />
            <Route
              path="/tasks"
              element={<TasksPage projectId={id!} projectName={project.Name} permission={project.Permission} />}
            />
            <Route
              path="/reports"
              element={
                <ReportsPage
                  projectId={id!}
                  projectName={project.Name}
                  permission={project.Permission}
                  projectSidebarCollapsed={isProjectSidebarCollapsed}
                  onProjectSidebarCollapseChange={setIsProjectSidebarCollapsed}
                />
              }
            />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
