import { Card, Typography, Button, Space } from "antd";
import { useNavigate, useParams } from "react-router-dom";

const { Title, Text } = Typography;

export default function TrainingProjectPlaceholder() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();

  return (
    <div style={{ padding: "24px", maxWidth: "1200px", margin: "0 auto" }}>
      <Card
        variant="borderless"
        style={{ borderRadius: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Title level={3} style={{ margin: 0 }}>
            训练项目
          </Title>
          <Text type="secondary">
            训练平台功能后续会逐步完善，这里先占位。
          </Text>
          <Text>当前项目ID：{id}</Text>
          <div>
            <Button onClick={() => navigate("/projects")}>返回项目列表</Button>
          </div>
        </Space>
      </Card>
    </div>
  );
}
