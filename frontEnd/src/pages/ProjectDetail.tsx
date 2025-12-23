import {
  Routes,
  Route,
  Navigate,
  useParams,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { Layout, Menu, Typography, Card, Spin, Alert } from "antd";
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
    <Layout style={{ height: "100vh", overflow: "hidden" }}>
      <Sider
        width={200}
        style={{ background: "#fff", borderRight: "1px solid #f0f0f0" }}
      >
        <Menu
          mode="inline"
          selectedKeys={getSelectedKeys()}
          style={{ height: "100%", borderRight: 0 }}
          items={projectSidebarItems}
          onClick={handleMenuClick}
        />
      </Sider>

      <Layout style={{ height: "100vh", overflow: "hidden" }}>
        <Content
          style={{
            backgroundColor: "#f0f2f5",
            padding: 24,
            margin: 0,
            height: "100%",
            overflow: "auto",
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
                <ReportsPage projectId={id!} projectName={project.Name} permission={project.Permission} />
              }
            />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
