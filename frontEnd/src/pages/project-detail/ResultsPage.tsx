import React, { useState } from "react";
import {
  Table,
  Card,
  Statistic,
  Row,
  Col,
  Typography,
  Tag,
  Space,
  Button,
  Modal,
  Image,
  Progress,
  Select,
  DatePicker,
  Input,
  message,
  Breadcrumb,
  Tabs,
  Radio,
  Divider,
  Alert,
} from "antd";
import {
  EyeOutlined,
  DownloadOutlined,
  FileImageOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  CompressOutlined,
  LeftOutlined,
  RightOutlined,
} from "@ant-design/icons";
import type { TableColumnsType } from "antd";
import { useParams } from "react-router-dom";
import { useRequest } from "ahooks";
import { resultAPI } from "../../utils/api";
import ReportDetailModal from "../../components/ReportDetailModal";
import { Task } from "../../utils/data";

const { Title } = Typography;
const { Search } = Input;
const { RangePicker } = DatePicker;

interface ResultsPageProps {
  projectId: string;
  projectName: string;
  permission?: string;
}

export default function ResultsPage({
  projectId,
  projectName,
  permission = "READ_ONLY",
}: ResultsPageProps) {
  const isReadOnly = permission === "READ_ONLY";
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [reportData, setReportData] = useState<any>(null);
  const [verificationStatus, setVerificationStatus] = useState<string>("");
  const [verificationNotes, setVerificationNotes] = useState<string>("");

  // 使用 useRequest 获取检测结果数据（实际上是已完成的任务数据）
  const {
    data: resultResponse,
    loading,
    refresh,
    error: requestError,
  } = useRequest(
    () => {
      return resultAPI.getResults(projectId, {
        page: currentPage,
        pageSize,
        keyword: searchKeyword,
        status: statusFilter || "completed", // 默认获取已完成的任务
      });
    },
    {
      refreshDeps: [
        currentPage,
        pageSize,
        searchKeyword,
        statusFilter,
        projectId,
      ],
    }
  );

  const results: Task[] = (resultResponse?.Data as any)?.Tasks || [];
  const total = (resultResponse?.Data as any)?.TotalCount || 0;

  // 处理分页变化
  const handlePaginationChange = (page: number, size: number) => {
    setCurrentPage(page);
    setPageSize(size);
  };

  // 处理页大小变化
  const handleShowSizeChange = (current: number, size: number) => {
    setCurrentPage(1);
    setPageSize(size);
  };

  // 处理搜索
  const handleSearch = (value: string) => {
    setSearchKeyword(value);
    setCurrentPage(1);
  };

  // 处理状态筛选
  const handleStatusChange = (value: string) => {
    setStatusFilter(value);
    setCurrentPage(1);
  };

  const handleViewDetail = (task: Task) => {
    // 使用任务数据作为报告数据
    setReportData(task);
    setShowDetailModal(true);
  };

  const handleDownload = async (task: Task) => {
    if (!task.TaskFiles || task.TaskFiles.length === 0) {
      message.warning("该任务暂无检测数据可下载");
      return;
    }

    // 显示loading，3秒后自动消失，避免永久卡住
    const hideLoading = message.loading("正在生成PDF报告...", 3);

    try {
      // 动态导入PDF生成器
      const { generateAndDownloadTaskPDF } = await import(
        "../../utils/pdfGenerator"
      );

      // 调用PDF生成
      await generateAndDownloadTaskPDF(task);

      hideLoading();
      message.success(`${task.Name} 的检测报告已开始下载`);
    } catch (error) {
      hideLoading();
      console.error("PDF生成失败:", error);
      message.error("PDF生成失败，请稍后重试");
    }
  };

  const getStatusTag = (status: string) => {
    const statusMap = {
      completed: {
        color: "success",
        text: "已完成",
        icon: <CheckCircleOutlined />,
      },
      failed: { color: "error", text: "失败", icon: <CloseCircleOutlined /> },
      processing: {
        color: "processing",
        text: "处理中",
        icon: <ExclamationCircleOutlined />,
      },
    };
    const config = statusMap[status as keyof typeof statusMap] || {
      color: "default",
      text: status,
      icon: null,
    };
    return (
      <Tag color={config.color} icon={config.icon}>
        {config.text}
      </Tag>
    );
  };

  const columns: TableColumnsType<Task> = [
    {
      title: "任务名称",
      dataIndex: "Name",
      key: "Name",
    },
    {
      title: "状态",
      dataIndex: "Status",
      key: "Status",
      render: (status: string) => getStatusTag(status),
      filters: [
        { text: "已完成", value: "completed" },
        { text: "失败", value: "failed" },
        { text: "处理中", value: "processing" },
      ],
    },
    {
      title: "文件统计",
      key: "fileStats",
      render: (_, record: Task) => (
        <div>
          <Tag color="blue">{record.FileCount} 个文件</Tag>
          <Tag color="green">{record.SuccessFiles} 成功</Tag>
          {record.FailedFiles > 0 && (
            <Tag color="red">{record.FailedFiles} 失败</Tag>
          )}
        </div>
      ),
    },
    {
      title: "缺陷统计",
      key: "defectStats",
      render: (_, record: Task) => {
        const totalDefects = (record.TaskFiles || []).reduce((sum, file) => {
          if (file.VisionResult) {
            try {
              const visionData = JSON.parse(file.VisionResult);
              return sum + (visionData.totalDefects || 0);
            } catch {
              return sum;
            }
          }
          return sum;
        }, 0);
        return (
          <Tag color={totalDefects > 0 ? "volcano" : "green"}>
            {totalDefects} 个缺陷
          </Tag>
        );
      },
    },
    {
      title: "进度",
      dataIndex: "Progress",
      key: "Progress",
      render: (progress: number) => `${progress}%`,
    },
    {
      title: "操作",
      key: "action",
      render: (_, record: Task) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record)}
          >
            查看详情
          </Button>
          <Button
            type="text"
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => handleDownload(record)}
          >
            下载结果
          </Button>
        </Space>
      ),
    },
  ];

  const handleSaveVerification = () => {
    if (!verificationStatus) {
      message.warning("请选择核验结果");
      return;
    }

    // 这里可以调用API保存核验结果
    message.success("核验结果已保存");
    setShowDetailModal(false);
    setReportData(null);
    setVerificationStatus("");
    setVerificationNotes("");
  };

  return (
    <div style={{ padding: 24, minHeight: "100%" }}>
      <Breadcrumb style={{ marginBottom: "24px" }}>
        <Breadcrumb.Item>项目管理</Breadcrumb.Item>
        <Breadcrumb.Item>{projectName}</Breadcrumb.Item>
        <Breadcrumb.Item>报告管理</Breadcrumb.Item>
      </Breadcrumb>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "24px",
        }}
      >
        <Title level={2} style={{ margin: 0 }}>
          报告管理
        </Title>
      </div>

      {/* 错误提示 */}
      {requestError && (
        <Alert
          message="获取报告数据时发生错误"
          description={`错误信息: ${requestError.message}`}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={refresh}>
              重试
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      <div
        style={{
          marginBottom: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Space>
          <Search
            placeholder="搜索文件名或任务名"
            allowClear
            style={{ width: 240 }}
            onSearch={handleSearch}
          />
          <Select
            placeholder="状态筛选"
            allowClear
            style={{ width: 120 }}
            onChange={handleStatusChange}
            options={[
              { label: "已完成", value: "completed" },
              { label: "失败", value: "failed" },
              { label: "处理中", value: "processing" },
            ]}
          />
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={results}
        loading={loading}
        rowKey="Id"
        pagination={{
          current: currentPage,
          pageSize: pageSize,
          total: total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total, range) =>
            `第 ${range[0]}-${range[1]} 条/共 ${total} 条`,
          pageSizeOptions: ["10", "20", "50", "100"],
          onChange: handlePaginationChange,
          onShowSizeChange: handleShowSizeChange,
        }}
      />

      <ReportDetailModal
        open={showDetailModal}
        onClose={() => {
          setShowDetailModal(false);
          setReportData(null);
        }}
        reportData={reportData}
      />
    </div>
  );
}
