import React, { useState, useMemo } from "react";
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
  Layout,
  Collapse,
  Breadcrumb,
  Tooltip,
  Image,
  Modal,
} from "antd";
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  FileImageOutlined,
  CaretRightOutlined,
  RollbackOutlined,
  ExportOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import { reportAPI, userAPI, getUserId } from "../../utils/api";
import { TaskFile, Report, User, DefectRecord } from "../../utils/data";


const { Title, Text, Paragraph } = Typography;
const { Content, Sider } = Layout;
const { Panel } = Collapse;

interface ReportPreviewPageProps {
  taskId: string;
  projectId: string;
  projectName: string;
  onBack: () => void;
  onReview?: () => void;
}

/**
 * 显示带缺陷标注的图片缩略图/预览。
 *
 * 实现思路：
 *  - 外层容器用 paddingTop 确定矫正后的宽高比（metaHeight/metaWidth），
 *    使容器在视觉上与矫正后图像尺寸一致。
 *  - img 绝对居中并施加与 ReportEditorPage 相同的 CSS 变换（先旋转再翻转），
 *    使原始文件在视觉上以正确方向填满容器。
 *  - 缺陷标注框坐标已存储在矫正后坐标系中，直接以 metaWidth/metaHeight 为基准
 *    计算百分比定位，无需逆变换。
 */
const DefectImage = ({ file, projectId, userId, style, showLabel = true, defects = null }: {
  file: TaskFile, projectId: string, userId: string,
  style?: React.CSSProperties, showLabel?: boolean, defects?: any[] | null
}) => {
  const corrRotation = file.CorrectionRotation ?? 0;
  const flipH = file.CorrectionFlip ? -1 : 1;
  const normR = ((corrRotation % 360) + 360) % 360;
  const isAxesSwapped = normR === 90 || normR === 270;

  let metaWidth = 1920, metaHeight = 1080;
  let visionResult: any = { results: [] };
  try {
    visionResult = JSON.parse(file.VisionResult || '{"results":[]}');
    metaWidth = visionResult.metadata?.width || 1920;
    metaHeight = visionResult.metadata?.height || 1080;
  } catch (e) { /* 保持默认值 */ }

  // 构建单个标注框（直接使用矫正坐标系百分比）
  const makeOverlay = (minX: number, minY: number, maxX: number, maxY: number, label: string, key: string) => (
    <div key={key} style={{
      position: "absolute",
      top: `${(minY / metaHeight) * 100}%`,
      left: `${(minX / metaWidth) * 100}%`,
      width: `${((maxX - minX) / metaWidth) * 100}%`,
      height: `${((maxY - minY) / metaHeight) * 100}%`,
      border: "1px dashed #ff4d4f",
      pointerEvents: "none",
      zIndex: 10,
    }}>
      {showLabel && (
        <span style={{
          position: "absolute", top: -18, left: -1,
          background: '#ff4d4f', color: '#fff', fontSize: '10px',
          padding: '0 4px', borderRadius: '2px', whiteSpace: 'nowrap',
          transform: 'scale(0.8)', transformOrigin: 'left bottom',
        }}>{label}</span>
      )}
    </div>
  );

  const overlays: JSX.Element[] = [];
  try {
    if (defects && defects.length > 0) {
      defects.forEach((item: any, i: number) => {
        let minX = 0, minY = 0, maxX = 0, maxY = 0, isValid = false;
        if (item.isDefectRecord && item.Geometry) {
          try {
            const geo = JSON.parse(item.Geometry);
            if (geo.type === 'rect') {
              minX = geo.x; minY = geo.y; maxX = geo.x + geo.w; maxY = geo.y + geo.h; isValid = true;
            } else if (geo.type === 'circle') {
              minX = geo.x - geo.r; minY = geo.y - geo.r; maxX = geo.x + geo.r; maxY = geo.y + geo.r; isValid = true;
            } else if (geo.type === 'polygon' && Array.isArray(geo.points)) {
              const xs = geo.points.map((p: any) => p.x);
              const ys = geo.points.map((p: any) => p.y);
              minX = Math.min(...xs); minY = Math.min(...ys); maxX = Math.max(...xs); maxY = Math.max(...ys); isValid = true;
            }
          } catch (e) { }
        } else if (!item.isDefectRecord && item.vvContour?.length > 0) {
          const xs = item.vvContour.map((p: any) => p[0]);
          const ys = item.vvContour.map((p: any) => p[1]);
          minX = Math.min(...xs); minY = Math.min(...ys); maxX = Math.max(...xs); maxY = Math.max(...ys); isValid = true;
        }
        if (isValid) overlays.push(makeOverlay(minX, minY, maxX, maxY, item.strName || item.DefectName, `defect-${i}`));
      });
    } else if (!defects && visionResult.results) {
      visionResult.results.forEach((item: any, i: number) => {
        if (!item.vvContour?.length) return;
        const xs = item.vvContour.map((p: any) => p[0]);
        const ys = item.vvContour.map((p: any) => p[1]);
        overlays.push(makeOverlay(Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys), item.strName, `model-${i}`));
      });
    }
  } catch (e) { /* 解析失败时跳过标注 */ }

  // 旋转90°/270°时，原始图像宽高互换；img 宽度设为 metaH/metaW 使旋转后恰好填满容器
  const imgWidth = isAxesSwapped ? `${(metaHeight / metaWidth) * 100}%` : '100%';

  return (
    <div style={{
      position: 'relative',
      paddingTop: `${(metaHeight / metaWidth) * 100}%`,  // 锁定矫正后宽高比
      overflow: 'hidden',
      background: '#f5f5f5',
      ...style,
    }}>
      <img
        src={`/api/v1/files/preview?FileId=${file.FileId}&ProjectId=${projectId}&UserId=${userId}`}
        alt="preview"
        style={{
          position: 'absolute',
          display: 'block',
          width: imgWidth,
          height: 'auto',
          top: '50%',
          left: '50%',
          // translate(-50%,-50%) 先将 img 居中，再旋转翻转，使其恰好填满容器
          transform: `translate(-50%, -50%) scale(${flipH}, 1) rotate(${corrRotation}deg)`,
          transformOrigin: 'center center',
        }}
      />
      {overlays}
    </div>
  );
};

