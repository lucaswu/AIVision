import { useEffect, useMemo } from "react";
import { Routes, Route, Navigate, BrowserRouter } from "react-router-dom";
import { Layout, Menu, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { useLocation, useNavigate } from "react-router-dom";
import AppHeader from "./components/AppHeader";
import ProjectList from "./pages/ProjectList";
import UserManagement from "./pages/UserManagement";
import UserAddEdit from "./pages/UserAddEdit";
import ProjectDetail from "./pages/ProjectDetail";
import CreateProject from "./pages/CreateProject";
import Login from "./pages/Login";
import { rootSidebarItems } from "./utils/constans";
import { projectAPI } from "./utils/api";
import { useRequest } from "ahooks";
import { PROJECTS_UPDATED_EVENT } from "./utils/projectEvents";

const { Header, Sider, Content } = Layout;

// 路由守卫组件
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem("token");
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

function AppContent() {
  const location = useLocation();
  const navigate = useNavigate();

  const { data: projectsResponse, refresh: refreshProjects } = useRequest(() => projectAPI.getProjects(), {
    refreshDeps: [location.pathname],
  });

  useEffect(() => {
    const handleProjectsUpdated = () => {
      refreshProjects();
    };

    window.addEventListener(PROJECTS_UPDATED_EVENT, handleProjectsUpdated);
    return () => {
      window.removeEventListener(PROJECTS_UPDATED_EVENT, handleProjectsUpdated);
    };
  }, [refreshProjects]);

  const projects = useMemo(() => {
    return (projectsResponse?.Data || []).sort((a, b) => {
      return (
        new Date(b.CreateTime).getTime() - new Date(a.CreateTime).getTime()
      );
    });
  }, [projectsResponse]);

  // 获取当前选中的菜单项
  const getSelectedKeys = () => {
    const path = location.pathname;
    if (path.startsWith("/users")) return ["users"];
    if (path.startsWith("/projects")) return ["projects"];
    if (path.startsWith("/models")) return ["models"];
    return ["projects"];
  };

  // 处理菜单点击
  const handleMenuClick = ({ key }: { key: string }) => {
    if (key.startsWith("project-")) {
      const projectId = key.replace("project-", "");
      navigate(`/projects/${projectId}/files`);
    } else {
    navigate(`/${key}`);
    }
  };

  // 根据角色过滤菜单项
  const getMenuItems = () => {
    const role = localStorage.getItem("role");
    
    // 生成动态项目子菜单
    const projectSubItems = [
      { key: "projects", label: "全部项目" },
      ...projects.slice(0, 5).map(p => ({
        key: `project-${p.Id}`,
        label: p.Name,
      }))
    ];

    const menuItems = rootSidebarItems.map(group => {
      if (group.key === "projects-group") {
        return { ...group, children: projectSubItems };
      }
      return group;
    });

    if (role === "ADMIN") {
      return menuItems;
    }
    // 非管理员（质检员）过滤掉“系统管理”
    return menuItems.filter((item) => item.key !== "system-group");
  };

  // 检查是否在项目详情页面（不显示侧边栏）
  const isProjectDetailPage = location.pathname.match(/^\/projects\/\d+/);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <>
                <AppHeader />
                <Routes>
                  {/* 新增项目页面 - 需要侧边栏 */}
                  <Route
                    path="/projects/create"
                    element={
                      <Layout
                        style={{
                          height: "calc(100vh - 64px)",
                          overflow: "auto",
                        }}
                      >
                        <Sider width={160} style={{ background: "#fff" }}>
                          <Menu
                            mode="inline"
                            selectedKeys={["projects"]}
                            style={{ height: "100%", borderRight: 0 }}
                            items={getMenuItems()}
                            onClick={handleMenuClick}
                          />
                        </Sider>
                        <Layout style={{ height: "100%", overflow: "auto" }}>
                          <Content
                            style={{
                              padding: "24px",
                              margin: 0,
                              minHeight: "100%",
                              backgroundColor: "#f0f2f5",
                            }}
                          >
                            <CreateProject />
                          </Content>
                        </Layout>
                      </Layout>
                    }
                  />

        {/* ProjectDetail 独立路由，不包含侧边栏 */}
        <Route path="/projects/:id/*" element={<ProjectDetail />} />

        {/* 其他页面使用带侧边栏的布局 */}
        <Route
          path="/*"
          element={
                      <Layout
                        style={{
                          height: "calc(100vh - 64px)",
                          overflow: "auto",
                        }}
                      >
              <Sider width={160} style={{ background: "#fff" }}>
                <Menu
                  mode="inline"
                  selectedKeys={getSelectedKeys()}
                  style={{ height: "100%", borderRight: 0 }}
                            items={getMenuItems()}
                  onClick={handleMenuClick}
                />
              </Sider>
              <Layout style={{ height: "100%", overflow: "auto" }}>
                <Content
                  style={{
                    padding: "24px",
                    margin: 0,
                    minHeight: "100%",
                    backgroundColor: "#f0f2f5",
                  }}
                >
                  <Routes>
                    <Route
                      path="/"
                      element={<Navigate to="/projects" replace />}
                    />
                              <Route
                                path="/projects"
                                element={<ProjectList />}
                              />
                              <Route
                                path="/users"
                                element={<UserManagement />}
                              />
                              <Route
                                path="/users/add"
                                element={<UserAddEdit />}
                              />
                              <Route
                                path="/users/edit/:id"
                                element={<UserAddEdit />}
                              />
                  </Routes>
                </Content>
              </Layout>
            </Layout>
                    }
                  />
                </Routes>
              </>
            </ProtectedRoute>
          }
        />
      </Routes>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ConfigProvider locale={zhCN}>
        <AppContent />
      </ConfigProvider>
    </BrowserRouter>
  );
}

export default App;
