import { Layout, Typography, Avatar, Dropdown, Space, message, Tag, Button } from "antd";
import { UserOutlined, LogoutOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { userMenuItems } from "@/utils/constans";

const { Header } = Layout;
const { Title, Text } = Typography;

export default function AppHeader() {
  const navigate = useNavigate();
  const username = localStorage.getItem("username") || "未登录";
  const role = localStorage.getItem("role");
  
  const roleText = role === "ADMIN" ? "管理员" : "质检员";

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("userId");
    localStorage.removeItem("username");
    localStorage.removeItem("role");
    message.success("已退出登录");
    navigate("/login");
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
