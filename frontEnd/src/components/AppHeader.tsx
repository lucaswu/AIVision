import { useEffect, useState } from "react";
import { Layout, Typography, Avatar, Dropdown, Space, message, Tag, Button, Tooltip } from "antd";
import { UserOutlined, LogoutOutlined, ExportOutlined, DeploymentUnitOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { userMenuItems } from "@/utils/constans";
import { userAPI, modelStatusAPI } from "@/utils/api";

const { Header } = Layout;
const { Title, Text } = Typography;

const MODEL_STATUS_POLL_INTERVAL_MS = 30000;

export default function AppHeader() {
  const navigate = useNavigate();
  const username = localStorage.getItem("username") || "未登录";
  const role = localStorage.getItem("role");
  const [modelNames, setModelNames] = useState<string[]>([]);

  const roleText = role === "ADMIN" ? "管理员" : "质检员";

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      const status = await modelStatusAPI.getSilently();
      if (cancelled || !status) return;
      const names = new Set<string>();
      const profileDetails = status.profile_details || {};
      Object.values<any>(profileDetails).forEach((profile) => {
        Object.values<any>(profile?.slots || {}).forEach((slot) => {
          if (slot?.model_name) names.add(slot.model_name);
        });
      });
      setModelNames(Array.from(names));
    };

    poll();
    const timer = setInterval(poll, MODEL_STATUS_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("userId");
    localStorage.removeItem("username");
    localStorage.removeItem("role");
    message.success("已退出登录");
    navigate("/login");
  };

  const handleSsoJump = async () => {
    try {
      const res = await userAPI.ssoJump();
      window.open(res.Data.url, "_blank");
    } catch (err) {
      message.error(err instanceof Error ? err.message : "跳转失败");
    }
  };

  return (
    <Header
      style={{
        background: "#fff",
        padding: "0 24px",
        borderBottom: "1px solid #f0f0f0",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        height: 64,
      }}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        <div
          style={{
            width: 32,
            height: 32,
            background: "#1890ff",
            borderRadius: "6px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "white",
            fontWeight: "bold",
            marginRight: 12,
          }}
        >
          AI
        </div>
        <Title level={4} style={{ margin: 0, color: "#1890ff", fontSize: 18 }}>
          AI Vision平台
        </Title>
      </div>

      <Space size={16}>
        {modelNames.length > 0 && (
          <Tooltip title={`当前推理运行的模型：${modelNames.join("、")}`}>
            <div style={{
              display: "flex",
              alignItems: "center",
              background: "#f6ffed",
              padding: "4px 12px",
              borderRadius: "20px",
              border: "1px solid #d9f7be",
              height: "36px",
              maxWidth: 320,
            }}>
              <DeploymentUnitOutlined style={{ color: "#52c41a" }} />
              <Text
                strong
                style={{
                  color: "#389e0d",
                  marginLeft: 8,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {modelNames.join("、")}
              </Text>
            </div>
          </Tooltip>
        )}

        <div style={{
          display: "flex",
          alignItems: "center",
          background: "#f0f7ff",
          padding: "4px 12px",
          borderRadius: "20px",
          border: "1px solid #e6f7ff",
          height: "36px"
        }}>
          <Tag color="processing" style={{ border: "none", margin: 0, borderRadius: "10px", height: "20px", lineHeight: "20px" }}>
            {roleText.substring(0, 2)}
          </Tag>
          <Text strong style={{ color: "#1890ff", marginLeft: 8 }}>{username}</Text>
        </div>

        <Button
          icon={<ExportOutlined />}
          onClick={handleSsoJump}
          style={{ borderRadius: "6px" }}
        >
          跳转到训练平台
        </Button>

        <Button
          icon={<LogoutOutlined />}
          onClick={handleLogout}
          style={{ borderRadius: "6px" }}
        >
          退出
        </Button>
        </Space>
    </Header>
  );
}
