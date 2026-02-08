import { useMemo } from "react";
import {
  Routes,
  Route,
  Navigate,
  useParams,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { Layout, Menu, Card, Spin, Alert, Dropdown, Typography, Space, Button } from "antd";
import {
  DatabaseOutlined,
  TagsOutlined,
  ExperimentOutlined,
  DeploymentUnitOutlined,
  DownOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import { projectAPI } from "@/utils/api";
import DataManagementPage from "./DataManagementPage";

const { Sider, Content } = Layout;
const { Text } = Typography;

const trainingMenuItems = [
  {
    key: "data",
    label: "数据管理",
    icon: <DatabaseOutlined />,
  },
  {
    key: "labeling",
    label: "数据标注",
    icon: <TagsOutlined />,
  },
  {
    key: "experiments",
    label: "实验管理",
    icon: <ExperimentOutlined />,
  },
  {
    key: "models",
    label: "模型管理",
    icon: <DeploymentUnitOutlined />,
  },
];

const Placeholder = ({ title }: { title: string }) => (
  <div style={{ padding: 24 }}>
    <Card
      variant="borderless"
      style={{ borderRadius: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}
    >
      <Text type="secondary">{title}功能待开发</Text>
    </Card>
  </div>
);

export default function TrainingProjectLayout() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const { data: projectsResponse, loading, error } = useRequest(
    () => projectAPI.getProjects(),
    { refreshDeps: [] }
  );

  const trainingProjects = useMemo(() => {
    return (projectsResponse?.Data || []).filter(
      (project) => (project as any).ProjectType === "AI_TRAINING" || (project as any).projectType === "AI_TRAINING"
    );
  }, [projectsResponse]);

  const project = trainingProjects.find((item) => item.Id === id);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <Spin size="large" />
      </div>
    );
  }

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

  const getSelectedKeys = () => {
    const path = location.pathname;
    if (path.includes("/labeling")) return ["labeling"];
    if (path.includes("/experiments")) return ["experiments"];
    if (path.includes("/models")) return ["models"];
    return ["data"];
  };

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(`/training/projects/${id}/${key}`);
  };

  const projectMenuItems = trainingProjects.map((item) => ({
    key: item.Id,
    label: item.Name,
    onClick: () => navigate(`/training/projects/${item.Id}/data`),
  }));

  return (
    <Layout style={{ height: "calc(100vh - 64px)", overflow: "hidden" }}>
      <Sider width={240} style={{ background: "#fff", borderRight: "1px solid #f0f0f0" }}>
        <div style={{ padding: 16, borderBottom: "1px solid #f0f0f0" }}>
          <Dropdown menu={{ items: projectMenuItems }} trigger={["click"]}>
            <Button
              type="text"
              style={{ padding: 0, height: "auto", width: "100%", textAlign: "left" }}
            >
              <Space>
                <Text strong>{project.Name}</Text>
                <DownOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
              </Space>
            </Button>
          </Dropdown>
          <div style={{ marginTop: 6 }}>
            <Button type="link" onClick={() => navigate("/projects")} style={{ padding: 0 }}>
              返回项目列表
            </Button>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={getSelectedKeys()}
          style={{ height: "100%", borderRight: 0, paddingTop: 8 }}
          items={trainingMenuItems}
          onClick={handleMenuClick}
        />
      </Sider>

      <Layout style={{ height: "100%", overflow: "hidden" }}>
        <Content
          style={{
            backgroundColor: "#f0f2f5",
            padding: 0,
            margin: 0,
            height: "100%",
            overflow: "auto",
          }}
        >
          <Routes>
            <Route path="/" element={<Navigate to="data" replace />} />
            <Route
              path="/data"
              element={<DataManagementPage projectId={project.Id} projectName={project.Name} />}
            />
            <Route
              path="/labeling"
              element={<Placeholder title="数据标注" />}
            />
            <Route
              path="/experiments"
              element={<Placeholder title="实验管理" />}
            />
            <Route
              path="/models"
              element={<Placeholder title="模型管理" />}
            />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
