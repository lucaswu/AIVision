import React, { useState, useEffect, useMemo, useRef } from "react";
import { ImageEditorViewer } from "./components/ImageEditorViewer";
import {
  List,
  Typography,
  Space,
  Button,
  message,
  Layout,
  Select,
  Checkbox,
  Progress,
  Tooltip,
  Pagination,
  Switch,
} from "antd";
import {
  CheckCircleOutlined,
  DoubleRightOutlined,
  LeftOutlined,
  FileTextOutlined,
  SwapOutlined,
  RightOutlined as CollapseRightOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import { reportAPI } from "../../utils/api";
import { TaskFile } from "../../utils/data";

const { Content, Sider } = Layout;
const { Title, Text } = Typography;

interface ReportEditorPageProps {
  taskId: string;
  projectId: string;
  projectName?: string;
  onBack: () => void;
  onPreview?: () => void;
  projectSidebarCollapsed?: boolean;
  onProjectSidebarCollapseChange?: (collapsed: boolean) => void;
}

const ReportEditorPage: React.FC<ReportEditorPageProps> = ({
  taskId,
  projectId,
  onBack,
  onPreview,
  projectSidebarCollapsed = false,
  onProjectSidebarCollapseChange,
}) => {
  const [selectedFile, setSelectedFile] = useState<TaskFile | null>(null);
  const [viewMode, setViewMode] = useState<'single' | 'compare'>('single');
  const [compareSelectedFiles, setCompareSelectedFiles] = useState<[TaskFile | null, TaskFile | null]>([null, null]);
  // 所有模式（单图 + 对比左 + 对比右）共享同一份 Blob LRU 缓存
  // 单图↔对比模式互切时可直接命中已加载的图片，无需重新下载
  const blobCacheRef = useRef<Map<string, File>>(new Map());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const editorContainerRef = useRef<HTMLDivElement>(null);
  const reportTitleRef = useRef<HTMLDivElement>(null);
  const [leftSidebarWidth, setLeftSidebarWidth] = useState(280);
  const [isLeftSidebarCollapsed, setIsLeftSidebarCollapsed] = useState(false);

  const { data: reportResp } = useRequest(() => reportAPI.getReportDetail(taskId));
  const report = reportResp?.Data;

  useEffect(() => {
    if (reportTitleRef.current) {
      const measuredWidth = reportTitleRef.current.offsetWidth + 40;
      setLeftSidebarWidth(Math.max(measuredWidth, 240));
    }
  }, [report?.ReportName, taskId, reportResp]);

  const {
    data: filesResp,
    loading: filesLoading,
    refresh: refreshFiles,
  } = useRequest(() => reportAPI.getReportFiles(taskId));
  const files: TaskFile[] = filesResp?.Data || [];

  const confirmedCount = files.filter(f => f.ReviewStatus === "CONFIRMED").length;
  const unconfirmedCount = files.length - confirmedCount;
  const progressPercent = files.length > 0 ? Math.round((confirmedCount / files.length) * 100) : 0;

  const paginatedFiles = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return files.slice(start, start + pageSize);
  }, [files, currentPage, pageSize]);

  useEffect(() => {
    if (files.length > 0 && !selectedFile) {
      setSelectedFile(files[0]);
    }
  }, [files]);

  useEffect(() => {
    setCompareSelectedFiles(([left, right]) => {
      const nextLeft = left && files.some(f => f.TaskFileId === left.TaskFileId) ? left : null;
      const nextRight = right && files.some(f => f.TaskFileId === right.TaskFileId) ? right : null;
      if (nextLeft === left && nextRight === right) return [left, right];
      return [nextLeft, nextRight];
    });
  }, [files]);

  const handleSelectAll = (checked: boolean) => {
    if (checked) setSelectedIds(new Set(files.map(f => f.TaskFileId)));
    else setSelectedIds(new Set());
  };

  const handleSelectOne = (id: string, checked: boolean) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const handleBatchConfirm = async () => {
    if (selectedIds.size === 0) { message.warning("请先选择要确认的文件"); return; }
    try {
      await reportAPI.batchConfirmFiles(Array.from(selectedIds));
      message.success(`成功批量确认 ${selectedIds.size} 个文件`);
      setSelectedIds(new Set());
      refreshFiles();
    } catch (err) {
      console.error(err);
    }
  };

  const toggleFullScreen = () => {
    if (!document.fullscreenElement) {
      editorContainerRef.current?.requestFullscreen().catch(err => {
        message.error(`全屏失败: ${err.message} (${err.name})`);
      });
    } else {
      document.exitFullscreen();
    }
  };

  const collapsedLeftSidebarWidth = 24;
  const actualLeftSidebarWidth = isLeftSidebarCollapsed ? collapsedLeftSidebarWidth : leftSidebarWidth;
  const areBothSidebarsCollapsed = isLeftSidebarCollapsed && projectSidebarCollapsed;

  const handleToggleBothSidebars = () => {
    const nextCollapsed = !areBothSidebarsCollapsed;
    setIsLeftSidebarCollapsed(nextCollapsed);
    onProjectSidebarCollapseChange?.(nextCollapsed);
  };

  return (
    <Layout style={{ height: '100%', overflow: 'hidden' }}>
      <Sider
        width={actualLeftSidebarWidth}
        theme="light"
        style={{
          borderRight: "1px solid #f0f0f0",
          overflow: 'hidden',
          transition: 'all 0.2s ease',
          position: 'relative',
          background: isLeftSidebarCollapsed ? '#fafafa' : '#fff',
          flex: `0 0 ${actualLeftSidebarWidth}px`,
          maxWidth: actualLeftSidebarWidth,
          minWidth: actualLeftSidebarWidth,
        }}
      >
        {isLeftSidebarCollapsed ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Tooltip title="展开左侧列表" placement="right" getPopupContainer={() => editorContainerRef.current || document.body}>
              <Button
                type="text" size="small" icon={<CollapseRightOutlined />}
                onClick={() => setIsLeftSidebarCollapsed(false)}
                style={{ width: 18, height: 72, padding: 0, borderRadius: 999, color: '#8c8c8c', background: 'transparent' }}
              />
            </Tooltip>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: leftSidebarWidth, overflow: 'hidden' }}>
            <div style={{ padding: "20px 16px", borderBottom: "1px solid #f0f0f0" }}>
              <Space direction="vertical" style={{ width: "100%" }} size={12}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <Button icon={<LeftOutlined />} onClick={onBack} type="text" style={{ padding: 0, height: 'auto', color: '#8c8c8c' }}>
                    返回列表
                  </Button>
                  <Space size={4}>
                    {onProjectSidebarCollapseChange && (
                      <Tooltip
                        title={projectSidebarCollapsed ? '展开项目列表' : '收起项目列表'}
                        placement="right"
                        getPopupContainer={() => editorContainerRef.current || document.body}
                      >
                        <Button type="text" size="small"
                          icon={<DoubleRightOutlined style={{ transform: projectSidebarCollapsed ? 'none' : 'rotate(180deg)' }} />}
                          onClick={() => onProjectSidebarCollapseChange(!projectSidebarCollapsed)}
                          style={{ color: '#8c8c8c', width: 24, minWidth: 24, height: 24, padding: 0, borderRadius: 12, flexShrink: 0 }}
                        />
                      </Tooltip>
                    )}
                    {onProjectSidebarCollapseChange && (
                      <Tooltip
                        title={areBothSidebarsCollapsed ? '展开项目列表和返回列表' : '同时折叠项目列表和返回列表'}
                        placement="right"
                        getPopupContainer={() => editorContainerRef.current || document.body}
                      >
                        <Button type="text" size="small" icon={<SwapOutlined />} onClick={handleToggleBothSidebars}
                          style={{ color: areBothSidebarsCollapsed ? '#1890ff' : '#8c8c8c', width: 24, minWidth: 24, height: 24, padding: 0, borderRadius: 12, flexShrink: 0 }}
                        />
                      </Tooltip>
                    )}
                    <Tooltip title="收起左侧列表" placement="right" getPopupContainer={() => editorContainerRef.current || document.body}>
                      <Button type="text" size="small" icon={<LeftOutlined />} onClick={() => setIsLeftSidebarCollapsed(true)}
                        style={{ color: '#8c8c8c', width: 24, minWidth: 24, height: 24, padding: 0, borderRadius: 12, flexShrink: 0 }}
                      />
                    </Tooltip>
                  </Space>
                </div>
                <Title level={4} style={{ margin: 0, fontSize: '18px', whiteSpace: 'nowrap', display: 'inline-block' }}>
                  <div ref={reportTitleRef}>
                    {report?.ReportName || `检测报告_${taskId.slice(-6)}`}
                  </div>
                </Title>
              </Space>

              <div style={{ marginTop: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: '12px', color: '#8c8c8c' }}>
                  <span>文件总数: {files.length}个</span>
                  <span>{progressPercent}%</span>
                </div>
                <Progress percent={progressPercent} size="small" showInfo={false} strokeColor="#52c41a" trailColor="#f0f0f0" />
                <div style={{ display: 'flex', marginTop: 16, background: '#f8f9fa', borderRadius: '4px', padding: '12px 0' }}>
                  <div style={{ textAlign: 'center', flex: 1 }}>
                    <div style={{ color: '#52c41a', fontSize: '20px', fontWeight: '600', lineHeight: 1.2 }}>{confirmedCount}</div>
                    <div style={{ fontSize: '12px', color: '#8c8c8c', marginTop: 4 }}>已确认</div>
                  </div>
                  <div style={{ borderLeft: '1px solid #e8e8e8', height: '24px', alignSelf: 'center' }} />
                  <div style={{ textAlign: 'center', flex: 1 }}>
                    <div style={{ color: '#faad14', fontSize: '20px', fontWeight: '600', lineHeight: 1.2 }}>{unconfirmedCount}</div>
                    <div style={{ fontSize: '12px', color: '#8c8c8c', marginTop: 4 }}>未确认</div>
                  </div>
                </div>
              </div>
            </div>

            <div style={{ padding: "8px 16px", display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f0f0f0' }}>
              <Checkbox
                checked={selectedIds.size === files.length && files.length > 0}
                indeterminate={selectedIds.size > 0 && selectedIds.size < files.length}
                onChange={(e) => handleSelectAll(e.target.checked)}
              >
                全选
              </Checkbox>
              {selectedIds.size > 0 && (
                <Button type="link" size="small" danger onClick={handleBatchConfirm}>
                  批量确认 ({selectedIds.size})
                </Button>
              )}
            </div>

            <div style={{ padding: '10px 16px', borderBottom: '1px solid #f0f0f0', background: '#fff' }}>
              <Space size={8} style={{ width: '100%', justifyContent: 'space-between' }}>
                <Text strong style={{ fontSize: 13 }}>
                  {viewMode === 'compare' ? '当前为对比模式' : '当前为单图模式'}
                </Text>
                <Space size={8}>
                  <span style={{ fontSize: 12, color: '#8c8c8c' }}>对比模式</span>
                  <Switch
                    checked={viewMode === 'compare'}
                    onChange={(checked) => {
                      setViewMode(checked ? 'compare' : 'single');
                      if (checked && selectedFile) {
                        setCompareSelectedFiles([selectedFile, null]);
                      }
                    }}
                    size="small"
                  />
                </Space>
              </Space>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
              <List
                loading={filesLoading}
                dataSource={paginatedFiles}
                renderItem={(file) => (
                  <List.Item
                    onClick={() => {
                      if (viewMode === 'single') {
                        setSelectedFile(file);
                      } else {
                        setCompareSelectedFiles(prev => {
                          if (!prev[0] || (prev[0] && prev[1])) return [file, null];
                          return [prev[0], file];
                        });
                      }
                    }}
                    style={{
                      cursor: "pointer",
                      padding: "10px 16px",
                      backgroundColor: (viewMode === "single"
                        ? selectedFile?.TaskFileId === file.TaskFileId
                        : compareSelectedFiles.some(f => f?.TaskFileId === file.TaskFileId))
                        ? "#e6f7ff" : "transparent",
                      borderLeft: (viewMode === "single"
                        ? selectedFile?.TaskFileId === file.TaskFileId
                        : compareSelectedFiles.some(f => f?.TaskFileId === file.TaskFileId))
                        ? "4px solid #1890ff" : "4px solid transparent",
                      transition: 'all 0.3s',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                      <Checkbox
                        checked={selectedIds.has(file.TaskFileId)}
                        onChange={(e) => handleSelectOne(file.TaskFileId, e.target.checked)}
                        onClick={(e) => e.stopPropagation()}
                        style={{ marginRight: 12 }}
                      />
                      <Space style={{ flex: 1 }}>
                        {file.ReviewStatus === "CONFIRMED" ? (
                          <CheckCircleOutlined style={{ color: "#52c41a" }} />
                        ) : (
                          <div style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid #faad14' }} />
                        )}
                        <Tooltip title={file.FileName} placement="topLeft" mouseEnterDelay={0.1}>
                          <Text ellipsis style={{
                            flex: 1,
                            color: (viewMode === "single"
                              ? selectedFile?.TaskFileId === file.TaskFileId
                              : compareSelectedFiles.some(f => f?.TaskFileId === file.TaskFileId))
                              ? "#1890ff" : "inherit",
                            minWidth: 0,
                          }}>
                            {file.FileName}
                          </Text>
                        </Tooltip>
                      </Space>
                    </div>
                  </List.Item>
                )}
              />
            </div>

            <div style={{ padding: '8px', borderTop: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              <Pagination
                simple
                current={currentPage}
                total={files.length}
                pageSize={pageSize}
                onChange={setCurrentPage}
                showSizeChanger={false}
                size="small"
                style={{ whiteSpace: 'nowrap' }}
              />
              <Select
                size="small"
                value={pageSize}
                onChange={(size) => { setPageSize(size); setCurrentPage(1); }}
                placement="topLeft"
                options={[
                  { label: '10条/页', value: 10 },
                  { label: '20条/页', value: 20 },
                  { label: '50条/页', value: 50 },
                ]}
              />
            </div>

            <div style={{ padding: '16px', borderTop: '1px solid #f0f0f0' }}>
              <Button
                type="primary" block size="large" icon={<FileTextOutlined />}
                style={{ height: '48px', borderRadius: '4px' }}
                onClick={() => onPreview && onPreview()}
              >
                预览报告
              </Button>
            </div>
          </div>
        )}
      </Sider>

      <Content
        ref={editorContainerRef}
        style={{ display: "flex", flexDirection: "column", background: '#f0f2f5', height: '100%', overflow: 'hidden' }}
      >
        {viewMode === 'single' ? (
          <ImageEditorViewer
            file={selectedFile}
            taskId={taskId}
            projectId={projectId}
            sharedBlobCacheRef={blobCacheRef}
            onFileSaved={refreshFiles}
          />
        ) : (
          <div style={{ display: 'flex', height: '100%', width: '100%' }}>
            <div style={{ flex: 1, borderRight: '2px solid #000', position: 'relative', overflow: 'hidden' }}>
              {compareSelectedFiles[0] ? (
                <ImageEditorViewer
                  file={compareSelectedFiles[0]}
                  taskId={taskId}
                  projectId={projectId}
                  initialReviewPanelCollapsed={true}
                  onToggleFullScreen={toggleFullScreen}
                  sharedBlobCacheRef={blobCacheRef}
                  onFileSaved={refreshFiles}
                />
              ) : (
                <div style={{ padding: '40px', textAlign: 'center' }}>请在左侧选择图片 1</div>
              )}
            </div>
            <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
              {compareSelectedFiles[1] ? (
                <ImageEditorViewer
                  file={compareSelectedFiles[1]}
                  taskId={taskId}
                  projectId={projectId}
                  initialReviewPanelCollapsed={true}
                  onToggleFullScreen={toggleFullScreen}
                  sharedBlobCacheRef={blobCacheRef}
                  onFileSaved={refreshFiles}
                />
              ) : (
                <div style={{ padding: '40px', textAlign: 'center' }}>请在左侧选择图片 2</div>
              )}
            </div>
          </div>
        )}
      </Content>
    </Layout>
  );
};

export default ReportEditorPage;
