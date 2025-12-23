import React, { useState } from "react";
import {
  Card,
  Table,
  Space,
  Typography,
  Tag,
  Button,
  message,
  Breadcrumb,
  Tooltip,
  Statistic,
  Row,
  Col,
} from "antd";
import {
  FileSearchOutlined,
  EyeOutlined,
  DownloadOutlined,
  CloudUploadOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileDoneOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import type { TableColumnsType } from "antd";
import { useRequest } from "ahooks";
import { reportAPI } from "../../utils/api";
import { Report } from "../../utils/data";

const { Title, Text } = Typography;

interface ReportsPageProps {
  projectId: string;
  projectName?: string;
  onReview: (taskId: string) => void;
  onPreview: (taskId: string) => void;
}

const ReportsPage: React.FC<ReportsPageProps> = ({
  projectId,
  projectName = "项目",
  onReview,
  onPreview,
}) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const {
    data: reportsResponse,
    loading,
    refresh,
  } = useRequest(() => reportAPI.getReports(projectId), {
    refreshDeps: [projectId],
  });

  const reports = reportsResponse?.Data || [];

  const columns: TableColumnsType<Report> = [
    {
      title: "报告名称",
      dataIndex: "ReportName",
      key: "ReportName",
      render: (text) => <Text strong>{text}</Text>,
    },
    {
      title: "文件数",
      dataIndex: "TotalFiles",
      key: "TotalFiles",
      width: 100,
      render: (count) => `${count}个文件`,
    },
    {
      title: "缺陷概览",
      key: "defects",
      width: 250,
      render: (_, record) => (
        <Space size="middle">
          {record.SevereDefects > 0 ? (
            <Tag color="error">
              <ExclamationCircleOutlined /> {record.SevereDefects}处严重
            </Tag>
          ) : null}
          {record.NormalDefects > 0 ? (
            <Tag color="warning">
              {record.NormalDefects}处一般
            </Tag>
          ) : null}
          {record.SevereDefects === 0 && record.NormalDefects === 0 ? (
            <Tag color="success">未检测到缺陷</Tag>
          ) : null}
        </Space>
      ),
    },
    {
      title: "生成时间",
      dataIndex: "CreatedAt",
      key: "CreatedAt",
      width: 180,
    },
    {
      title: "状态",
      dataIndex: "Status",
      key: "Status",
      width: 120,
      render: (status) => {
        const config = {
          PENDING: { color: "default", text: "审核中", icon: <ClockCircleOutlined /> },
          COMPLETED: { color: "success", text: "已审核", icon: <CheckCircleOutlined /> },
          ARCHIVED: { color: "blue", text: "已归档", icon: <FileDoneOutlined /> },
        };
        const item = config[status] || { color: "default", text: status };
        return <Tag color={item.color} icon={item.icon}>{item.text}</Tag>;
      },
    },
    {
      title: "操作",
      key: "action",
      width: 180,
      render: (_, record) => (
        <Space size="middle">
          <Tooltip title="结果审核">
            <Button
              type="text"
              icon={<FileSearchOutlined />}
              onClick={() => onReview(record.TaskId)}
              disabled={record.Status === "ARCHIVED"}
            />
          </Tooltip>
          <Tooltip title="预览报告">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => onPreview(record.TaskId)}
            />
          </Tooltip>
          <Tooltip title="下载 PDF">
            <Button
              type="text"
              icon={<DownloadOutlined />}
              onClick={() => message.info("PDF 生成功能开发中")}
            />
          </Tooltip>
          {record.Status !== "ARCHIVED" && (
            <Tooltip title="归档报告">
              <Button
                type="text"
                icon={<CloudUploadOutlined />}
                onClick={() => {
                  reportAPI.archiveReport(record.ReportId, true).then(() => {
                    message.success("报告已归档");
                    refresh();
                  });
                }}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  const stats = {
    total: reports.length,
    pending: reports.filter((r) => r.Status === "PENDING").length,
    archived: reports.filter((r) => r.Status === "ARCHIVED").length,
  };

  return (
    <div style={{ height: "100%" }}>
      <Breadcrumb style={{ marginBottom: "24px" }}>
        <Breadcrumb.Item>项目</Breadcrumb.Item>
        <Breadcrumb.Item>{projectName}</Breadcrumb.Item>
        <Breadcrumb.Item>报告管理</Breadcrumb.Item>
      </Breadcrumb>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
        <div>
          <Title level={2} style={{ margin: 0 }}>报告管理</Title>
          <Text type="secondary">查看和管理检测报告</Text>
        </div>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic title="总报告数" value={stats.total} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="待审核" value={stats.pending} valueStyle={{ color: "#faad14" }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="已归档" value={stats.archived} valueStyle={{ color: "#1890ff" }} />
          </Card>
        </Col>
      </Row>

      <Card title={
        <Space>
          <FileDoneOutlined />
          <span>报告列表</span>
        </Space>
      } extra={<Button type="link" onClick={refresh}>刷新</Button>}>
        <Table
          columns={columns}
          dataSource={reports}
          loading={loading}
          rowKey="ReportId"
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            onChange: (p, s) => { setCurrentPage(p); setPageSize(s); },
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </Card>
    </div>
  );
};

export default ReportsPage;

