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
  Progress,
  Tooltip,
} from "antd";
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileImageOutlined,
  SaveOutlined,
  DoubleRightOutlined,
  LeftOutlined,
  RightOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  DragOutlined,
  BorderOutlined,
  BgColorsOutlined,
  RotateLeftOutlined,
  RotateRightOutlined,
  ExpandOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import { reportAPI, getUserId } from "../../utils/api";
import { TaskFile, Report } from "../../utils/data";

const { Content, Sider } = Layout;
const { Title, Text, Link } = Typography;

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

  const confirmedCount = files.filter(f => f.ReviewStatus === "CONFIRMED").length;
  const unconfirmedCount = files.length - confirmedCount;
  const progressPercent = files.length > 0 ? Math.round((confirmedCount / files.length) * 100) : 0;

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
  }, [selectedFile, form]);

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
      {/* 左侧文件列表 */}
      <Sider width={280} theme="light" style={{ borderRight: "1px solid #f0f0f0", display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: "16px", borderBottom: "1px solid #f0f0f0" }}>
          <Space direction="vertical" style={{ width: "100%" }}>
            <Button icon={<ArrowLeftOutlined />} onClick={onBack} type="text">返回列表</Button>
            <Title level={4} style={{ margin: "8px 0 0 0" }}>检测任务 #{taskId.slice(-4)}</Title>
          </Space>
          
          <div style={{ marginTop: 20, textAlign: 'center', background: '#fafafa', padding: '16px', borderRadius: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <Text type="secondary">文件总数: {files.length}个</Text>
              <Text type="secondary">{progressPercent}%</Text>
            </div>
            <Progress percent={progressPercent} size="small" showInfo={false} />
            <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: 12 }}>
              <div>
                <div style={{ color: '#52c41a', fontSize: '18px', fontWeight: 'bold' }}>{confirmedCount}</div>
                <div style={{ fontSize: '12px', color: '#8c8c8c' }}>已确认</div>
              </div>
              <div style={{ borderLeft: '1px solid #d9d9d9' }} />
              <div>
                <div style={{ color: '#faad14', fontSize: '18px', fontWeight: 'bold' }}>{unconfirmedCount}</div>
                <div style={{ fontSize: '12px', color: '#8c8c8c' }}>未确认</div>
              </div>
            </div>
          </div>
        </div>
        
        <div style={{ flex: 1, overflowY: 'auto' }}>
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
                <Space>
                  {file.ReviewStatus === "CONFIRMED" ? (
                    <CheckCircleOutlined style={{ color: "#52c41a" }} />
                  ) : (
                    <div style={{ width: 14, height: 14, borderRadius: '50%', border: '2px solid #faad14' }} />
                  )}
                  <Text ellipsis style={{ width: 180, color: selectedFile?.TaskFileId === file.TaskFileId ? "#1890ff" : "inherit" }}>
                    {file.FileName}
                  </Text>
                </Space>
              </List.Item>
            )}
          />
        </div>

        <div style={{ padding: '16px', borderTop: '1px solid #f0f0f0' }}>
          <Button type="primary" block icon={<CheckCircleOutlined />} onClick={() => message.info("批量审核功能开发中")}>
            批量确认
          </Button>
        </div>
      </Sider>
      
      {/* 中间编辑区 */}
      <Content style={{ display: "flex", flexDirection: "column", background: '#f0f2f5' }}>
        {/* 顶部工具栏 */}
        <div style={{ height: 48, background: '#1f1f1f', color: '#fff', display: 'flex', alignItems: 'center', padding: '0 16px', justifyContent: 'space-between' }}>
          <Space size="large">
            <Tooltip title="选择"><Button type="text" ghost icon={<DragOutlined />} /></Tooltip>
            <Tooltip title="缺陷标注"><Button type="text" ghost icon={<BorderOutlined />} /></Tooltip>
            <Tooltip title="文本标注"><Button type="text" ghost icon={<BgColorsOutlined />} /></Tooltip>
            <Tooltip title="标尺"><Button type="text" ghost icon={<ExpandOutlined />} /></Tooltip>
            <Divider type="vertical" style={{ background: '#434343' }} />
            <Tooltip title="平移"><Button type="text" ghost icon={<DragOutlined />} /></Tooltip>
            <Tooltip title="缩放"><Button type="text" ghost icon={<ZoomInOutlined />} /></Tooltip>
            <Tooltip title="正片/负片切换"><Button type="text" ghost>正片</Button></Tooltip>
          </Space>
          
          <Space size="middle">
            <Button type="text" ghost icon={<RotateLeftOutlined />} />
            <Button type="text" ghost icon={<RotateRightOutlined />} />
            <Button type="text" ghost icon={<ZoomInOutlined />} />
            <Text style={{ color: '#fff', fontSize: '12px' }}>100%</Text>
            <Button type="text" ghost icon={<ZoomOutOutlined />} />
          </Space>
        </div>

        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {selectedFile ? (
            <div style={{ position: "relative" }}>
              <img 
                src={`/api/v1/files/preview?FileId=${selectedFile.FileId}&ProjectId=${projectId}&UserId=${getUserId()}`} 
                alt="preview" 
                style={{ maxHeight: "calc(100vh - 250px)", maxWidth: "100%", boxShadow: "0 4px 12px rgba(0,0,0,0.15)" }} 
              />
              {/* 模拟标注框 */}
              <div style={{ position: "absolute", top: "20%", left: "30%", width: "100px", height: "100px", border: "2px solid #ff4d4f", pointerEvents: "none" }}>
                <span style={{ position: "absolute", top: -20, left: -2, background: '#ff4d4f', color: '#fff', fontSize: '10px', padding: '0 4px' }}>裂纹 0.98</span>
              </div>
            </div>
          ) : (
            <Empty description="请从左侧选择图片开始审核" />
          )}
          
          {/* 底部悬浮控制条 */}
          {selectedFile && (
            <div style={{ position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)', background: 'rgba(255,255,255,0.9)', padding: '8px 24px', borderRadius: '24px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
              <Space size="large">
                <Button type="text" icon={<LeftOutlined />} onClick={() => {
                  const idx = files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId);
                  if (idx > 0) setSelectedFile(files[idx - 1]);
                }} disabled={files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId) === 0}>上一个</Button>
                <Text strong>{files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId) + 1} / {files.length}</Text>
                <Button type="text" onClick={() => {
                  const idx = files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId);
                  if (idx < files.length - 1) setSelectedFile(files[idx + 1]);
                }} disabled={files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId) === files.length - 1}>下一个 <RightOutlined /></Button>
                <Divider type="vertical" />
                <Button type="primary" size="middle" icon={<SaveOutlined />} onClick={handleSave}>保存并确认</Button>
                <Link onClick={() => onBack()}>预览报告</Link>
              </Space>
            </div>
          )}
        </div>
      </Content>

      {/* 右侧审核信息 */}
      <Sider width={300} theme="light" style={{ borderLeft: "1px solid #f0f0f0", padding: '16px', overflowY: 'auto' }}>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <Title level={5} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              缺陷信息
              {!selectedFile?.VisionResult && <Text type="secondary" style={{ fontSize: '12px', fontWeight: 'normal' }}>尚未标记缺陷</Text>}
            </Title>
            <Card size="small" style={{ background: '#fafafa', border: 'none' }}>
              <List
                size="small"
                dataSource={JSON.parse(selectedFile?.VisionResult || '{"results":[]}').results}
                renderItem={(item: any, idx: number) => (
                  <List.Item key={idx} style={{ padding: '8px 0' }}>
                    <div style={{ width: '100%' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Tag color="red">{item.strName}</Tag>
                        <Text type="secondary">置信度: {(item.score * 100).toFixed(1)}%</Text>
                      </div>
                      <Text type="secondary" style={{ fontSize: '12px' }}>位置: (120, 340) | 尺寸: 15x12 px</Text>
                    </div>
                  </List.Item>
                )}
                locale={{ emptyText: <div style={{ color: '#bfbfbf', fontSize: '12px', textAlign: 'center', padding: '20px 0' }}>选择“缺陷标记”工具，在图像上拖拽标记缺陷位置</div> }}
              />
            </Card>
          </div>

          <div>
            <Title level={5}>底片质量</Title>
            <Form form={form} layout="vertical">
              <Form.Item name="PlateQuality">
                <Select style={{ width: '100%' }}>
                  <Select.Option value="一级">I 级 (优)</Select.Option>
                  <Select.Option value="二级">II 级 (良)</Select.Option>
                  <Select.Option value="三级">III 级 (中)</Select.Option>
                  <Select.Option value="四级">IV 级 (差)</Select.Option>
                </Select>
              </Form.Item>
            </Form>
          </div>

          <Divider style={{ margin: '8px 0' }} />

          <div>
            <Title level={5}>快捷键说明</Title>
            <div style={{ fontSize: '12px', color: '#595959', lineHeight: '24px', background: '#f5f5f5', padding: '12px', borderRadius: '4px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>滚轮:</span> <span>缩放图像</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>空格+拖拽:</span> <span>平移视图</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Ctrl+Z:</span> <span>撤销操作</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>R:</span> <span>重置视图</span></div>
            </div>
          </div>

          <div style={{ marginTop: 20 }}>
            <div style={{ fontSize: '12px', color: '#8c8c8c' }}>
              <div>窗宽: 400 | 窗位: 128</div>
              <div>当前坐标: (120, 340)</div>
              <div style={{ marginTop: 8, borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>底片评分系统 | 当前工具: 平移</div>
            </div>
          </div>
        </Space>
      </Sider>
    </Layout>
  );
};

export default ReportEditorPage;


