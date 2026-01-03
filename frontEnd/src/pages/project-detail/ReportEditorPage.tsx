import React, { useState, useEffect, useMemo, useRef } from "react";
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
  Pagination,
  Slider, // 引入 Slider
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
  FileTextOutlined,
  QuestionCircleOutlined,
  AimOutlined,
  HighlightOutlined,
  ColumnWidthOutlined,
  InfoCircleOutlined,
  RollbackOutlined,
  SwapOutlined,
  FullscreenOutlined,
  FontSizeOutlined,
  ArrowRightOutlined,
  PlusOutlined,
  LinkOutlined,
  VerticalAlignBottomOutlined,
  VerticalAlignTopOutlined,
} from "@ant-design/icons";
import { useRequest } from "ahooks";
import { reportAPI, getUserId } from "../../utils/api";
import { TaskFile, Report } from "../../utils/data";
import GeometricMeasureTool from './tool/GeometricMeasureTool';
import { useWindowLevelTool, WindowLevelSVGFilter } from './tool/WindowLevelTool'; 
import Ruler from './tool/Ruler';

const { Content, Sider } = Layout;
const { Title, Text, Link } = Typography;

interface ReportEditorPageProps {
  taskId: string;
  projectId: string;
  projectName?: string;
  onBack: () => void;
  onPreview?: () => void;
}

