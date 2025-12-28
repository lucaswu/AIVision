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
  ExportOutlined,
  InboxOutlined,
} from "@ant-design/icons";
import type { TableColumnsType } from "antd";
import { useRequest } from "ahooks";
import { useNavigate } from "react-router-dom";
import { reportAPI } from "../../utils/api";
import { Report } from "../../utils/data";

const { Title, Text, Link } = Typography;

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
  const navigate = useNavigate();
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
      width: 250,
      render: (text) => (
        <div>
          <Text strong>{text}</Text>
          <div style={{ fontSize: '12px', color: '#8c8c8c' }}>质检员 生成</div>
        </div>
      ),
    },
    {
      title: "检测任务",
      dataIndex: "TaskName",
      key: "TaskName",
      width: 200,
      render: (text, record) => (
        <Space>
          <Link onClick={() => navigate(`/projects/${projectId}/tasks`)}>
            {text || `检测任务 #${record.TaskId.slice(-4)}`}
          </Link>
          <ExportOutlined style={{ fontSize: '12px', color: '#1890ff' }} />
        </Space>
      ),
    },
    {
      title: "文件数",
      dataIndex: "TotalFiles",
      key: "TotalFiles",
      width: 120,
      render: (count) => `${count}个文件`,
    },
    {
      title: "缺陷概览",
      key: "defects",
      width: 280,
      render: (_, record) => (
        <Space size="large">
          {record.SevereDefects > 0 ? (
            <span style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ff4d4f', marginRight: 8 }} />
              <Text type="danger">{record.SevereDefects}处严重</Text>
            </span>
          ) : null}
          {record.NormalDefects > 0 ? (
            <span style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#faad14', marginRight: 8 }} />
              <Text style={{ color: '#faad14' }}>{record.NormalDefects}处一般</Text>
            </span>
          ) : null}
          {record.SevereDefects === 0 && record.NormalDefects === 0 && (
            <span style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#52c41a', marginRight: 8 }} />
              <Text type="success">未检测到缺陷</Text>
            </span>
          )}
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
        const isArchived = status === "ARCHIVED";
        return (
          <span style={{ display: 'flex', alignItems: 'center' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: isArchived ? '#d9d9d9' : '#52c41a', marginRight: 8 }} />
            <Text style={{ color: isArchived ? '#8c8c8c' : '#52c41a' }}>
              {isArchived ? '已归档' : '未归档'}
            </Text>
          </span>
        );
      },
    },
    {
      title: "操作",
      key: "action",
      width: 200,
      render: (_, record) => (
        <Space size="middle">
          <Tooltip title="查看">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => onPreview(record.TaskId)}
            />
          </Tooltip>
          <Tooltip title="审核">
            <Button
              type="text"
              icon={<FileSearchOutlined />}
              onClick={() => onReview(record.TaskId)}
              disabled={record.Status === "ARCHIVED"}
            />
          </Tooltip>
          <Tooltip title="下载">
            <Button
              type="text"
              icon={<DownloadOutlined />}
              onClick={() => {
                const url = reportAPI.downloadReport(record.ReportId);
                const link = document.createElement('a');
                link.href = url;
                // 后端已经设置了 Content-Disposition 文件名，这里不需要手动指定
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
              }}
            />
          </Tooltip>
          <Tooltip title={record.Status === "ARCHIVED" ? "取消归档" : "归档"}>
            <Button
              type="text"
              icon={<InboxOutlined />}
              onClick={() => {
                const newStatus = record.Status === "ARCHIVED";
                reportAPI.archiveReport(record.ReportId, !newStatus).then(() => {
                  message.success(newStatus ? "已取消归档" : "报告已归档");
                  refresh();
                });
              }}
            />
          </Tooltip>
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
    <div style={{ padding: 24, minHeight: "100%" }}>
      <Breadcrumb 
        style={{ marginBottom: "24px" }}
        items={[
          { title: '项目' },
          { title: projectName },
          { title: '报告管理' },
        ]}
      />

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