const ReportPreviewPage: React.FC<ReportPreviewPageProps> = ({
  taskId,
  projectId,
  projectName,
  onBack,
  onReview,
}) => {
  const [activeTab, setActiveTab] = useState<"all" | "has_defects" | "no_defects">("all");
  const [currentPage, setCurrentPage] = useState(1);
  const [previewFile, setPreviewFile] = useState<TaskFile | null>(null);
  const [scale, setScale] = useState(1);
  const pageSize = 10;

  // 1. 获取报告详情
  const { data: reportResp } = useRequest(() => reportAPI.getReportDetail(taskId));
  const report = reportResp?.Data;

  // 2. 获取用户信息
  const { data: userResp } = useRequest(() => userAPI.getUser(getUserId()));
  const currentUser = userResp?.Data;

  // 3. 获取文件列表
  const {
    data: filesResp,
    loading: filesLoading,
  } = useRequest(() => reportAPI.getReportFiles(taskId, "all"), {
    refreshDeps: [taskId],
  });

  const allFiles = filesResp?.Data || [];

  // 统一获取缺陷列表的逻辑 - 仅使用 defect_record 表数据
  const getDefectsForFile = (f: TaskFile) => {
    // 只使用 DefectRecords,
    if (f.DefectRecords && f.DefectRecords.length > 0) {
      return f.DefectRecords.map(dr => ({
        strName: dr.DefectName,
        isDefectRecord: true,
        ...dr
      }));
    }

    return [];
  };

  // 统一判定逻辑
  const hasDefects = (f: TaskFile) => {
    const defects = getDefectsForFile(f);
    return defects.length > 0;
  };

  // 统计数据
  const stats = useMemo(() => {
    const confirmed = allFiles.filter(f => f.ReviewStatus === "CONFIRMED");
    const unconfirmed = allFiles.filter(f => f.ReviewStatus !== "CONFIRMED");

    return {
      confirmed: {
        total: confirmed.length,
        hasDefects: confirmed.filter(hasDefects).length,
        noDefects: confirmed.filter(f => !hasDefects(f)).length
      },
      unconfirmed: {
        total: unconfirmed.length,
        hasDefects: unconfirmed.filter(hasDefects).length,
        noDefects: unconfirmed.filter(f => !hasDefects(f)).length
      }
    };
  }, [allFiles]);

  const filteredFiles = useMemo(() => {
    if (activeTab === "has_defects") return allFiles.filter(hasDefects);
    if (activeTab === "no_defects") return allFiles.filter(f => !hasDefects(f));
    return allFiles;
  }, [allFiles, activeTab]);

  const formatTime = (timeStr?: string) => {
    if (!timeStr) return "-";
    return timeStr.replace('T', ' ').substring(0, 19); // 包含秒
  };

  const getFileInfo = (file: TaskFile) => {
    try {
      const result = JSON.parse(file.VisionResult || '{}');
      const width = result.metadata?.width || 1920;
      const height = result.metadata?.height || 1080;
      return { width, height };
    } catch (e) {
      return { width: 1920, height: 1080 };
    }
  };

  return (
    <Layout style={{ height: "100%", background: "#f0f2f5", margin: 0, padding: 0 }}>
      {/* 预览 Modal */}
      <Modal
        open={!!previewFile}
        onCancel={() => {
          setPreviewFile(null);
          setScale(1);
        }}
        footer={null}
        width="90%"
        centered
        bodyStyle={{ padding: 0, height: '85vh', display: 'flex', flexDirection: 'column' }}
        style={{ top: 20 }}
      >
        {previewFile && (
          <>
            <div style={{ padding: '12px 24px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text strong style={{ fontSize: '16px' }}>{previewFile.FileName}</Text>
              <Space>
                <Button icon={<ZoomOutOutlined />} onClick={() => setScale(s => Math.max(0.2, s - 0.2))} />
                <span style={{ minWidth: 60, textAlign: 'center' }}>{(scale * 100).toFixed(0)}%</span>
                <Button icon={<ZoomInOutlined />} onClick={() => setScale(s => s + 0.2)} />
              </Space>
            </div>
            <div style={{ flex: 1, overflow: 'auto', background: '#f0f2f5', padding: 24, display: 'flex', justifyContent: 'center', alignItems: 'flex-start' }}>
              <div style={{
                transform: `scale(${scale})`,
                transformOrigin: 'top center',
                transition: 'transform 0.2s',
                boxShadow: '0 8px 24px rgba(0,0,0,0.1)',
                width: '100%',
              }}>
                <DefectImage
                  file={previewFile}
                  projectId={projectId}
                  userId={getUserId()}
                  defects={getDefectsForFile(previewFile)}
                  style={{ width: '100%' }}
                />
              </div>
            </div>
          </>
        )}
      </Modal>

      {/* 左侧固定统计栏 */}
      <Sider width={300} theme="light" style={{ borderRight: "1px solid #f0f0f0", padding: '24px', overflowY: 'auto' }}>
        <Button icon={<ArrowLeftOutlined />} onClick={onBack} type="text" style={{ marginBottom: 24, padding: 0 }}>返回任务列表</Button>

        <div style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <Text type="secondary">报告状态:</Text>
            <Space size={4}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: report?.Status === 'COMPLETED' ? '#52c41a' : '#1890ff', display: 'inline-block' }} />
              <Text>{report?.Status === 'COMPLETED' ? '已归档' : '待审核'}</Text>
            </Space>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <Text type="secondary">生成时间:</Text>
            <Text>{formatTime(report?.CreatedAt)}</Text>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Text type="secondary">操作人:</Text>
            <Text>{currentUser?.username || "质检员"}</Text>
          </div>
        </div>

        <Divider style={{ margin: '24px 0' }} />

        <Title level={5} style={{ marginBottom: 20 }}>检测统计</Title>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* 已确认卡片 - 绿色 */}
          <div style={{ background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text type="secondary" style={{ color: '#52c41a' }}>已确认文件</Text>
              <div style={{ background: '#52c41a', color: '#fff', borderRadius: '10px', padding: '0 8px', fontSize: '12px' }}>{stats.confirmed.total}</div>
            </div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a', marginBottom: 8 }}>
              {stats.confirmed.total}<span style={{ fontSize: '14px', fontWeight: 'normal', color: '#8c8c8c' }}>/{allFiles.length}</span>
            </div>
            <div style={{ fontSize: '12px', color: '#8c8c8c', display: 'flex', gap: 12 }}>
              <span>无缺陷: <Text strong style={{ color: '#52c41a' }}>{stats.confirmed.noDefects}个</Text></span>
              <span>有缺陷: <Text strong style={{ color: '#ff4d4f' }}>{stats.confirmed.hasDefects}个</Text></span>
            </div>
          </div>

          {/* 未确认卡片 - 黄色 */}
          <div style={{ background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text type="secondary" style={{ color: '#faad14' }}>未确认文件</Text>
              <div style={{ background: '#faad14', color: '#fff', borderRadius: '10px', padding: '0 8px', fontSize: '12px' }}>{stats.unconfirmed.total}</div>
            </div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#faad14', marginBottom: 4 }}>
              {stats.unconfirmed.total}
            </div>
            <div style={{ fontSize: '12px', color: '#8c8c8c' }}>待审核</div>
          </div>

          {/* 缺陷统计卡片 - 红色 */}
          <div style={{ background: '#fff1f0', border: '1px solid #ffa39e', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text type="secondary" style={{ color: '#ff4d4f' }}>缺陷统计</Text>
              <div style={{ background: '#ff4d4f', color: '#fff', borderRadius: '10px', padding: '0 8px', fontSize: '12px' }}>{report?.TotalDefects || 0}</div>
            </div>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ff4d4f', marginBottom: 8 }}>
              {report?.TotalDefects || 0}
            </div>
            <div style={{ fontSize: '12px', color: '#8c8c8c', display: 'flex', gap: 12 }}>
              <span>严重: <Text strong style={{ color: '#cf1322' }}>{report?.SevereDefects || 0}处</Text></span>
              <span>一般: <Text strong style={{ color: '#fa8c16' }}>{report?.NormalDefects || 0}处</Text></span>
            </div>
          </div>
        </div>

        <div style={{ marginTop: 40 }}>
          <Button
            block
            icon={<DownloadOutlined />}
            style={{ marginBottom: 12, height: 40 }}
            onClick={() => {
              if (report?.ReportId) {
                const url = reportAPI.downloadReport(report.ReportId);
                const link = document.createElement('a');
                link.href = url;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
              } else {
                message.error("无法获取报告ID");
              }
            }}
          >
            下载报告
          </Button>
          <Button
            block
            type="primary"
            icon={<ExportOutlined />}
            style={{ height: 40 }}
            onClick={() => {
              if (onReview) {
                onReview();
              } else {
                message.info("请通过报告列表进入审核");
              }
            }}
          >
            查看审核详情
          </Button>
        </div>
      </Sider>

      {/* 右侧内容区 */}
      <Content style={{ padding: '24px 40px', overflowY: 'auto' }}>
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>
          <Breadcrumb style={{ marginBottom: 24 }} items={[
            { title: '项目管理' },
            { title: projectName },
            { title: '任务管理' },
            { title: report?.TaskName || `任务 #${taskId.slice(-4)}` },
            { title: '检测报告' },
          ]} />

          <div style={{ marginBottom: 40 }}>
            <Title level={2}>{report?.TaskName || '检测任务'} - 检测报告</Title>
            <Space size={24}>
              <Text type="secondary">文件总数: <Text strong style={{ color: '#595959' }}>{allFiles.length}个</Text></Text>
              <Text type="secondary">生成时间: <Text strong style={{ color: '#595959' }}>{formatTime(report?.CreatedAt)}</Text></Text>
              <Text type="secondary">操作人: <Text strong style={{ color: '#595959' }}>{currentUser?.username || "质检员"}</Text></Text>
            </Space>
          </div>

          <section style={{ marginBottom: 48 }}>
            <Title level={4}>1. 缺陷总览</Title>
            <div style={{ background: '#fff', padding: '24px', borderRadius: '8px', border: '1px solid #f0f0f0', fontSize: '15px', lineHeight: '28px', color: '#595959' }}>
              本次检测共处理 {allFiles.length} 个文件，其中 {stats.confirmed.total} 个文件已确认，{stats.unconfirmed.total} 个文件待审核。在已确认的文件中，检测到 {report?.TotalDefects || 0} 处缺陷，包括 {report?.SevereDefects || 0} 处严重缺陷和 {report?.NormalDefects || 0} 处一般缺陷。
            </div>
          </section>

          <section>
            <Title level={4}>2. 详细检测结果</Title>
            <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #f0f0f0', overflow: 'hidden' }}>
              {/* 过滤器 */}
              <div style={{ padding: '20px 24px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'flex-end' }}>
                <Space>
                  <Button type={activeTab === 'all' ? 'primary' : 'default'} onClick={() => { setActiveTab('all'); setCurrentPage(1); }} size="small" shape="round">全部 ({allFiles.length})</Button>
                  <Button type={activeTab === 'has_defects' ? 'primary' : 'default'} onClick={() => { setActiveTab('has_defects'); setCurrentPage(1); }} size="small" shape="round">有缺陷 ({allFiles.filter(hasDefects).length})</Button>
                  <Button type={activeTab === 'no_defects' ? 'primary' : 'default'} onClick={() => { setActiveTab('no_defects'); setCurrentPage(1); }} size="small" shape="round">无缺陷 ({allFiles.filter(f => !hasDefects(f)).length})</Button>
                </Space>
              </div>

              <div style={{ padding: '0 24px' }}>
                <List
                  dataSource={filteredFiles}
                  loading={filesLoading}
                  pagination={{
                    current: currentPage,
                    pageSize: pageSize,
                    onChange: (page) => setCurrentPage(page),
                    total: filteredFiles.length,
                    showSizeChanger: false,
                    position: 'bottom',
                    align: 'center',
                    style: { marginTop: '24px', marginBottom: '24px' }
                  }}
                  renderItem={(file) => {
                    const defects = getDefectsForFile(file);
                    const { width, height } = getFileInfo(file);

                    return (
                      <div style={{ borderBottom: '1px solid #f0f0f0', padding: '8px 0' }}>
                        <Collapse
                          ghost
                          expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} style={{ fontSize: '12px', color: '#8c8c8c' }} />}
                        >
                          <Panel
                            header={
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                                <Space size="large">
                                  {file.ReviewStatus === "CONFIRMED" ? (
                                    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: '16px' }} />
                                  ) : (
                                    <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid #faad14' }} />
                                  )}
                                  <Text strong style={{ fontSize: '15px' }}>{file.FileName || "未知文件名"}</Text>
                                  {defects.length > 0 ? (
                                    <Space size={4}>
                                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ff4d4f', display: 'inline-block' }} />
                                      <Text type="danger" style={{ fontSize: '13px' }}>{defects.length}处缺陷</Text>
                                    </Space>
                                  ) : (
                                    <Space size={4}>
                                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#52c41a', display: 'inline-block' }} />
                                      <Text type="success" style={{ fontSize: '13px' }}>无缺陷</Text>
                                    </Space>
                                  )}
                                </Space>
                                <div style={{ marginRight: 16 }}>
                                  {file.ReviewStatus === "CONFIRMED" ? (
                                    <Tag color="success" style={{ margin: 0, borderRadius: '4px', border: 'none', background: '#f6ffed', color: '#52c41a' }}>已确认</Tag>
                                  ) : (
                                    <Tag color="default" style={{ margin: 0, borderRadius: '4px', border: 'none', background: '#fafafa', color: '#8c8c8c' }}>待审核</Tag>
                                  )}
                                </div>
                              </div>
                            }
                            key={file.TaskFileId}
                          >
                            <div style={{ padding: '8px 40px 16px 40px' }}>
                              <Row gutter={32}>
                                <Col span={7}>
                                  <div style={{ borderRadius: '8px', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.08)', border: '1px solid #f0f0f0', position: 'relative', cursor: 'pointer' }}
                                    onClick={() => {
                                      setPreviewFile(file);
                                      setScale(1);
                                    }}
                                  >
                                    <DefectImage
                                      file={file}
                                      projectId={projectId}
                                      userId={getUserId()}
                                      defects={defects}
                                      style={{ width: '100%' }}
                                      showLabel={true}
                                    />
                                    <div style={{
                                      position: 'absolute',
                                      top: 0,
                                      left: 0,
                                      right: 0,
                                      bottom: 0,
                                      background: 'rgba(0,0,0,0)',
                                      transition: 'background 0.3s',
                                      display: 'flex',
                                      justifyContent: 'center',
                                      alignItems: 'center',
                                      opacity: 0
                                    }}
                                      onMouseEnter={(e) => {
                                        e.currentTarget.style.background = 'rgba(0,0,0,0.3)';
                                        e.currentTarget.style.opacity = '1';
                                      }}
                                      onMouseLeave={(e) => {
                                        e.currentTarget.style.background = 'rgba(0,0,0,0)';
                                        e.currentTarget.style.opacity = '0';
                                      }}
                                    >
                                      <Space style={{ color: '#fff' }}>
                                        <FileImageOutlined /> 查看大图
                                      </Space>
                                    </div>
                                  </div>
                                </Col>
                                <Col span={17}>
                                  <div style={{ fontSize: '13px', color: '#8c8c8c', marginBottom: 20, display: 'flex', gap: 32 }}>
                                    <span>尺寸: <Text strong style={{ color: '#595959' }}>{width}×{height}</Text></span>
                                    <span>检测时间: <Text strong style={{ color: '#595959' }}>{formatTime(file.ProcessingEndTime)}</Text></span>
                                  </div>

                                  {/* --- 新增：底片信息展示 --- */}
                                  <div style={{ background: '#f9f9f9', padding: '12px', borderRadius: '4px', marginBottom: '16px', border: '1px solid #f0f0f0' }}>
                                    <Row gutter={24}>
                                      <Col span={6}>
                                        <Text type="secondary" style={{ fontSize: '12px' }}>焊口编号</Text>
                                        <div style={{ fontWeight: 500 }}>{file.WeldId || '-'}</div>
                                      </Col>
                                      <Col span={6}>
                                        <Text type="secondary" style={{ fontSize: '12px' }}>片号</Text>
                                        <div style={{ fontWeight: 500 }}>{file.FilmNumber || '-'}</div>
                                      </Col>
                                      <Col span={6}>
                                        <Text type="secondary" style={{ fontSize: '12px' }}>黑度</Text>
                                        <div style={{ fontWeight: 500 }}>{file.FilmDensity || '-'}</div>
                                      </Col>
                                      <Col span={6}>
                                        <Text type="secondary" style={{ fontSize: '12px' }}>灵敏度</Text>
                                        <div style={{ fontWeight: 500 }}>{file.Sensitivity || '-'}</div>
                                      </Col>
                                    </Row>
                                  </div>

                                  {defects.length > 0 ? (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                      <div style={{ color: '#ff4d4f', fontSize: '14px', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <InfoCircleOutlined /> <span>检测到 {defects.length} 处缺陷</span>
                                      </div>
                                      {defects.map((d: any, idx: number) => {
                                        const isSevere = d.strName.toLowerCase().includes('crack') || d.strName.toLowerCase().includes('unfused') || d.strName.toLowerCase().includes('penetration');

                                        // 直接使用 Position 字段（与 ReportEditorPage 中保持一致的用户录入位置信息）
                                        const position = d.Position || "-";
                                        const size = d.Size || "-";

                                        return (
                                          <div key={idx} style={{ background: isSevere ? '#fff1f0' : '#fff7e6', padding: '16px', borderRadius: '8px', border: `1px solid ${isSevere ? '#ffa39e' : '#ffe58f'}`, position: 'relative' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                              <div style={{ flex: 1 }}>
                                                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                                  <Space>
                                                    <Text strong style={{ fontSize: '15px' }}>缺陷类型: {d.strName}</Text>
                                                    <Tag color={isSevere ? "red" : "orange"} style={{ border: 'none', borderRadius: '10px' }}>{isSevere ? "严重" : "一般"}</Tag>
                                                  </Space>

                                                  {/* 只显示 defect_record 表的数据 */}
                                                  <div style={{ marginTop: 4, display: 'grid', gridTemplateColumns: 'auto auto auto', gap: '8px 24px', fontSize: '13px', color: '#595959' }}>
                                                    <div><span style={{ color: '#8c8c8c' }}>位置:</span> {position}</div>
                                                    <div><span style={{ color: '#8c8c8c' }}>尺寸:</span> {size}</div>
                                                    <div><span style={{ color: '#8c8c8c' }}>等级:</span> {d.Grade || '-'}</div>
                                                    <div style={{ gridColumn: '1 / -1' }}><span style={{ color: '#8c8c8c' }}>备注:</span> {d.Remark || '-'}</div>
                                                  </div>
                                                </Space>
                                              </div>
                                            </div>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  ) : (
                                    <div style={{ background: '#f6ffed', padding: '20px', borderRadius: '8px', border: '1px solid #b7eb8f', display: 'flex', alignItems: 'center', gap: 12 }}>
                                      <CheckCircleOutlined style={{ color: '#52c41a', fontSize: '18px' }} />
                                      <Text type="success" strong>未检测到缺陷</Text>
                                    </div>
                                  )}
                                </Col>
                              </Row>
                            </div>
                          </Panel>
                        </Collapse>
                      </div>
                    );
                  }}
                />
              </div>
            </div>
          </section>
        </div>
      </Content>
    </Layout>
  );
};

export default ReportPreviewPage;
