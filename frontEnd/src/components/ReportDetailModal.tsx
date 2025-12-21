import { useState } from "react";
import {
  Drawer,
  Card,
  Row,
  Col,
  Space,
  Button,
  Input,
  message,
  Typography,
  Tag,
  Modal,
  Table,
  Radio,
} from "antd";
import QuillEditor from "./QuillEditor";
import {
  CompressOutlined,
  ExpandOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
} from "@ant-design/icons";
// 不再需要 markdownToHtml 转换函数，因为 QuillEditor 组件内部已经处理了转换
import { Task, TaskFile } from "../utils/data";
import { filePreviewPath } from "@/utils/constans";
import { getUserId } from "@/utils/api";

const { Title, Text } = Typography;
const { TextArea } = Input;

interface ReportDetailModalProps {
  open: boolean;
  onClose: () => void;
  reportData: Task | null;
}

export default function ReportDetailModal({
  open,
  onClose,
  reportData,
}: ReportDetailModalProps) {
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [fileModalOpen, setFileModalOpen] = useState(false);
  const [currentFile, setCurrentFile] = useState<TaskFile | null>(null);
  const [verificationStatus, setVerificationStatus] = useState<string>("");
  const [verificationNotes, setVerificationNotes] = useState<string>("");
  const [editableMarkdown, setEditableMarkdown] = useState<string>("");
  const [isZoomed, setIsZoomed] = useState<boolean>(false);

  const handleFileClick = (file: TaskFile) => {
    setCurrentFile(file);
    // 确保 LlmResult 是 HTML 格式，如果不是，可能需要转换
    setEditableMarkdown(file.LlmResult || "");
    setVerificationStatus("");
    setVerificationNotes("");
    setIsEditing(false);
    setFileModalOpen(true);
  };

  const handleClose = () => {
    setIsEditing(false);
    setFileModalOpen(false);
    setCurrentFile(null);
    setVerificationStatus("");
    setVerificationNotes("");
    setEditableMarkdown("");
    onClose();
  };

  const handleModalClose = () => {
    setFileModalOpen(false);
    setCurrentFile(null);
    setVerificationStatus("");
    setVerificationNotes("");
    setEditableMarkdown("");
    setIsEditing(false);
    setIsZoomed(false);
  };

  const handleSave = () => {
    if (!verificationStatus) {
      message.warning("请选择核验结果");
      return;
    }

    // 这里可以调用API保存数据
    console.log({
      fileId: currentFile?.TaskFileId,
      editedReport: editableMarkdown,
      verificationStatus,
      verificationNotes,
    });

    message.success("保存成功");
    handleModalClose();
  };

  if (!reportData) return null;

  return (
    <>
      <Drawer
        title={reportData.Name}
        open={open}
        onClose={handleClose}
        width={1200}
        placement="right"
      >
        <div>
          {/* 任务状态信息 */}
          <div style={{ marginBottom: 16, fontSize: 14, color: "#666" }}>
            任务状态：{reportData.Status} | 进度：{reportData.Progress}% |
            处理文件：{reportData.ProcessedFiles}/{reportData.FileCount}
          </div>
          {/* 文件列表 */}
          <Card title="检测文件列表" size="small">
            <Table
              dataSource={(reportData.TaskFiles || []).map((file) => ({
                key: file.TaskFileId,
                ...file,
                processingTime: `${file.ProcessingStartTime} ~ ${file.ProcessingEndTime}`,
              }))}
              columns={[
                {
                  title: "文件名",
                  dataIndex: "FileName",
                  width: 200,
                },
                {
                  title: "状态",
                  dataIndex: "Status",
                  width: 100,
                  render: (status: string) =>
                    status === "completed" ? (
                      <Tag color="success" icon={<CheckCircleOutlined />}>
                        检测完成
                      </Tag>
                    ) : (
                      <Tag color="error" icon={<CloseCircleOutlined />}>
                        检测失败
                      </Tag>
                    ),
                },
                {
                  title: "分析报告",
                  dataIndex: "LlmResult",
                  ellipsis: true,
                },
                {
                  title: "处理时间",
                  dataIndex: "processingTime",
                  width: 200,
                },
                {
                  title: "操作",
                  dataIndex: "file",
                  width: 100,
                  render: (file, record) => (
                    <Button
                      type="primary"
                      size="small"
                      onClick={() => handleFileClick(record)}
                    >
                      查看详情
                    </Button>
                  ),
                },
              ]}
              pagination={false}
              size="small"
            />
          </Card>
        </div>
      </Drawer>

      {/* 文件详情弹窗 */}
      <Modal
        open={fileModalOpen}
        onCancel={handleModalClose}
        title={`文件详情 - ${currentFile?.FileName}`}
        width="90%"
        style={{ top: 20, paddingBottom: 0, maxWidth: "90vw" }}
        styles={{
          body: {
            height: "calc(90vh - 110px)",
            overflowY: "auto",
            padding: "16px",
          },
        }}
        footer={[
          <Button key="cancel" onClick={handleModalClose}>
            取消
          </Button>,
          <Button key="save" type="primary" onClick={handleSave}>
            保存核验
          </Button>,
        ]}
      >
        {currentFile && (
          <div style={{ height: "100%" }}>
            <Row gutter={24} style={{ height: "100%" }}>
              <Col span={14} style={{ height: "100%" }}>
                <Card
                  title="分析结果"
                  size="small"
                  styles={{
                    body: {
                      height: "calc(100% - 57px)",
                      overflowY: "auto",
                      padding: "16px",
                    },
                  }}
                  style={{ height: "100%" }}
                  extra={
                    <Button
                      type="text"
                      icon={<EditOutlined />}
                      size="small"
                      onClick={() => setIsEditing(!isEditing)}
                    >
                      {isEditing ? "预览" : "编辑"}
                    </Button>
                  }
                >
                  {/* AI分析报告 - 使用 Quill 富文本编辑器 */}
                  <QuillEditor
                    value={currentFile.LlmResult || ""}
                    onChange={(content) => setEditableMarkdown(content)}
                    editable={isEditing}
                    placeholder="暂无分析结果..."
                    minHeight={400}
                  />
                </Card>
              </Col>
              <Col span={10} style={{ height: "100%" }}>
                <Card
                  title="原始图像"
                  size="small"
                  styles={{
                    body: {
                      height: "calc(100% - 57px)",
                      overflowY: "auto",
                      padding: "16px",
                    },
                  }}
                  extra={
                    <Space>
                      <Button
                        type="text"
                        icon={
                          isZoomed ? <CompressOutlined /> : <ExpandOutlined />
                        }
                        size="small"
                        onClick={() => setIsZoomed(!isZoomed)}
                      >
                        {isZoomed ? "还原" : "缩放"}
                      </Button>
                      <Button
                        type="text"
                        icon={<DownloadOutlined />}
                        size="small"
                        onClick={() => {
                          const downloadUrl = `${filePreviewPath}?FileId=${currentFile.FileId}&ProjectId=${reportData.ProjectId}&UseId=${getUserId()}`;

                          const link = document.createElement("a");
                          link.href = downloadUrl;
                          link.download = currentFile.FileName;
                          link.style.display = "none";

                          document.body.appendChild(link);
                          link.click();
                          document.body.removeChild(link);

                          message.success(`正在下载 ${currentFile.FileName}`);
                        }}
                      >
                        下载
                      </Button>
                    </Space>
                  }
                >
                  <div style={{ textAlign: "center", marginBottom: 24 }}>
                    <img
                      src={`${filePreviewPath}?FileId=${currentFile.FileId}&ProjectId=${reportData.ProjectId}&UseId=${getUserId()}`}
                      alt={currentFile.FileName}
                      style={{
                        width: "100%",
                        minHeight: 200,
                        borderRadius: 8,
                        backgroundColor: "#f5f5f5",
                        objectFit: "contain",
                        cursor: "pointer",
                      }}
                      onClick={() => setIsZoomed(true)}
                    />
                  </div>

                  {/* 核验表单 */}
                  <div
                    style={{ borderTop: "1px solid #e8e8e8", paddingTop: 16 }}
                  >
                    <Title level={5} style={{ marginBottom: 16 }}>
                      核验
                    </Title>

                    <div style={{ marginBottom: 16 }}>
                      <Radio.Group
                        value={verificationStatus}
                        onChange={(e) => setVerificationStatus(e.target.value)}
                      >
                        <Row gutter={[16, 8]}>
                          <Col span={24}>
                            <Radio value="confirm">确认问题</Radio>
                          </Col>
                          <Col span={24}>
                            <Radio value="misreport">误报</Radio>
                          </Col>
                          <Col span={24}>
                            <Radio value="other">其他问题</Radio>
                          </Col>
                        </Row>
                      </Radio.Group>
                    </div>

                    <div>
                      <Text strong>备注</Text>
                      <TextArea
                        value={verificationNotes}
                        onChange={(e) => setVerificationNotes(e.target.value)}
                        placeholder="在此添加核验备注..."
                        rows={4}
                        style={{ marginTop: 8 }}
                      />
                    </div>
                  </div>
                </Card>
              </Col>
            </Row>
          </div>
        )}
      </Modal>
      {/* 图片缩放弹窗 */}
      {currentFile && (
        <Modal
          open={isZoomed}
          onCancel={() => setIsZoomed(false)}
          footer={null}
          width="80vw"
          height="80vh"
          style={{ top: 20 }}
          title={currentFile.FileName}
          centered
        >
          <div
            style={{
              textAlign: "center",
              padding: "20px 0",
              height: "calc(80vh - 120px)",
              overflow: "hidden",
            }}
          >
            <img
              src={`${filePreviewPath}?FileId=${currentFile.FileId}&ProjectId=${reportData.ProjectId}&UseId=${getUserId()}`}
              // src="https://img-s.msn.cn/tenant/amp/entityid/AA1IGBOh.img?w=640&h=426&m=6"
              alt={currentFile.FileName}
              style={{
                width: "100%",
                maxHeight: "100%",
                objectFit: "contain",
              }}
            />
          </div>
        </Modal>
      )}
    </>
  );
}
