import React, { useState } from "react";
import {
  Card,
  Typography,
  Space,
  Tag,
  Button,
  message,
  Table,
  Row,
  Col,
  Statistic,
  Divider,
  List,
  Tabs,
} from "antd";
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import { reportAPI } from "../../utils/api";
import { TaskFile, Report } from "../../utils/data";

const { Title, Text, Paragraph } = Typography;

interface ReportPreviewPageProps {
  taskId: string;
  projectId: string;
  onBack: () => void;
}

const ReportPreviewPage: React.FC<ReportPreviewPageProps> = ({
  taskId,
  projectId,
  onBack,
}) => {
  const [activeTab, setActiveTab] = useState<"all" | "has_defects" | "no_defects">("all");

  // 1. 获取报告详情
  const { data: reportResp } = useRequest(() => reportAPI.getReportDetail(taskId));
  const report = reportResp?.Data;

  // 2. 获取文件列表 (根据 Tab 过滤)
  const {
    data: filesResp,
    loading: filesLoading,
  } = useRequest(() => reportAPI.getReportFiles(taskId, activeTab), {
    refreshDeps: [taskId, activeTab],
  });
  const files = filesResp?.Data || [];

  const columns = [
    {
      title: "文件名",
      dataIndex: "FileName",
      key: "FileName",
      render: (text, record) => (
        <Space>
          <img src={`/api/v1/files/preview/${record.FileId}`} alt="thumb" style={{ width: 40, height: 40, objectFit: "cover", borderRadius: 4 }} />
          <Text strong>{text}</Text>
        </Space>
      ),
    },
    {
      title: "检测结果",
      key: "result",
      render: (_, record) => {
        const result = JSON.parse(record.VisionResult || '{"results":[]}');
        const defects = result.results.filter((r: any) => r.strName !== "normal");
        return defects.length > 0 ? (
          <Space wrap>
            {defects.map((d: any, idx: number) => (
              <Tag color="red" key={idx}>{d.strName}</Tag>
            ))}
          </Space>
        ) : (
          <Tag color="success">无缺陷</Tag>
        );
      },
    },
    {
      title: "底片质量",
      dataIndex: "PlateQuality",
      key: "PlateQuality",
      render: (q) => q || "一级",
    },
    {
      title: "审核状态",
      dataIndex: "ReviewStatus",
      key: "ReviewStatus",
      render: (s) => s === "CONFIRMED" ? <Tag color="success">已确认</Tag> : <Tag color="default">待审核</Tag>,
    },
  ];

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", paddingBottom: 40 }}>
      <div style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Button icon={<ArrowLeftOutlined />} onClick={onBack} type="text">返回列表</Button>
        <Space>
          <Button icon={<DownloadOutlined />} type="primary">下载 PDF 报告</Button>
        </Space>
      </div>

      <Card>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <Title level={2}>{report?.ReportName}</Title>
          <Space split={<Divider type="vertical" />}>
            <Text type="secondary">文件总数: {report?.TotalFiles}</Text>
            <Text type="secondary">生成时间: {report?.CreatedAt}</Text>
            <Text type="secondary">审核人: 管理员</Text>
          </Space>
        </div>

        <Row gutter={16} style={{ marginBottom: 40 }}>
          <Col span={6}>
            <Card size="small" style={{ textAlign: "center", background: "#f6ffed" }}>
              <Statistic title="已确认文件" value={report?.ConfirmedFiles} suffix={`/ ${report?.TotalFiles}`} valueStyle={{ color: "#52c41a" }} />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small" style={{ textAlign: "center", background: "#fff1f0" }}>
              <Statistic title="缺陷总数" value={report?.TotalDefects} valueStyle={{ color: "#ff4d4f" }} />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small" style={{ textAlign: "center", background: "#fff7e6" }}>
              <Statistic title="严重缺陷" value={report?.SevereDefects} valueStyle={{ color: "#faad14" }} />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small" style={{ textAlign: "center", background: "#e6f7ff" }}>
              <Statistic title="一般缺陷" value={report?.NormalDefects} valueStyle={{ color: "#1890ff" }} />
            </Card>
          </Col>
        </Row>

        <Title level={4}><InfoCircleOutlined /> 1. 缺陷总结</Title>
        <Paragraph>
          本次检测共处理 {report?.TotalFiles} 个文件，其中 {report?.ConfirmedFiles} 个文件已确认。
          在已确认的文件中，检测到 {report?.TotalDefects} 处缺陷，包括 {report?.SevereDefects} 处严重缺陷和 {report?.NormalDefects} 处一般缺陷。
        </Paragraph>

        <Divider />

        <Title level={4}><CheckCircleOutlined /> 2. 详细检测结果</Title>
        <Tabs
          activeKey={activeTab}
          onChange={(key: any) => setActiveTab(key)}
          items={[
            { key: "all", label: "全部" },
            { key: "has_defects", label: "有缺陷" },
            { key: "no_defects", label: "无缺陷" },
          ]}
        />
        <Table
          columns={columns}
          dataSource={files}
          loading={filesLoading}
          rowKey="TaskFileId"
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  );
};

export default ReportPreviewPage;

