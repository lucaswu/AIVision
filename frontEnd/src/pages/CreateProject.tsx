import React, { useState } from "react";
import {
  Card,
  Form,
  Input,
  Button,
  Typography,
  Space,
  Breadcrumb,
  message,
} from "antd";
import { useNavigate } from "react-router-dom";
import { projectAPI } from "@/utils/api";
import { CreateProjectRequest } from "@/utils/data";

const { Title, Text } = Typography;
const { TextArea } = Input;

const CreateProject: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const breadcrumbItems = [
    { title: "主菜单" },
    { title: "项目管理", href: "/projects" },
    { title: "新增项目" },
  ];

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      const res = await projectAPI.createProject({
        ProjectName: values.ProjectName,
        Description: values.Description,
      } as CreateProjectRequest);

      if (res.Code === 200) {
        message.success("项目创建成功");
        navigate("/projects");
      }
    } catch (error) {
      console.error("Create project error:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "24px", maxWidth: "1200px", margin: "0 auto" }}>
      <Breadcrumb items={breadcrumbItems} style={{ marginBottom: "16px" }} />

      <div style={{ marginBottom: "24px" }}>
        <Title level={2} style={{ margin: "0 0 4px 0" }}>
          新增项目
        </Title>
        <Text type="secondary">创建新的检测项目</Text>
      </div>

      <Card
        title="基本信息"
        variant="none"
        style={{ borderRadius: "12px", boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          requiredMark={true}
          size="large"
        >
          <Form.Item
            label="项目名称"
            name="ProjectName"
            rules={[{ required: true, message: "请输入项目名称" }]}
          >
            <Input placeholder="请输入项目名称" style={{ borderRadius: "8px" }} />
          </Form.Item>

          <Form.Item label="备注" name="Description">
            <TextArea
              placeholder="请输入项目备注信息..."
              rows={6}
              style={{ borderRadius: "8px" }}
            />
          </Form.Item>

          <Form.Item style={{ marginTop: "32px", marginBottom: 0, textAlign: "right" }}>
            <Space>
              <Button
                onClick={() => navigate("/projects")}
                style={{ borderRadius: "8px", minWidth: "100px" }}
              >
                取消
              </Button>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                style={{
                  borderRadius: "8px",
                  minWidth: "100px",
                  backgroundColor: "#1890ff",
                }}
              >
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default CreateProject;

