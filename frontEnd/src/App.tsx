import { Routes, Route, Navigate, BrowserRouter } from "react-router-dom";
import { Layout, Menu, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { useLocation, useNavigate } from "react-router-dom";
import AppHeader from "./components/AppHeader";
import ProjectList from "./pages/ProjectList";
import UserManagement from "./pages/UserManagement";
import ProjectDetail from "./pages/ProjectDetail";
import { rootSidebarItems } from "./utils/constans";

const { Header, Sider, Content } = Layout;

function AppContent() {
  const location = useLocation();
  const navigate = useNavigate();

  // 获取当前选中的菜单项
  const getSelectedKeys = () => {
    const path = location.pathname;
    if (path.startsWith("/users")) return ["users"];
    if (path.startsWith("/projects")) return ["projects"];
    return ["projects"];
  };

  // 处理菜单点击
  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(`/${key}`);
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
      <AppHeader />
      <Routes>
        {/* ProjectDetail 独立路由，不包含侧边栏 */}
        <Route path="/projects/:id/*" element={<ProjectDetail />} />

        {/* 其他页面使用带侧边栏的布局 */}
        <Route
          path="/*"
          element={
            <Layout style={{ height: "calc(100vh - 64px)", overflow: "auto" }}>
              <Sider width={200} style={{ background: "#fff" }}>
                <Menu
                  mode="inline"
                  selectedKeys={getSelectedKeys()}
                  style={{ height: "100%", borderRight: 0 }}
                  items={rootSidebarItems}
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
                    <Route path="/projects" element={<ProjectList />} />
                    <Route path="/users" element={<UserManagement />} />
                  </Routes>
                </Content>
              </Layout>
            </Layout>
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
