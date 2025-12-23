import React, { useState, useEffect } from "react";
import {
  Row,
  Col,
  Card,
  List,
  Typography,
  Space,
  Tag,
  Button,
  message,
  Layout,
  Breadcrumb,
  Empty,
  Select,
  Form,
  Checkbox,
  Divider,
} from "antd";
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileImageOutlined,
  SaveOutlined,
  DoubleRightOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import { reportAPI } from "../../utils/api";
import { TaskFile, Report } from "../../utils/data";

const { Content, Sider } = Layout;
const { Title, Text } = Typography;

interface ReportEditorPageProps {
  taskId: string;
  projectId: string;
  projectName?: string;
  onBack: () => void;
}

const ReportEditorPage: React.FC<ReportEditorPageProps> = ({
  taskId,
  projectId,
  projectName,
  onBack,
}) => {
  const [selectedFile, setSelectedFile] = useState<TaskFile | null>(null);
  const [form] = Form.useForm();

  // 1. 获取报告详情
  const { data: reportResp } = useRequest(() => reportAPI.getReportDetail(taskId));
  const report = reportResp?.Data;

  // 2. 获取文件列表
  const {
    data: filesResp,
    loading: filesLoading,
    refresh: refreshFiles,
  } = useRequest(() => reportAPI.getReportFiles(taskId));
  const files = filesResp?.Data || [];

  useEffect(() => {
    if (files.length > 0 && !selectedFile) {
      setSelectedFile(files[0]);
    }
  }, [files]);

  useEffect(() => {
    if (selectedFile) {
      form.setFieldsValue({
        PlateQuality: selectedFile.PlateQuality || "一级",
      });
    }
  }, [selectedFile]);

  // 保存审核结果
  const handleSave = async () => {
    if (!selectedFile) return;
    try {
      const values = await form.validateFields();
      await reportAPI.reviewFile(selectedFile.TaskFileId, {
        ManualResult: selectedFile.VisionResult || "{}", // 简化处理，暂时直接存 visionResult
        PlateQuality: values.PlateQuality,
      });
      message.success("保存并确认成功");
      refreshFiles();
      
      // 自动跳转到下一个未确认的文件
      const currentIndex = files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId);
      if (currentIndex < files.length - 1) {
        setSelectedFile(files[currentIndex + 1]);
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <Layout style={{ height: "calc(100vh - 120px)", background: "#fff" }}>
      <Sider width={300} theme="light" style={{ borderRight: "1px solid #f0f0f0", overflowY: "auto" }}>
        <div style={{ padding: "16px", borderBottom: "1px solid #f0f0f0" }}>
          <Space direction="vertical" style={{ width: "100%" }}>
            <Button icon={<ArrowLeftOutlined />} onClick={onBack} type="text">返回列表</Button>
            <Title level={4} style={{ margin: 0 }}>结果审核</Title>
            <Text type="secondary">{report?.ReportName}</Text>
          </Space>
        </div>
        <List
          loading={filesLoading}
          dataSource={files}
          renderItem={(file) => (
            <List.Item
              onClick={() => setSelectedFile(file)}
              style={{
                cursor: "pointer",
                padding: "12px 16px",
                backgroundColor: selectedFile?.TaskFileId === file.TaskFileId ? "#e6f7ff" : "transparent",
                borderLeft: selectedFile?.TaskFileId === file.TaskFileId ? "4px solid #1890ff" : "4px solid transparent",
              }}
            >
              <List.Item.Meta
                avatar={<FileImageOutlined style={{ fontSize: 20, color: "#8c8c8c" }} />}
                title={<Text ellipsis style={{ width: 180 }}>{file.FileName}</Text>}
                description={
                  file.ReviewStatus === "CONFIRMED" ? (
                    <Tag color="success" icon={<CheckCircleOutlined />}>已确认</Tag>
                  ) : (
                    <Tag color="default" icon={<ClockCircleOutlined />}>待审核</Tag>
                  )
                }
              />
            </List.Item>
          )}
        />
      </Sider>
      
      <Content style={{ display: "flex", flexDirection: "column" }}>
        {selectedFile ? (
          <>
            <div style={{ flex: 1, backgroundColor: "#f5f5f5", display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
              {/* 图片标注编辑器占位 */}
              <div style={{ position: "relative" }}>
                <img 
                  src={`/api/v1/files/preview/${selectedFile.FileId}`} 
                  alt="preview" 
                  style={{ maxHeight: "100%", maxWidth: "100%", boxShadow: "0 4px 12px rgba(0,0,0,0.15)" }} 
                />
                {/* 模拟标注框 */}
                <div style={{ position: "absolute", top: "20%", left: "30%", width: "100px", height: "100px", border: "2px solid red", pointerEvents: "none" }}>
                  <Tag color="red" style={{ position: "absolute", top: -22, left: -2 }}>裂纹 (AI)</Tag>
                </div>
              </div>
              
              <div style={{ position: "absolute", bottom: 20, right: 20 }}>
                <Space>
                  <Button type="primary" size="large" icon={<SaveOutlined />} onClick={handleSave}>保存并确认</Button>
                  <Button size="large" icon={<DoubleRightOutlined />} onClick={() => {
                    const idx = files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId);
                    if (idx < files.length - 1) setSelectedFile(files[idx + 1]);
                  }}>下一个</Button>
                </Space>
              </div>
            </div>
            
            <div style={{ height: 240, borderTop: "1px solid #f0f0f0", padding: 20 }}>
              <Row gutter={32}>
                <Col span={12}>
                  <Title level={5}>缺陷详情</Title>
                  <List
                    size="small"
                    dataSource={JSON.parse(selectedFile.VisionResult || '{"results":[]}').results}
                    renderItem={(item: any) => (
                      <List.Item>
                        <Space>
                          <Tag color="red">{item.strName}</Tag>
                          <Text>置信度: {(item.score * 100).toFixed(1)}%</Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                </Col>
                <Col span={12}>
                  <Title level={5}>审核属性</Title>
                  <Form form={form} layout="vertical">
                    <Form.Item name="PlateQuality" label="底片质量">
                      <Select style={{ width: 200 }}>
                        <Select.Option value="一级">一级 (优)</Select.Option>
                        <Select.Option value="二级">二级 (良)</Select.Option>
                        <Select.Option value="三级">三级 (及格)</Select.Option>
                        <Select.Option value="四级">四级 (不及格)</Select.Option>
                      </Select>
                    </Form.Item>
                  </Form>
                </Col>
              </Row>
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Empty description="请从左侧选择图片开始审核" />
          </div>
        )}
      </Content>
    </Layout>
  );
};

export default ReportEditorPage;