const ReportEditorPage: React.FC<ReportEditorPageProps> = ({
  taskId,
  projectId,
  projectName,
  onBack,
  onPreview,
}) => {
  const [selectedFile, setSelectedFile] = useState<TaskFile | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;
  const [form] = Form.useForm();

  // 记录当前激活的工具 ('measure', 'pan' 等)
  const [activeTool, setActiveTool] = useState<string>('pan'); 
  
  // 图片变换状态
  const [scale, setScale] = useState(1); 
  const [rotation, setRotation] = useState(0); // 旋转
  const [flipH, setFlipH] = useState(1);       // 水平翻转 (1 or -1)
  const [flipV, setFlipV] = useState(1);       // 垂直翻转 (1 or -1)

  // 标尺相关状态
  const imageWrapperRef = useRef<HTMLDivElement>(null);
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 });
  const [imageOffset, setImageOffset] = useState({ x: 0, y: 0 }); //  图片偏移量
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 }); //  容器尺寸
  const [canvasContainer, setCanvasContainer] = useState<HTMLDivElement | null>(null); // 视口容器

  const [originalSize, setOriginalSize] = useState({ w: 0, h: 0 }); // 图片原始尺寸
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });       // 鼠标在原图上的坐标

  // 计算图片原始分辨率与显示分辨率的比例
  // 用于传给 Ruler 组件，确保标尺刻度对应真实像素
  const widthRatio = (originalSize.w > 0 && imgSize.w > 0) ? (originalSize.w / imgSize.w) : 1;
  const heightRatio = (originalSize.h > 0 && imgSize.h > 0) ? (originalSize.h / imgSize.h) : 1;


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

  // 计算图片位置偏移 (用于标尺)
  const updateImageOffset = () => {
    if (imageWrapperRef.current && canvasContainer) {
      const imgRect = imageWrapperRef.current.getBoundingClientRect();
      const containerRect = canvasContainer.getBoundingClientRect();
      
      setImageOffset({
        x: imgRect.left - containerRect.left,
        y: imgRect.top - containerRect.top
      });
      setContainerSize({
        w: containerRect.width,
        h: containerRect.height
      });
    }
  };

  // 监听变换以更新标尺
  useEffect(() => {
    updateImageOffset();
    window.addEventListener('resize', updateImageOffset);
    return () => window.removeEventListener('resize', updateImageOffset);
  }, [scale, rotation, flipH, flipV, imgSize, selectedFile]);

  //  鼠标移动追踪函数
  const handleMouseMoveTracker = (e: React.MouseEvent<HTMLDivElement>) => {
    // 确保有引用且图片已加载
    if (!imageWrapperRef.current || imgSize.w === 0 || originalSize.w === 0) return;
    
    // 获取图片容器的矩形（受 scale 影响）
    const rect = imageWrapperRef.current.getBoundingClientRect();
    
    // 计算相对于容器左上角的坐标 (除以 scale 还原为未缩放时的 CSS 像素)
    const rawX = (e.clientX - rect.left) / scale;
    const rawY = (e.clientY - rect.top) / scale;
    
    // 计算缩放比例 (原始分辨率 / 显示尺寸)
    const ratioX = originalSize.w / imgSize.w;
    const ratioY = originalSize.h / imgSize.h;
    
    // 映射到原始分辨率坐标
    const trueX = Math.floor(rawX * ratioX);
    const trueY = Math.floor(rawY * ratioY);
    
    // 限制坐标在图片范围内 (防止边缘溢出)
    const clampedX = Math.max(0, Math.min(originalSize.w, trueX));
    const clampedY = Math.max(0, Math.min(originalSize.h, trueY));
    setMousePos({ x: clampedX, y: clampedY });
  };

  // 鼠标滚轮事件处理函数
  const handleWheel = (e: React.WheelEvent) => {
    const step = 0.1;
    const delta = e.deltaY > 0 ? -step : step;
    let newScale = scale + delta;
    newScale = Math.max(0.1, Math.min(5, newScale));
    newScale = parseFloat(newScale.toFixed(1));
    setScale(newScale);
  };

  const confirmedCount = files.filter(f => f.ReviewStatus === "CONFIRMED").length;
  const unconfirmedCount = files.length - confirmedCount;
  const progressPercent = files.length > 0 ? Math.round((confirmedCount / files.length) * 100) : 0;

  // Window Level Tool Hook
  const { 
    windowParams, 
    selectionRect, 
    imgRef, 
    handlers, 
    resetWindow,
    windowWidth,
    windowLevel,
    setManualWindowLevel
  } = useWindowLevelTool({ activeTool, scale });

  // 鼠标样式逻辑
  const cursorStyle = activeTool === 'windowing' ? 'crosshair' : (activeTool === 'pan' ? 'grab' : 'default');

  // 分页后的文件列表
  const paginatedFiles = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return files.slice(start, start + pageSize);
  }, [files, currentPage]);

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
      // 切换图片时重置所有状态
      resetWindow();
      setScale(1);
      setRotation(0);
      setFlipH(1);
      setFlipV(1);
    }
  }, [selectedFile, form, resetWindow]);

  // 全选/反选
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(files.map(f => f.TaskFileId)));
    } else {
      setSelectedIds(new Set());
    }
  };

  // 单选
  const handleSelectOne = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) newSelected.add(id);
    else newSelected.delete(id);
    setSelectedIds(newSelected);
  };

  // 批量确认
  const handleBatchConfirm = async () => {
    if (selectedIds.size === 0) {
      message.warning("请先选择要确认的文件");
      return;
    }
    try {
      await reportAPI.batchConfirmFiles(Array.from(selectedIds));
      message.success(`成功批量确认 ${selectedIds.size} 个文件`);
      setSelectedIds(new Set());
      refreshFiles();
    } catch (err) {
      console.error(err);
    }
  };

  //负片
  const [isNegative, setIsNegative] = useState(false);

  // 保存并确认当前文件
  const handleSave = async () => {
    if (!selectedFile) return;
    try {
      const values = await form.validateFields();
      await reportAPI.reviewFile(selectedFile.TaskFileId, {
        ManualResult: selectedFile.VisionResult || "{}",
        PlateQuality: values.PlateQuality,
      });
      message.success("保存并确认成功");
      refreshFiles();
      
      const currentIndex = files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId);
      if (currentIndex < files.length - 1) {
        const nextFile = files[currentIndex + 1];
        setSelectedFile(nextFile);
        const nextPageIndex = Math.floor((currentIndex + 1) / pageSize) + 1;
        if (nextPageIndex !== currentPage) {
          setCurrentPage(nextPageIndex);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <Layout style={{ height: "100%", background: "#fff", margin: 0, padding: 0 }}>
      <WindowLevelSVGFilter id="wlFilter" slope={windowParams.slope} intercept={windowParams.intercept} />

      {/* 左侧文件列表 */}
      <Sider width={300} theme="light" style={{ borderRight: "1px solid #f0f0f0", display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: "20px 16px", borderBottom: "1px solid #f0f0f0" }}>
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            <Button 
              icon={<LeftOutlined />} 
              onClick={onBack} 
              type="text" 
              style={{ padding: 0, height: 'auto', color: '#8c8c8c' }}
            >
              返回列表
            </Button>
            <Title level={4} style={{ margin: 0, fontSize: '18px' }}>
              {report?.ReportName || `检测报告_${taskId.slice(-6)}`}
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
        
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <List
            loading={filesLoading}
            dataSource={paginatedFiles}
            renderItem={(file) => (
              <List.Item
                onClick={() => setSelectedFile(file)}
                style={{
                  cursor: "pointer",
                  padding: "10px 16px",
                  backgroundColor: selectedFile?.TaskFileId === file.TaskFileId ? "#e6f7ff" : "transparent",
                  borderLeft: selectedFile?.TaskFileId === file.TaskFileId ? "4px solid #1890ff" : "4px solid transparent",
                  transition: 'all 0.3s'
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
                    <Text ellipsis style={{ width: 160, color: selectedFile?.TaskFileId === file.TaskFileId ? "#1890ff" : "inherit" }}>
                      {file.FileName}
                    </Text>
                  </Space>
                </div>
              </List.Item>
            )}
          />
        </div>
        
        <div style={{ padding: '8px', textAlign: 'center', borderTop: '1px solid #f0f0f0' }}>
          <Pagination
            simple
            current={currentPage}
            total={files.length}
            pageSize={pageSize}
            onChange={setCurrentPage}
            size="small"
          />
        </div>

        <div style={{ padding: '16px', borderTop: '1px solid #f0f0f0' }}>
          <Button 
            type="primary" 
            block 
            size="large"
            icon={<FileTextOutlined />} 
            style={{ height: '48px', borderRadius: '4px' }}
            onClick={onPreview}
          >
            预览报告
          </Button>
        </div>
      </Sider>
      
      {/* 中间编辑区 */}
      <Content style={{ display: "flex", flexDirection: "column", background: '#f0f2f5' }}>
        {/* 顶部专业工具栏 */}
        <div style={{ 
          height: 48, 
          background: '#1f1f1f', 
          color: '#fff', 
          display: 'flex', 
          alignItems: 'center', 
          padding: '0 8px', 
          justifyContent: 'space-between',
          borderBottom: '1px solid #303030'
        }}>
          <Space size={0}>
            <Tooltip title="选择 (V)"><Button type="text" ghost icon={<AimOutlined />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            <Tooltip title="缺陷标记 (D)"><Button type="text" ghost icon={<BorderOutlined />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            <Tooltip title="文本标注 (T)"><Button type="text" ghost icon={<FontSizeOutlined />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            <Tooltip title="箭头 (A)"><Button type="text" ghost icon={<ArrowRightOutlined style={{ transform: 'rotate(-45deg)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            <Tooltip title="多边形 (P)"><Button type="text" ghost icon={<HighlightOutlined />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            
            <Tooltip title="几何测量 (M)">
              <Button 
                type={activeTool === 'measure' ? 'primary' : 'text'} 
                ghost={activeTool !== 'measure'} 
                onClick={() => setActiveTool(activeTool === 'measure' ? 'pan' : 'measure')} 
                icon={<img src="/geometric_measurement.svg" alt="measurement" style={{ width: 20, height: 20 }} />} 
                style={{ color: '#fff', width: 36, height: 36, padding: 0, background: activeTool === 'measure' ? '#1890ff' : 'transparent' }} 
              />
            </Tooltip>

            <Tooltip title="负片">
              <Button
                type={isNegative ? 'primary' : 'text'} 
                ghost={!isNegative} 
                onClick={() => setIsNegative(!isNegative)} 
                icon={<img src="/negative.svg" alt="negative" style={{ width: 32, height: 32 }} />}  
                style={{ color: '#fff', width: 36, height: 36, padding: 0, background: isNegative ? '#1890ff' : 'transparent' }} 
              />
            </Tooltip>
            
            <Tooltip title="窗宽窗位 (ROI自适应)">
              <Button 
                type={activeTool === 'windowing' ? 'primary' : 'text'} 
                ghost={activeTool !== 'windowing'}
                icon={<img src="/windowing.svg" style={{width:20, height:20}} />} 
                onClick={() => setActiveTool(activeTool === 'windowing' ? 'pan' : 'windowing')}
                style={{ color: '#fff', width: 36, height: 36, padding: 0, background: activeTool === 'windowing' ? '#1890ff' : 'transparent' }} 
              />
            </Tooltip>

             <Tooltip title="重置窗宽窗位">
                <Button type="text" ghost icon={<RollbackOutlined />} onClick={resetWindow} />
            </Tooltip>

            {/*  旋转和翻转按钮 */}
            <Tooltip title="左旋转90度">
              <Button type="text" ghost icon={<img src="/rotate_left.svg" alt="rotate_left" style={{ width: 32, height: 32 }} />} style={{ color: '#fff', width: 36, height: 36, padding: 0 }} onClick={() => setRotation(r => r - 90)} />
            </Tooltip>
            <Tooltip title="右旋转90度">
              <Button type="text" ghost icon={<img src="/rotate_right.svg" alt="rotate_right" style={{ width: 32, height: 32 }} />} style={{ color: '#0c0b0bff', width: 36, height: 36, padding: 0 }} onClick={() => setRotation(r => r + 90)} />
            </Tooltip>
            <Tooltip title="旋转180度">
              <Button type="text" ghost icon={<img src="/rotate_180_degrees.svg" alt="rotate_180_degrees" style={{ width: 32, height: 32 }} />} style={{ color: '#fff', width: 36, height: 36, padding: 0 }} onClick={() => setRotation(r => r + 180)} />
            </Tooltip>
            
            <Tooltip title="垂直翻转">
               <Button type="text" ghost icon={<img src="/vertical_flip.svg" alt="vertical_flip" style={{ width: 32, height: 32 }} />} style={{ color: '#fff', width: 36, height: 36, padding: 0 }} onClick={() => setFlipV(v => v * -1)} />
            </Tooltip>
            <Tooltip title="水平翻转">
               <Button type="text" ghost icon={<img src="/horizontal_flip.svg" alt="horizontal_flip" style={{ width: 32, height: 32 }} />} style={{ color: '#fff', width: 36, height: 36, padding: 0 }} onClick={() => setFlipH(h => h * -1)} />
            </Tooltip>

            <Tooltip title="还原">
               <Button 
                  type="text" ghost 
                  icon={<img src="/reset.svg" alt="reset" style={{ width: 32, height: 32 }} />} 
                  style={{ color: '#fff', width: 36, height: 36, padding: 0 }} 
                  onClick={() => { setScale(1); setRotation(0); setFlipH(1); setFlipV(1); }} 
                />
            </Tooltip>

            <Tooltip title="平移 (Space)"><Button type="text" ghost icon={<DragOutlined />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            <Tooltip title="新增 (N)"><Button type="text" ghost icon={<PlusOutlined />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            
            <Divider type="vertical" style={{ background: '#434343', margin: '0 8px', height: 20 }} />
            
            <Button type="text" ghost style={{ color: '#fff', fontSize: '12px', height: 28, padding: '0 8px', background: '#303030', borderRadius: '2px', marginRight: 8 }}>正片</Button>
            
            <Tooltip title="向左旋转"><Button type="text" ghost icon={<RotateLeftOutlined />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            <Tooltip title="向右旋转"><Button type="text" ghost icon={<RotateRightOutlined />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            <Tooltip title="重置视图"><Button type="text" ghost icon={<FullscreenOutlined />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            <Tooltip title="水平翻转"><Button type="text" ghost icon={<SwapOutlined />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
            <Tooltip title="垂直翻转"><Button type="text" ghost icon={<SwapOutlined style={{ transform: 'rotate(90deg)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0 }} /></Tooltip>
          </Space>
          
          <Space size={8}>
            <Button 
              type="text" 
              ghost 
              icon={<ColumnWidthOutlined />} 
              style={{ 
                color: '#fff', fontSize: '12px', height: 28, padding: '0 12px', background: '#303030', borderRadius: '4px', display: 'flex', alignItems: 'center'
              }}
            >
              尺寸定标
            </Button>
            
            <div style={{ background: '#262626', height: 28, borderRadius: '4px', display: 'flex', alignItems: 'center', padding: '0 8px', fontSize: '11px', color: '#8c8c8c' }}>
              <LinkOutlined style={{ transform: 'rotate(-45deg)', marginRight: 4 }} />
              <div style={{ textAlign: 'center', lineHeight: 1.1 }}>
                <div>1px</div>
                <div style={{ borderTop: '1px solid #595959', marginTop: 1 }}>5mm</div>
              </div>
            </div>

            <div style={{ background: '#262626', height: 28, borderRadius: '4px', display: 'flex', alignItems: 'center', padding: '0 8px', fontSize: '11px', color: '#8c8c8c' }}>
              <AimOutlined style={{ color: '#1890ff', marginRight: 4 }} />
              <div style={{ textAlign: 'left', lineHeight: 1.1 }}>
                <div>点:</div>
                <div style={{ color: '#fff' }}>(0, 0)</div>
              </div>
            </div>

            <div style={{ background: '#262626', height: 28, borderRadius: '4px', display: 'flex', alignItems: 'center', padding: '0 8px', fontSize: '11px', color: '#8c8c8c' }}>
              <div style={{ textAlign: 'left', lineHeight: 1.1 }}>
                <div>400 |</div>
                <div>窗位: 128</div>
              </div>
            </div>
          </Space>
        </div>

        {/* [修改] 图片容器：改为 Grid 布局以放置标尺 */}
        <div style={{ 
            flex: 1, 
            position: 'relative', 
            overflow: 'hidden', 
            background: '#262626', // 深色背景匹配标尺
            display: 'grid', 
            gridTemplateColumns: '20px 1fr', 
            gridTemplateRows: '20px 1fr',
          }}
        >
          {/* 1. 左上角单位块 */}
          <div style={{ background: '#1f1f1f', color: '#8c8c8c', fontSize: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderBottom: '1px solid #303030', borderRight: '1px solid #303030', zIndex: 20 }}>
             PX
          </div>

          {/* 2. 顶部横向标尺 */}
          <div style={{ overflow: 'hidden', position: 'relative', zIndex: 10 }}>
             <Ruler type="horizontal" scale={scale} offset={imageOffset.x} length={containerSize.w} ratio={widthRatio} />
          </div>

          {/* 3. 左侧纵向标尺 */}
          <div style={{ overflow: 'hidden', position: 'relative', zIndex: 10 }}>
             <Ruler type="vertical" scale={scale} offset={imageOffset.y} length={containerSize.h} ratio={heightRatio}/>
          </div>

          {/* 4. 图片视口 (Bottom-Right Cell) */}
          <div 
             ref={setCanvasContainer}
             style={{ position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            {selectedFile ? (
              <div 
                ref={imageWrapperRef} 
                onWheel={handleWheel}
                {...handlers}
                onMouseMove={(e) => {
                    handlers.onMouseMove && handlers.onMouseMove(e); // 保持原有工具逻辑
                    handleMouseMoveTracker(e); // 新增坐标追踪
                }}
                  
                style={{ 
                  position: "relative", 
                  display: 'inline-block',
                  transform: `scale(${scale * flipH}, ${scale * flipV}) rotate(${rotation}deg)`,
                  transformOrigin: 'center center',
                  transition: 'none', // 移除过渡以保证标尺实时对齐
                  cursor: cursorStyle
                }}
                onTransitionEnd={updateImageOffset}
              >
                <img 
                  ref={imgRef}
                  src={`/api/v1/files/preview?FileId=${selectedFile.FileId}&ProjectId=${projectId}&UserId=${getUserId()}`} 
                  alt="preview" 
                  draggable={false} 
                  crossOrigin="anonymous" 
                  onLoad={(e) => {
                    setImgSize({ w: e.currentTarget.clientWidth, h: e.currentTarget.clientHeight });
                    setOriginalSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight });
                    setTimeout(updateImageOffset, 50);
                  }}
                  style={{ 
                    maxHeight: "calc(100vh - 280px)", 
                    maxWidth: "100%", 
                    boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
                    display: 'block',
                    userSelect: activeTool === 'measure' ? 'none' : 'auto',
                    filter: `${isNegative ? 'invert(100%)' : ''} url(#wlFilter)`
                  }} 
                />

                {selectionRect && (
                   <div style={{
                     position: 'absolute',
                     border: '2px dashed #ff4d4f',
                     backgroundColor: 'rgba(255, 77, 79, 0.2)',
                     left: selectionRect.left,
                     top: selectionRect.top,
                     width: selectionRect.width,
                     height: selectionRect.height,
                     pointerEvents: 'none',
                     zIndex: 10
                   }} />
                 )}

                <GeometricMeasureTool
                  visible={activeTool === 'measure'} 
                  imageUrl={`/api/v1/files/preview?FileId=${selectedFile.FileId}&ProjectId=${projectId}&UserId=${getUserId()}`}
                  width={imgSize.w}
                  height={imgSize.h}
                  pixelRatio={0.26}
                  scale={scale} // 注意：这里可能需要传递 flip 状态给测量工具，取决于测量工具内部实现
                  container={canvasContainer} 
                />
              </div>
            ) : (
              <Empty description="请从左侧选择图片开始审核" />
            )}
            
            {/* 窗宽窗位 Slider 控制条 */}
            {selectedFile && (
              <div style={{ 
                position: 'absolute', bottom: 0, left: 0, right: 0,
                background: 'rgba(38, 38, 38, 0.85)', padding: '4px 24px', 
                display: 'flex', alignItems: 'center', gap: '32px',
                borderTop: '1px solid #434343', height: '40px', zIndex: 100 
              }}>
                <div style={{ display: 'flex', alignItems: 'center', flex: 1, gap: '12px' }}>
                  <span style={{ color: '#fff', fontSize: '12px', whiteSpace: 'nowrap', minWidth: '60px' }}>窗宽: {windowWidth}</span>
                  <Slider 
                    min={1} max={512} value={windowWidth}
                    onChange={(val) => setManualWindowLevel(val, windowLevel)}
                    style={{ flex: 1, margin: 0 }}
                    trackStyle={{ backgroundColor: '#1890ff' }} handleStyle={{ borderColor: '#1890ff' }}
                  />
                </div>
                <div style={{ width: 1, height: 16, background: '#595959' }}></div>
                <div style={{ display: 'flex', alignItems: 'center', flex: 1, gap: '12px' }}>
                  <span style={{ color: '#fff', fontSize: '12px', whiteSpace: 'nowrap', minWidth: '60px' }}>窗位: {windowLevel}</span>
                  <Slider 
                    min={0} max={255} value={windowLevel}
                    onChange={(val) => setManualWindowLevel(windowWidth, val)}
                    style={{ flex: 1, margin: 0 }}
                    trackStyle={{ backgroundColor: '#1890ff' }} handleStyle={{ borderColor: '#1890ff' }}
                  />
                </div>
                <div style={{ color: '#8c8c8c', fontSize: '12px', marginLeft: '12px' }}>缩放: {Math.round(scale * 100)}%</div>
              </div>
            )}

            {/* 底部悬浮操作栏 */}
            {selectedFile && (
              <div style={{ 
                position: 'absolute', bottom: 50, left: '50%', transform: 'translateX(-50%)', 
                background: '#fff', padding: '8px 24px', borderRadius: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                display: 'flex', alignItems: 'center', gap: '24px', border: '1px solid #e8e8e8', zIndex: 90
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Button type="text" icon={<LeftOutlined />} onClick={() => {
                      const idx = files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId);
                      if (idx > 0) setSelectedFile(files[idx - 1]);
                    }} disabled={files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId) === 0} style={{ color: '#8c8c8c' }}>上一个</Button>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', padding: '0 12px', whiteSpace: 'nowrap', minWidth: '60px', justifyContent: 'center' }}>
                    <Text strong style={{ fontSize: '16px' }}>{files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId) + 1}</Text>
                    <Text type="secondary" style={{ fontSize: '12px', margin: '0 2px' }}>/</Text>
                    <Text type="secondary" style={{ fontSize: '12px' }}>{files.length}</Text>
                  </div>
                  <Button type="text" onClick={() => {
                      const idx = files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId);
                      if (idx < files.length - 1) setSelectedFile(files[idx + 1]);
                    }} disabled={files.findIndex(f => f.TaskFileId === selectedFile.TaskFileId) === files.length - 1} style={{ color: '#1890ff' }}>下一个 <RightOutlined /></Button>
                </div>
                <Divider type="vertical" style={{ height: '24px' }} />
                <Button type="primary" onClick={handleSave} style={{ borderRadius: '4px', height: '36px', padding: '0 20px', background: '#1890ff' }} icon={<SaveOutlined />}>保存并确认</Button>
              </div>
            )}
          </div>
        </div>
        
       {/* 底部状态条 */}
        <div style={{ height: 28, background: '#f8f9fa', borderTop: '1px solid #e9ecef', display: 'flex', alignItems: 'center', padding: '0 16px', fontSize: '11px', color: '#6c757d' }}>
          {/* 显示图像尺寸和实时鼠标坐标 */}
          图像尺寸：{originalSize.w}*{originalSize.h}，鼠标位置：{mousePos.x}*{mousePos.y}
        </div>
      </Content>

      {/* 右侧审核信息 */}
      <Sider width={300} theme="dark" style={{ borderLeft: "1px solid #303030", display: 'flex', flexDirection: 'column', background: '#1f1f1f' }}>
          {/* ... 右侧内容保持不变 ... */}
          <div style={{ flex: 1, padding: '40px 16px 20px 16px', overflowY: 'auto' }}>
          <Space direction="vertical" style={{ width: '100%' }} size={32}>
            <div>
            <Title level={5} style={{ marginBottom: 16, fontSize: '14px', color: '#fff', fontWeight: 'normal' }}>缺陷信息</Title>
              <div style={{ minHeight: 120 }}>
            <List
                  size="small"
                  dataSource={JSON.parse(selectedFile?.VisionResult || '{"results":[]}').results}
                  renderItem={(item: any, idx: number) => (
                    <div key={idx} style={{ marginBottom: 16, borderBottom: '1px solid #303030', paddingBottom: 12 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <Tag color={isSevere(item.strName) ? "red" : "orange"} style={{ borderRadius: '2px', border: 'none', padding: '0 8px' }}>{item.strName}</Tag>
                        <Text style={{ fontSize: '12px', color: '#8c8c8c' }}>{(item.score * 100).toFixed(1)}%</Text>
                      </div>
                      <div style={{ display: 'flex', gap: 12, color: '#595959', fontSize: '11px' }}>
                        <span>位置: (120, 340)</span>
                        <span>尺寸: 15x12 px</span>
                      </div>
                    </div>
                  )}
                  locale={{ emptyText: (
                    <div style={{ color: '#595959', fontSize: '12px', textAlign: 'left', padding: '0' }}>
                      <div style={{ marginBottom: 8 }}>尚未标记缺陷</div>
                      <div style={{ lineHeight: '1.6' }}>选择“缺陷标记”工具，在图像上拖拽标记缺陷位置</div>
                    </div>
                  ) }}
                />
              </div>
            </div>

            <div>
              <Title level={5} style={{ marginBottom: 16, fontSize: '14px', color: '#fff', fontWeight: 'normal' }}>底片质量</Title>
              <Form form={form} layout="vertical">
                <Form.Item name="PlateQuality" style={{ marginBottom: 0 }}>
                  <Select 
                    variant="borderless" 
                    style={{ width: '100%', background: '#262626', borderRadius: '4px', color: '#fff' }} 
                    dropdownStyle={{ background: '#262626' }}
                    placeholder="请选择评级"
                  >
                    <Select.Option value="一级"><span style={{ color: '#fff' }}>I 级 (优)</span></Select.Option>
                    <Select.Option value="二级"><span style={{ color: '#fff' }}>II 级 (良)</span></Select.Option>
                    <Select.Option value="三级"><span style={{ color: '#fff' }}>III 级 (中)</span></Select.Option>
                    <Select.Option value="四级"><span style={{ color: '#fff' }}>IV 级 (差)</span></Select.Option>
                  </Select>
                </Form.Item>
              </Form>
            </div>

            <div>
              <Title level={5} style={{ marginBottom: 16, fontSize: '14px', color: '#fff', fontWeight: 'normal' }}>快捷键</Title>
              <div style={{ fontSize: '12px', color: '#8c8c8c', lineHeight: '28px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>滚轮:</span>
                  <span style={{ color: '#fff' }}>缩放图像</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>空格+拖拽:</span>
                  <span style={{ color: '#fff' }}>平移视图</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Ctrl+Z:</span>
                  <span style={{ color: '#fff' }}>撤销操作</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>R:</span>
                  <span style={{ color: '#fff' }}>重置视图</span>
                </div>
              </div>
            </div>
          </Space>
        </div>

        <div style={{ background: '#141414', padding: '24px 16px', fontSize: '12px', color: '#8c8c8c', borderTop: '1px solid #303030' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <span>窗宽: {windowWidth}</span>
            <span>窗位: {windowLevel}</span>
          </div>
          <div style={{ marginBottom: 16 }}>当前坐标: (120, 340)</div>
          <div style={{ borderTop: '1px solid #303030', paddingTop: 16, color: '#8c8c8c', display: 'flex', alignItems: 'center', gap: '8px' }}>
            底片评分系统 | 当前工具: 平移
            </div>
          </div>
      </Sider>
    </Layout>
  );
};

// 辅助函数判断是否为严重缺陷
const isSevere = (type: string) => {
  const severeKeywords = ['裂纹', '未熔合', '未焊透', 'crack', 'unfused', 'incomplete'];
  return severeKeywords.some(k => type.toLowerCase().includes(k));
};

export default ReportEditorPage;