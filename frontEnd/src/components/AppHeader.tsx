import { Layout, Typography, Avatar, Dropdown, Space } from "antd";
import { UserOutlined } from "@ant-design/icons";
import { userMenuItems } from "@/utils/constans";

const { Header } = Layout;
const { Title } = Typography;

export default function AppHeader() {
  return (
    <Header
      style={{
        background: "#fff",
        padding: "0 24px",
        borderBottom: "1px solid #f0f0f0",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        <div
          style={{
            width: 32,
            height: 32,
            background: "#1890ff",
            borderRadius: "50%",
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
        <Title level={4} style={{ margin: 0, color: "#1890ff" }}>
          AI Vision平台
        </Title>
      </div>

      <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
        <Space style={{ cursor: "pointer" }}>
          <Avatar icon={<UserOutlined />} />
          <span>User1</span>
        </Space>
      </Dropdown>
    </Header>
  );
}
