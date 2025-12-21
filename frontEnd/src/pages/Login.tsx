import React, { useState } from "react";
import { Form, Input, Button, Card, Typography, Segmented, message } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { userAPI } from "../utils/api";

const { Title, Text } = Typography;

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState<string>("质检员");
  const navigate = useNavigate();

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      const res = await userAPI.login({
        username: values.username,
        password: values.password,
        role: role === "管理员" ? "ADMIN" : "INSPECTOR",
      });
      
      if (res.Code === 200) {
        message.success("登录成功");
        localStorage.setItem("token", res.Data.token);
        localStorage.setItem("userId", res.Data.userId);
        localStorage.setItem("username", res.Data.username);
        localStorage.setItem("role", res.Data.role);
        
        navigate("/projects");
      }
    } catch (error) {
      console.error("Login error:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        backgroundColor: "#eef5ff",
        padding: "20px",
      }}
    >
      <Card
        variant="none"
        style={{
          width: "100%",
          maxWidth: "480px",
          borderRadius: "16px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.04)",
          textAlign: "center",
          padding: "32px 16px",
        }}
      >
        <div style={{ marginBottom: "40px" }}>
          <div
            style={{
              width: "72px",
              height: "72px",
              backgroundColor: "#2f80ed",
              borderRadius: "16px",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontSize: "32px",
              fontWeight: "bold",
              marginBottom: "16px",
              boxShadow: "0 4px 12px rgba(47, 128, 237, 0.3)",
            }}
          >
            AI
          </div>
          <Title level={2} style={{ margin: "0 0 4px 0", fontSize: "28px", fontWeight: 600 }}>
            AI Vision平台
          </Title>
          <Text type="secondary" style={{ fontSize: "16px", letterSpacing: "1px" }}>
            质量检测系统
          </Text>
        </div>

        <Form
          name="login"
          onFinish={onFinish}
          size="large"
          layout="vertical"
          requiredMark={false}
        >
          <Form.Item label={<span style={{ color: "#8c8c8c" }}>登录身份</span>} style={{ marginBottom: "24px" }}>
            <div style={{ backgroundColor: "#f0f2f5", padding: "4px", borderRadius: "8px" }}>
              <Segmented
                block
                options={["质检员", "管理员"]}
                value={role}
                onChange={(value) => setRole(value as string)}
                style={{
                  backgroundColor: "transparent",
                }}
              />
            </div>
            <style>{`
              .ant-segmented-item {
                transition: all 0.3s;
                color: #595959;
              }
              .ant-segmented-item-selected {
                background: #fff !important;
                border-radius: 6px !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
                color: #1890ff !important;
              }
            `}</style>
          </Form.Item>

          <Form.Item
            label={<span style={{ color: "#8c8c8c" }}>用户名</span>}
            name="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input
              placeholder="请输入用户名"
              style={{ 
                borderRadius: "8px", 
                height: "48px",
                backgroundColor: "#fcfdfe",
                border: "1px solid #eef0f2"
              }}
            />
          </Form.Item>

          <Form.Item
            label={<span style={{ color: "#8c8c8c" }}>密码</span>}
            name="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password
              placeholder="请输入密码"
              style={{ 
                borderRadius: "8px", 
                height: "48px",
                backgroundColor: "#fcfdfe",
                border: "1px solid #eef0f2"
              }}
            />
          </Form.Item>

          <Form.Item style={{ marginTop: "40px", marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{
                height: "52px",
                borderRadius: "10px",
                fontSize: "18px",
                fontWeight: "500",
                backgroundColor: "#2f80ed",
                boxShadow: "0 4px 12px rgba(47, 128, 237, 0.2)",
              }}
            >
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
      
      <div style={{ marginTop: "32px" }}>
        <Text style={{ color: "#bfbfbf", fontSize: "14px" }}>
          © 2026 AI Vision平台
        </Text>
      </div>
    </div>
  );
};

export default Login;
