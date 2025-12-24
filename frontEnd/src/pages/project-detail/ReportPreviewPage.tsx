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
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import { reportAPI, userAPI, getUserId } from "../../utils/api";
import { TaskFile, Report, User } from "../../utils/data";

const { Title, Text, Paragraph } = Typography;
const { Content, Sider } = Layout;
const { Panel } = Collapse;

interface ReportPreviewPageProps {
  taskId: string;
  projectId: string;
  projectName: string;
  onBack: () => void;
}

const ReportPreviewPage: React.FC<ReportPreviewPageProps> = ({
  taskId,
  projectId,
  projectName,
  onBack,
}) => {
  const [activeTab, setActiveTab] = useState<"all" | "has_defects" | "no_defects">("all");
  const [currentPage, setCurrentPage] = useState(1);
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

  // 统一判定逻辑
  const hasDefects = (f: TaskFile) => {
    try {
      const result = JSON.parse(f.VisionResult || '{"results":[]}');
      return result.results?.some((r: any) => r.strName && r.strName.toLowerCase() !== "normal") || false;
    } catch (e) {
      return false;
    }
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
    <Layout style={{ height: "calc(100vh - 120px)", background: "#f0f2f5" }}>
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
          <Button block icon={<DownloadOutlined />} style={{ marginBottom: 12, height: 40 }}>下载报告</Button>
          <Button block type="primary" icon={<RollbackOutlined />} style={{ height: 40 }} onClick={() => message.info("请通过报告列表进入审核")}>查看审核详情</Button>
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
                    const result = JSON.parse(file.VisionResult || '{"results":[]}');
                    const defects = result.results?.filter((r: any) => r.strName && r.strName.toLowerCase() !== "normal") || [];
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
                                  <div style={{ borderRadius: '8px', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.08)', border: '1px solid #f0f0f0' }}>
                                    <img 
                                      src={`/api/v1/files/preview?FileId=${file.FileId}&ProjectId=${projectId}&UserId=${getUserId()}`} 
                                      alt="preview" 
                                      style={{ width: '100%', display: 'block', minHeight: '120px', background: '#f5f5f5' }} 
                                    />
                                  </div>
                                </Col>
                                <Col span={17}>
                                  <div style={{ fontSize: '13px', color: '#8c8c8c', marginBottom: 20, display: 'flex', gap: 32 }}>
                                    <span>尺寸: <Text strong style={{ color: '#595959' }}>{width}×{height}</Text></span>
                                    <span>检测时间: <Text strong style={{ color: '#595959' }}>{formatTime(file.ProcessingEndTime)}</Text></span>
                                  </div>
                                  
                                  {defects.length > 0 ? (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                      <div style={{ color: '#ff4d4f', fontSize: '14px', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <InfoCircleOutlined /> <span>检测到 {defects.length} 处缺陷</span>
                                      </div>
                                      {defects.map((d: any, idx: number) => {
                                        const isSevere = d.strName.toLowerCase().includes('crack') || d.strName.toLowerCase().includes('unfused') || d.strName.toLowerCase().includes('penetration');
                                        
                                        // 动态计算缺陷尺寸和位置
                                        let position = "(120, 340)";
                                        let size = "15×12 px";
                                        if (d.vvContour && d.vvContour.length > 0) {
                                          const xs = d.vvContour.map((p: any) => p[0]);
                                          const ys = d.vvContour.map((p: any) => p[1]);
                                          const minX = Math.min(...xs);
                                          const minY = Math.min(...ys);
                                          const maxX = Math.max(...xs);
                                          const maxY = Math.max(...ys);
                                          position = `(${Math.round(minX)}, ${Math.round(minY)})`;
                                          size = `${Math.round(maxX - minX)}×${Math.round(maxY - minY)} px`;
                                        }

                                        return (
                                          <div key={idx} style={{ background: isSevere ? '#fff1f0' : '#fff7e6', padding: '16px', borderRadius: '8px', border: `1px solid ${isSevere ? '#ffa39e' : '#ffe58f'}`, position: 'relative' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                              <div style={{ flex: 1 }}>
                                                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                                  <Space>
                                                    <Text strong style={{ fontSize: '15px' }}>缺陷类型: {d.strName}</Text>
                                                    <Tag color={isSevere ? "red" : "orange"} style={{ border: 'none', borderRadius: '10px' }}>{isSevere ? "严重" : "一般"}</Tag>
                                                  </Space>
                                                  <Text type="secondary" style={{ fontSize: '13px', color: isSevere ? '#cf1322' : '#d46b08' }}>
                                                    位置: {position} | 尺寸: {size} | 置信度: {(d.score * 100).toFixed(1)}%
                                                  </Text>
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
