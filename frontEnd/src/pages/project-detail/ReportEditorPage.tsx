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
  Slider,
  Modal,
  InputNumber,
  Input,
  Collapse,
  Popconfirm,
  Alert,
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
  DeleteOutlined,
  DownOutlined,
  UpOutlined,
  RightOutlined as CollapseRightOutlined, // 为了区分普通向右箭头
} from "@ant-design/icons";
import { useRequest, useDebounceFn } from "ahooks";
import { reportAPI, defectTypeAPI, defectRecordAPI, getUserId } from "../../utils/api";
import { TaskFile, Report, DefectType, DefectRecord } from "../../utils/data";
import GeometricMeasureTool from './tool/GeometricMeasureTool';
import { useWindowLevelTool } from './tool/WindowLevelTool';
import Ruler from './tool/Ruler';
import DefectMarking, { DrawingType } from './tool/DefectMarking';

const { Content, Sider } = Layout;
const { Title, Text, Link } = Typography;
const { Option } = Select;

// --- 1. 缺陷类型默认数据 (后端加载失败时的备用) ---
const DEFAULT_DEFECT_TYPES = [
  { Code: 'crack', Name: '裂纹(A)', Color: '#ff4d4f', SortOrder: 1, Enabled: true },
  { Code: 'lack_fusion', Name: '未熔合(B)', Color: '#eb2f96', SortOrder: 2, Enabled: true },
  { Code: 'incomplete_penetration', Name: '未焊透(C)', Color: '#a0522d', SortOrder: 3, Enabled: true },
  { Code: 'linear_defect', Name: '条形缺陷(D)', Color: '#faad14', SortOrder: 4, Enabled: true },
  { Code: 'round_defect', Name: '圆形缺陷(E)', Color: '#722ed1', SortOrder: 5, Enabled: true },
  { Code: 'undercut', Name: '咬边(F)', Color: '#13c2c2', SortOrder: 6, Enabled: true },
  { Code: 'concave', Name: '内凹(G)', Color: '#1890ff', SortOrder: 7, Enabled: true },
  { Code: 'other', Name: '其他(H)', Color: '#52c41a', SortOrder: 8, Enabled: true },
];

interface ReportEditorPageProps {
  taskId: string;
  projectId: string;
  projectName?: string;
  onBack: () => void;
  onPreview?: () => void;
}

// 扩展保存的图形接口，增加 label, color 以及新的业务字段
interface DefectBase {
  label: string;
  color: string;
  // 新增业务字段
  position?: string; // 缺陷位置
  size?: string;     // 缺陷尺寸
  quality?: string;  // 质量等级
  remark?: string;   // 备注
}

interface SavedRect extends DefectBase { x: number; y: number; w: number; h: number; }
interface SavedCircle extends DefectBase { x: number; y: number; r: number; }
interface SavedPolygon extends DefectBase { points: { x: number, y: number }[]; }

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

  // 底片信息表单
  const [filmInfoForm] = Form.useForm();

  // 记录当前激活的工具
  const [activeTool, setActiveTool] = useState<string>('pan');

  // 记录缺陷标注的具体工具类型
  const [drawingType, setDrawingType] = useState<DrawingType>('rect');

  // 图片变换状态
  const [scale, setScale] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [flipH, setFlipH] = useState(1);
  const [flipV, setFlipV] = useState(1);
  // 图片平移位置
  const [position, setPosition] = useState({ x: 0, y: 0 });

  // 平移交互状态
  const [isSpacePressed, setIsSpacePressed] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  // 标尺相关状态
  const imageWrapperRef = useRef<HTMLDivElement>(null);
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 });
  const [originalSize, setOriginalSize] = useState({ w: 0, h: 0 }); // 原始尺寸
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });       // 鼠标坐标
  const [imageOffset, setImageOffset] = useState({ x: 0, y: 0 });
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 });
  const [canvasContainer, setCanvasContainer] = useState<HTMLDivElement | null>(null);

  //  坐标原点状态管理
  const [originPoint, setOriginPoint] = useState<{ x: number, y: number } | null>(null);
  const [isSettingOrigin, setIsSettingOrigin] = useState(false);
  const [tempOrigin, setTempOrigin] = useState<{ x: number, y: number } | null>(null);

  // 标定相关状态
  const [pixelRatio, setPixelRatio] = useState<number>(5);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibrateLine, setCalibrateLine] = useState<{ x1: number, y1: number, x2: number, y2: number } | null>(null);
  const [calibrateModalVisible, setCalibrateModalVisible] = useState(false);
  const [measuredPixelDistance, setMeasuredPixelDistance] = useState(0);
  const [actualLength, setActualLength] = useState<number | null>(null);

  // --- 缺陷绘制相关状态 ---

  // 通用绘制状态
  const [isDrawingDefect, setIsDrawingDefect] = useState(false);
  const [defectStartPoint, setDefectStartPoint] = useState<{ x: number, y: number } | null>(null);

  // 1. 矩形相关
  const [currentDefectRect, setCurrentDefectRect] = useState<{ x: number, y: number, w: number, h: number } | null>(null);
  const [defectRects, setDefectRects] = useState<SavedRect[]>([]);

  // 2. 多边形相关
  const [currentPolygonPoints, setCurrentPolygonPoints] = useState<{ x: number, y: number }[]>([]);
  const [defectPolygons, setDefectPolygons] = useState<SavedPolygon[]>([]);
  const [cursorInImage, setCursorInImage] = useState<{ x: number, y: number } | null>(null);

  // 3. 圆形相关
  const [currentDefectCircle, setCurrentDefectCircle] = useState<{ x: number, y: number, r: number } | null>(null);
  const [defectCircles, setDefectCircles] = useState<SavedCircle[]>([]);

  // --- 2. 新增：缺陷类型选择弹窗状态 ---
  const [labelModalVisible, setLabelModalVisible] = useState(false);
  const [selectedLabelCode, setSelectedLabelCode] = useState<string | null>(null);

  // 暂存刚画完但未分类的形状数据
  const [pendingShape, setPendingShape] = useState<any>(null);
  const [pendingShapeType, setPendingShapeType] = useState<DrawingType>('rect');

  // --- 新增：折叠状态 ---
  const [showDefectList, setShowDefectList] = useState(true);
  const [showFilmInfo, setShowFilmInfo] = useState(true); // 底片信息折叠状态

  // --- 新增：每个缺陷项的展开状态 ---
  const [expandedDefects, setExpandedDefects] = useState<Set<string>>(new Set());

  // --- 标记是否为初始加载（防止自动保存时触发） ---
  const isInitialLoadRef = useRef(true);

  // 1. 获取报告详情
  const { data: reportResp } = useRequest(() => reportAPI.getReportDetail(taskId));
  const report = reportResp?.Data;

  // 2. 获取缺陷类型列表
  const { data: defectTypesResp, error: defectTypesError } = useRequest(() => defectTypeAPI.getDefectTypes());
  const isDefectTypesFromBackend = !defectTypesError && defectTypesResp?.Data != null;

  // 使用 useMemo 缓存 DEFECT_TYPES，避免每次渲染都创建新数组导致 useEffect 重复执行
  const DEFECT_TYPES = useMemo(() => {
    return (defectTypesResp?.Data || DEFAULT_DEFECT_TYPES).map((dt: any) => ({
      code: dt.Code,
      name: dt.Name,
      color: dt.Color,
    }));
  }, [defectTypesResp?.Data]);

  // 3. 获取文件列表
  const {
    data: filesResp,
    loading: filesLoading,
    refresh: refreshFiles,
  } = useRequest(() => reportAPI.getReportFiles(taskId));
  const files = filesResp?.Data || [];

  const previewUrl = selectedFile
    ? `/api/v1/files/preview?FileId=${selectedFile.FileId}&ProjectId=${projectId}&UserId=${getUserId()}`
    : '';

  // 计算图片位置偏移 (用于标尺)
  const updateImageOffset = (_e?: any) => {
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

  useEffect(() => {
    if (!imageWrapperRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (let entry of entries) {
        setImgSize({ w: entry.contentRect.width, h: entry.contentRect.height });
      }
      updateImageOffset();
    });
    observer.observe(imageWrapperRef.current);
    return () => observer.disconnect();
  }, [imageWrapperRef.current]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat) {
        e.preventDefault();
        setIsSpacePressed(true);
      }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        setIsSpacePressed(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  useEffect(() => {
    updateImageOffset();
    window.addEventListener('resize', updateImageOffset);
    return () => window.removeEventListener('resize', updateImageOffset);
  }, [scale, rotation, flipH, flipV, imgSize, selectedFile, position]);

  useEffect(() => {
    if (activeTool !== 'setOrigin') {
      setIsSettingOrigin(false);
      setTempOrigin(null);
    }
    if (activeTool !== 'calibrate') {
      setIsCalibrating(false);
      setCalibrateLine(null);
    }
    if (activeTool !== 'defect') {
      setIsDrawingDefect(false);
      setCurrentDefectRect(null);
      setCurrentPolygonPoints([]);
      setCurrentDefectCircle(null);
      setCursorInImage(null);
    }
  }, [activeTool]);

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

  const [imageFile, setImageFile] = useState<File | undefined>(undefined);

  const {
    selectionRect,
    canvasRef,
    handlers,
    resetWindow,
    windowWidth,
    windowLevel,
    setManualWindowLevel,
  } = useWindowLevelTool({
    activeTool,
    scale,
    imageFile: imageFile
  });

  useEffect(() => {
    if (!selectedFile || !previewUrl) {
      setImageFile(undefined);
      return;
    }
    fetch(previewUrl)
      .then(res => res.blob())
      .then(blob => {
        const file = new File([blob], selectedFile.FileName || 'image.png', { type: blob.type || 'image/png' });
        setImageFile(file);
      })
      .catch(err => {
        console.error('Failed to load image:', err);
        message.error('图像加载失败');
      });
  }, [selectedFile, previewUrl]);

  useEffect(() => {
    if (canvasRef.current) {
      const canvas = canvasRef.current;
      if (canvas.width > 0 && canvas.height > 0) {
        setOriginalSize({ w: canvas.width, h: canvas.height });
      }
    }
  }, [canvasRef.current?.width, canvasRef.current?.height, imageFile]);

  let cursorStyle = 'default';
  if (isPanning) {
    cursorStyle = 'grabbing';
  } else if (isSpacePressed || activeTool === 'pan') {
    cursorStyle = 'grab';
  } else if (activeTool === 'windowing') {
    cursorStyle = 'crosshair';
  } else if (activeTool === 'measure' || activeTool === 'calibrate') {
    cursorStyle = 'crosshair';
  } else if (activeTool === 'setOrigin') {
    cursorStyle = 'crosshair';
  } else if (activeTool === 'defect') {
    cursorStyle = 'crosshair';
  }

  const handleMouseMoveTracker = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!imageWrapperRef.current || imgSize.w === 0 || originalSize.w === 0) return;
    const rect = imageWrapperRef.current.getBoundingClientRect();
    const rawX = (e.clientX - rect.left) / scale;
    const rawY = (e.clientY - rect.top) / scale;
    const ratioX = originalSize.w / imgSize.w;
    const ratioY = originalSize.h / imgSize.h;
    const trueX = Math.floor(rawX * ratioX);
    const trueY = Math.floor(rawY * ratioY);
    const clampedX = Math.max(0, Math.min(originalSize.w, trueX));
    const clampedY = Math.max(0, Math.min(originalSize.h, trueY));
    setMousePos({ x: clampedX, y: clampedY });
  };

  const getImageCoordinates = (e: React.MouseEvent) => {
    if (!imageWrapperRef.current) return { x: 0, y: 0 };
    const rect = imageWrapperRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const dx = e.clientX - centerX;
    const dy = e.clientY - centerY;
    const rad = -rotation * (Math.PI / 180);
    const rotatedX = dx * Math.cos(rad) - dy * Math.sin(rad);
    const rotatedY = dx * Math.sin(rad) + dy * Math.cos(rad);
    const flippedX = rotatedX * flipH;
    const flippedY = rotatedY * flipV;
    const unscaledX = flippedX / scale;
    const unscaledY = flippedY / scale;
    return {
      x: unscaledX + imgSize.w / 2,
      y: unscaledY + imgSize.h / 2
    };
  };

  const calculateTrueCoordinates = (cssX: number, cssY: number) => {
    const ratioX = (originalSize.w > 0 && imgSize.w > 0) ? originalSize.w / imgSize.w : 1;
    const ratioY = (originalSize.h > 0 && imgSize.h > 0) ? originalSize.h / imgSize.h : 1;
    return {
      x: Math.round(cssX * ratioX),
      y: Math.round(cssY * ratioY)
    };
  };

  // --- 鼠标按下 ---
  const handleMouseDownWrapper = (e: React.MouseEvent<HTMLDivElement>) => {
    const isPanMode = isSpacePressed || activeTool === 'pan';

    if (activeTool === 'defect') {
      e.stopPropagation();
      const { x, y } = getImageCoordinates(e);

      if (drawingType === 'rect') {
        e.preventDefault();
        setIsDrawingDefect(true);
        setDefectStartPoint({ x, y });
        setCurrentDefectRect({ x, y, w: 0, h: 0 });
      }
      else if (drawingType === 'polygon') {
        setCurrentPolygonPoints(prev => [...prev, { x, y }]);
      }
      else if (drawingType === 'circle') {
        e.preventDefault();
        setIsDrawingDefect(true);
        setDefectStartPoint({ x, y });
        setCurrentDefectCircle({ x, y, r: 0 });
      }
    }
    else if (activeTool === 'setOrigin') {
      e.stopPropagation();
      e.preventDefault();
      const { x, y } = getImageCoordinates(e);
      setIsSettingOrigin(true);
      setTempOrigin({ x, y });
    }
    else if (activeTool === 'calibrate') {
      e.stopPropagation();
      e.preventDefault();
      const { x, y } = getImageCoordinates(e);
      setIsCalibrating(true);
      setCalibrateLine({ x1: x, y1: y, x2: x, y2: y });
    }
    else if (isPanMode) {
      setIsPanning(true);
      setPanStart({
        x: e.clientX - position.x,
        y: e.clientY - position.y
      });
      e.preventDefault();
    } else {
      handlers.onMouseDown && (handlers.onMouseDown as any)(e);
    }
  };

  // --- 鼠标移动 ---
  const handleMouseMoveWrapper = (e: React.MouseEvent<HTMLDivElement>) => {
    handleMouseMoveTracker(e);

    if (activeTool === 'defect') {
      if (drawingType === 'rect' && isDrawingDefect && defectStartPoint) {
        const { x: currX, y: currY } = getImageCoordinates(e);
        const newX = Math.min(defectStartPoint.x, currX);
        const newY = Math.min(defectStartPoint.y, currY);
        const newW = Math.abs(currX - defectStartPoint.x);
        const newH = Math.abs(currY - defectStartPoint.y);
        setCurrentDefectRect({ x: newX, y: newY, w: newW, h: newH });
      }
      else if (drawingType === 'polygon') {
        const coords = getImageCoordinates(e);
        setCursorInImage(coords);
      }
      else if (drawingType === 'circle' && isDrawingDefect && defectStartPoint) {
        const { x: currX, y: currY } = getImageCoordinates(e);
        const radius = Math.sqrt(Math.pow(currX - defectStartPoint.x, 2) + Math.pow(currY - defectStartPoint.y, 2));
        setCurrentDefectCircle({
          x: defectStartPoint.x,
          y: defectStartPoint.y,
          r: radius
        });
      }
    }
    else if (activeTool === 'setOrigin' && isSettingOrigin) {
      const { x, y } = getImageCoordinates(e);
      setTempOrigin({ x, y });
    }
    else if (activeTool === 'calibrate' && isCalibrating && calibrateLine) {
      const { x, y } = getImageCoordinates(e);
      setCalibrateLine({ ...calibrateLine, x2: x, y2: y });
    }
    else if (isPanning) {
      const newX = e.clientX - panStart.x;
      const newY = e.clientY - panStart.y;
      setPosition({ x: newX, y: newY });
    } else {
      handlers.onMouseMove && (handlers.onMouseMove as any)(e);
    }
  };

  // --- 鼠标松开 ---
  const handleMouseUpWrapper = (e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool === 'defect') {
      // --- 1. 矩形结束，触发弹窗 ---
      if (drawingType === 'rect' && isDrawingDefect && currentDefectRect) {
        setIsDrawingDefect(false);
        if (currentDefectRect.w > 2 && currentDefectRect.h > 2) {
          // 暂存形状，打开弹窗
          setPendingShape(currentDefectRect);
          setPendingShapeType('rect');
          setSelectedLabelCode(null); // 重置选择
          setLabelModalVisible(true);
        }
        setCurrentDefectRect(null);
        setDefectStartPoint(null);
      }
      // --- 2. 圆形结束，触发弹窗 ---
      else if (drawingType === 'circle' && isDrawingDefect && currentDefectCircle) {
        setIsDrawingDefect(false);
        if (currentDefectCircle.r > 2) {
          setPendingShape(currentDefectCircle);
          setPendingShapeType('circle');
          setSelectedLabelCode(null);
          setLabelModalVisible(true);
        }
        setCurrentDefectCircle(null);
        setDefectStartPoint(null);
      }
    }
    else if (activeTool === 'setOrigin' && isSettingOrigin && tempOrigin) {
      setIsSettingOrigin(false);
      const trueCoords = calculateTrueCoordinates(tempOrigin.x, tempOrigin.y);
      setOriginPoint(trueCoords);
      message.success(`坐标原点已设置: (${trueCoords.x}, ${trueCoords.y})`);
      setTempOrigin(null);
      setActiveTool('pan');
    }
    else if (activeTool === 'calibrate' && isCalibrating && calibrateLine) {
      setIsCalibrating(false);
      const dx = calibrateLine.x2 - calibrateLine.x1;
      const dy = calibrateLine.y2 - calibrateLine.y1;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist > 5) {
        setMeasuredPixelDistance(parseFloat(dist.toFixed(2)));
        setCalibrateModalVisible(true);
        setActualLength(null);
      } else {
        setCalibrateLine(null);
      }
    }
    else if (isPanning) {
      setIsPanning(false);
    } else {
      handlers.onMouseUp && (handlers.onMouseUp as any)(e);
    }
  };

  // --- 双击事件 (多边形结束绘制) ---
  const handleDoubleClickWrapper = (e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool === 'defect' && drawingType === 'polygon') {
      e.stopPropagation();
      e.preventDefault();

      if (currentPolygonPoints.length >= 3) {
        // --- 3. 多边形结束，触发弹窗 ---
        setPendingShape({ points: currentPolygonPoints });
        setPendingShapeType('polygon');
        setSelectedLabelCode(null);
        setLabelModalVisible(true);
      } else {
        message.warning("多边形至少需要3个点");
      }

      setCurrentPolygonPoints([]);
    }
  };

  const handleMouseLeaveWrapper = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isPanning) setIsPanning(false);
    if (activeTool === 'setOrigin') setIsSettingOrigin(false);
    if (isDrawingDefect) {
      setIsDrawingDefect(false);
      setCurrentDefectRect(null);
      setCurrentDefectCircle(null);
    }
    setCursorInImage(null);
    handlers.onMouseLeave && (handlers.onMouseLeave as any)(e);
  };

  const handleCalibrateConfirm = () => {
    if (actualLength && measuredPixelDistance > 0) {
      const ratio = actualLength / measuredPixelDistance;
      setPixelRatio(parseFloat(ratio.toFixed(4)));
      message.success(`标定成功：1px ≈ ${ratio.toFixed(4)}mm`);
      setCalibrateModalVisible(false);
      setCalibrateLine(null);
      setActiveTool('pan');
    } else {
      message.warning('请输入有效的实际长度');
    }
  };

  // --- 3. 确认缺陷分类，保存最终数据 ---
  const handleLabelConfirm = () => {
    if (!selectedLabelCode || !pendingShape) {
      message.warning("请选择缺陷类型");
      return;
    }

    const defectType = DEFECT_TYPES.find(d => d.code === selectedLabelCode);
    const color = defectType?.color || '#f5222d';
    const label = defectType?.name || '未知';

    // 初始化额外信息，实际场景中可能从几何计算得出
    const defaultExtra = {
      position: '',
      size: '',
      quality: '',
      remark: ''
    };

    if (pendingShapeType === 'rect') {
      const { w, h, x, y } = pendingShape;
      const trueW = Math.round(w * widthRatio);
      const trueH = Math.round(h * heightRatio);
      // 简单计算一下中心位置和宽高作为默认值
      const sizeStr = `${trueW}x${trueH}`;

      const newRect: SavedRect = { ...pendingShape, label, color, ...defaultExtra, size: sizeStr };
      setDefectRects([...defectRects, newRect]);
    } else if (pendingShapeType === 'polygon') {
      const newPoly: SavedPolygon = { ...pendingShape, label, color, ...defaultExtra };
      setDefectPolygons([...defectPolygons, newPoly]);
    } else if (pendingShapeType === 'circle') {
      const newCircle: SavedCircle = { ...pendingShape, label, color, ...defaultExtra };
      setDefectCircles([...defectCircles, newCircle]);
    }

    // 关闭弹窗并清理
    setLabelModalVisible(false);
    setPendingShape(null);
    setSelectedLabelCode(null);
    message.success(`已标记为: ${label}`);
  };

  const handleSaveDefect = () => {
    message.success(`标注数据已保存: ${defectRects.length}个矩形, ${defectPolygons.length}个多边形, ${defectCircles.length}个圆形`);
    setActiveTool('pan');
  };

  const paginatedFiles = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return files.slice(start, start + pageSize);
  }, [files, currentPage]);

  useEffect(() => {
    if (files.length > 0 && !selectedFile) {
      setSelectedFile(files[0]);
    }
  }, [files]);

  // 使用 useRef 保存之前的 TaskFileId，避免重复加载
  const prevTaskFileIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (selectedFile && selectedFile.TaskFileId !== prevTaskFileIdRef.current) {
      // 记录当前处理的文件ID
      prevTaskFileIdRef.current = selectedFile.TaskFileId;

      // 从后端加载底片信息字段
      filmInfoForm.setFieldsValue({
        weldId: selectedFile.WeldId || '',
        filmNumber: selectedFile.FilmNumber || '',
        filmDensity: selectedFile.FilmDensity || '',
        sensitivity: selectedFile.Sensitivity || '',
      });

      // 从后端加载缺陷记录
      defectRecordAPI.getByTaskFileId(selectedFile.TaskFileId).then(resp => {
        if (resp.Data && resp.Data.length > 0) {
          // 将后端 DefectRecord 转换为前端格式，根据几何类型分类
          const loadedRects: SavedRect[] = [];
          const loadedCircles: SavedCircle[] = [];
          const loadedPolygons: SavedPolygon[] = [];

          resp.Data.forEach((dr: DefectRecord) => {
            // 从 Geometry 字段解析几何坐标
            let geometry: any = null;
            try {
              geometry = dr.Geometry ? JSON.parse(dr.Geometry) : null;
            } catch (e) {
              console.warn('Failed to parse defect geometry:', dr.Geometry);
            }

            // Position 是算法计算的位置，直接使用数据库值
            const baseInfo = {
              label: dr.DefectName || '未知',
              color: DEFECT_TYPES.find(d => d.name === dr.DefectName)?.color || '#f5222d',
              position: dr.Position || '',  // 算法位置，空则显示空
              size: dr.Size || '',
              quality: dr.Grade || '',
              remark: dr.Remark || '',
              defectRecordId: dr.DefectRecordId,
            };

            if (geometry?.type === 'circle') {
              loadedCircles.push({
                x: geometry.x ?? 0,
                y: geometry.y ?? 0,
                r: geometry.r ?? 25,
                ...baseInfo,
              });
            } else if (geometry?.type === 'polygon' && Array.isArray(geometry.points)) {
              loadedPolygons.push({
                points: geometry.points,
                ...baseInfo,
              });
            } else {
              // 默认为矩形或无法解析时作为矩形处理
              loadedRects.push({
                x: geometry?.x ?? 0,
                y: geometry?.y ?? 0,
                w: geometry?.w ?? 50,
                h: geometry?.h ?? 50,
                ...baseInfo,
              });
            }
          });

          setDefectRects(loadedRects);
          setDefectCircles(loadedCircles);
          setDefectPolygons(loadedPolygons);
        } else {
          setDefectRects([]);
          setDefectCircles([]);
          setDefectPolygons([]);
        }
        // 加载完成后延迟标记，允许后续用户操作触发自动保存
        setTimeout(() => { isInitialLoadRef.current = false; }, 100);
      }).catch(() => {
        setDefectRects([]);
        setDefectCircles([]);
        setDefectPolygons([]);
        setTimeout(() => { isInitialLoadRef.current = false; }, 100);
      });

      // 切换文件时标记为初始加载状态
      isInitialLoadRef.current = true;

      resetWindow();
      setScale(1);
      setRotation(0);
      setFlipH(1);
      setFlipV(1);
      setPosition({ x: 0, y: 0 });
      setCalibrateLine(null);
      setOriginPoint(null);
      setTempOrigin(null);
      setCurrentPolygonPoints([]);
      setShowDefectList(true); // 每次切换文件，默认展开缺陷列表
      setShowFilmInfo(true);   // 每次切换文件，默认展开底片信息
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedFile?.TaskFileId]);

  // --- 监听缺陷数组变化，触发自动保存（跳过初始加载）---
  useEffect(() => {
    if (isInitialLoadRef.current || !selectedFile) return;
    autoSaveDefects();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defectRects, defectPolygons, defectCircles]);

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(files.map(f => f.TaskFileId)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectOne = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) newSelected.add(id);
    else newSelected.delete(id);
    setSelectedIds(newSelected);
  };

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

  const [isNegative, setIsNegative] = useState(false);

  const handleSave = async () => {
    if (!selectedFile) return;
    try {
      const infoValues = await filmInfoForm.validateFields();

      // 1. 保存底片信息
      await reportAPI.reviewFile(selectedFile.TaskFileId, {
        ManualResult: selectedFile.VisionResult || "{}",
        PlateQuality: '',  // 不再使用文件级别的质量评级，改为缺陷级别的等级
        WeldId: infoValues.weldId,
        FilmNumber: infoValues.filmNumber,
        FilmDensity: infoValues.filmDensity,
        Sensitivity: infoValues.sensitivity,
      });

      // 2. 保存缺陷记录（替换式更新）
      // Position 保持算法计算的位置，Geometry 存储几何坐标
      const allDefects = [
        ...defectRects.map(d => ({
          TaskFileId: selectedFile.TaskFileId,
          DefectName: d.label,
          Position: d.position || '',  // 算法位置，空则保持空
          Geometry: JSON.stringify({
            type: 'rect',
            x: d.x,
            y: d.y,
            w: d.w,
            h: d.h,
          }),
          Size: d.size || '',
          Grade: d.quality || '',
          Remark: d.remark || '',
        })),
        ...defectPolygons.map(d => ({
          TaskFileId: selectedFile.TaskFileId,
          DefectName: d.label,
          Position: d.position || '',
          Geometry: JSON.stringify({
            type: 'polygon',
            points: d.points,
          }),
          Size: d.size || '',
          Grade: d.quality || '',
          Remark: d.remark || '',
        })),
        ...defectCircles.map(d => ({
          TaskFileId: selectedFile.TaskFileId,
          DefectName: d.label,
          Position: d.position || '',
          Geometry: JSON.stringify({
            type: 'circle',
            x: d.x,
            y: d.y,
            r: d.r,
          }),
          Size: d.size || '',
          Grade: d.quality || '',
          Remark: d.remark || '',
        })),
      ];

      if (allDefects.length > 0) {
        await defectRecordAPI.replace(selectedFile.TaskFileId, allDefects);
      } else {
        // 如果没有缺陷，删除该文件的所有缺陷记录
        await defectRecordAPI.deleteByTaskFileId(selectedFile.TaskFileId);
      }

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
      message.error("保存失败，请重试");
    }
  };

  // --- 自动保存：底片信息（防抖 1 秒）---
  const { run: autoSaveFilmInfo } = useDebounceFn(
    async () => {
      if (!selectedFile) return;
      try {
        const values = await filmInfoForm.validateFields();
        await reportAPI.reviewFile(selectedFile.TaskFileId, {
          ManualResult: selectedFile.VisionResult || "{}",
          PlateQuality: '',  // 不再使用文件级别评级
          WeldId: values.weldId,
          FilmNumber: values.filmNumber,
          FilmDensity: values.filmDensity,
          Sensitivity: values.sensitivity,
        });
        console.log('底片信息已自动保存');
      } catch (err) {
        console.error('自动保存底片信息失败:', err);
      }
    },
    { wait: 1000 }
  );

  // --- 自动保存：缺陷记录（防抖 500ms）---
  const { run: autoSaveDefects } = useDebounceFn(
    async () => {
      if (!selectedFile) return;
      try {
        const allDefects = [
          ...defectRects.map(d => ({
            TaskFileId: selectedFile.TaskFileId,
            DefectName: d.label,
            Position: d.position || '',
            Geometry: JSON.stringify({ type: 'rect', x: d.x, y: d.y, w: d.w, h: d.h }),
            Size: d.size || '',
            Grade: d.quality || '',
            Remark: d.remark || '',
          })),
          ...defectPolygons.map(d => ({
            TaskFileId: selectedFile.TaskFileId,
            DefectName: d.label,
            Position: d.position || '',
            Geometry: JSON.stringify({ type: 'polygon', points: d.points }),
            Size: d.size || '',
            Grade: d.quality || '',
            Remark: d.remark || '',
          })),
          ...defectCircles.map(d => ({
            TaskFileId: selectedFile.TaskFileId,
            DefectName: d.label,
            Position: d.position || '',
            Geometry: JSON.stringify({ type: 'circle', x: d.x, y: d.y, r: d.r }),
            Size: d.size || '',
            Grade: d.quality || '',
            Remark: d.remark || '',
          })),
        ];

        if (allDefects.length > 0) {
          await defectRecordAPI.replace(selectedFile.TaskFileId, allDefects);
        } else {
          await defectRecordAPI.deleteByTaskFileId(selectedFile.TaskFileId);
        }
        console.log('缺陷记录已自动保存');
      } catch (err) {
        console.error('自动保存缺陷记录失败:', err);
      }
    },
    { wait: 500 }
  );

  const widthRatio = (originalSize.w > 0 && imgSize.w > 0) ? (originalSize.w / imgSize.w) : 1;
  const heightRatio = (originalSize.h > 0 && imgSize.h > 0) ? (originalSize.h / imgSize.h) : 1;

  const displayOrigin = useMemo(() => {
    if (activeTool === 'setOrigin' && tempOrigin) {
      return calculateTrueCoordinates(tempOrigin.x, tempOrigin.y);
    }
    return originPoint || { x: 0, y: 0 };
  }, [activeTool, tempOrigin, originPoint, originalSize, imgSize]);

  // --- 更新缺陷信息的辅助函数 ---
  const updateDefectInfo = (
    type: 'rect' | 'polygon' | 'circle',
    index: number,
    field: keyof DefectBase,
    value: any
  ) => {
    if (type === 'rect') {
      const newArr = [...defectRects];
      if (field === 'label') {
        // 如果是修改类型，同时更新颜色
        const match = DEFECT_TYPES.find(d => d.name === value);
        if (match) {
          newArr[index].color = match.color;
        }
      }
      (newArr[index] as any)[field] = value;
      setDefectRects(newArr);
    } else if (type === 'polygon') {
      const newArr = [...defectPolygons];
      if (field === 'label') {
        const match = DEFECT_TYPES.find(d => d.name === value);
        if (match) newArr[index].color = match.color;
      }
      (newArr[index] as any)[field] = value;
      setDefectPolygons(newArr);
    } else if (type === 'circle') {
      const newArr = [...defectCircles];
      if (field === 'label') {
        const match = DEFECT_TYPES.find(d => d.name === value);
        if (match) newArr[index].color = match.color;
      }
      (newArr[index] as any)[field] = value;
      setDefectCircles(newArr);
    }
    // 触发自动保存
    autoSaveDefects();
  };

  const deleteDefect = (type: 'rect' | 'polygon' | 'circle', index: number) => {
    if (type === 'rect') {
      const newArr = [...defectRects];
      newArr.splice(index, 1);
      setDefectRects(newArr);
    } else if (type === 'polygon') {
      const newArr = [...defectPolygons];
      newArr.splice(index, 1);
      setDefectPolygons(newArr);
    } else if (type === 'circle') {
      const newArr = [...defectCircles];
      newArr.splice(index, 1);
      setDefectCircles(newArr);
    }
    // 触发自动保存
    autoSaveDefects();
  };

  // 切换单个缺陷项的展开/收起状态
  const toggleDefectExpand = (key: string) => {
    setExpandedDefects(prev => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
  };

  // 生成缺陷编辑卡片（支持展开/收起）
  const renderDefectCard = (item: DefectBase, index: number, type: 'rect' | 'polygon' | 'circle', globalIndex: number) => {
    const defectKey = `${type}-${index}`;
    const isExpanded = expandedDefects.has(defectKey);

    return (
      <div key={defectKey} style={{
        background: globalIndex % 2 === 0 ? '#f6ffed' : '#fffbe6',
        border: `1px solid ${item.color || '#f0f0f0'}`,
        borderLeft: `5px solid ${item.color || '#f0f0f0'}`,
        borderRadius: '4px',
        marginBottom: '8px',
        padding: isExpanded ? '12px' : '8px 12px'
      }}>
        {/* 头部：展开/收起 + 序号 + 缺陷类型 + 删除 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* 展开/收起按钮 - 放在最左侧 */}
          <Button
            type="text"
            size="small"
            icon={isExpanded ? <UpOutlined /> : <DownOutlined />}
            onClick={() => toggleDefectExpand(defectKey)}
            style={{ color: '#8c8c8c', padding: 0, width: 20 }}
          />

          <span style={{ fontWeight: 'bold', color: '#8c8c8c', width: 20 }}>{globalIndex + 1}</span>

          {isExpanded ? (
            // 展开时显示下拉选择
            <Select
              size="small"
              value={item.label}
              style={{ flex: 1 }}
              onChange={(val) => updateDefectInfo(type, index, 'label', val)}
            >
              {DEFECT_TYPES.map(dt => (
                <Option key={dt.code} value={dt.name}>
                  <span style={{ color: dt.color, marginRight: 4 }}>●</span>{dt.name}
                </Option>
              ))}
            </Select>
          ) : (
            // 收起时只显示类型标签
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: item.color, fontSize: 14 }}>●</span>
              <span style={{ color: '#262626', fontSize: 13 }}>{item.label}</span>
              {item.position && <span style={{ color: '#8c8c8c', fontSize: 12 }}>({item.position})</span>}
            </div>
          )}

          {/* 删除按钮 */}
          <Popconfirm title="确定删除此缺陷?" onConfirm={() => deleteDefect(type, index)}>
            <Button type="text" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </div>

        {/* 展开时显示详细信息 */}
        {isExpanded && (
          <div style={{ marginTop: 12 }}>
            {/* 位置 */}
            <div style={{ marginBottom: 8 }}>
              <Input
                size="small"
                placeholder="请输入缺陷位置"
                addonBefore="位置"
                value={item.position}
                onChange={(e) => updateDefectInfo(type, index, 'position', e.target.value)}
              />
            </div>
            {/* 尺寸 */}
            <div style={{ marginBottom: 8 }}>
              <Input
                size="small"
                placeholder="请输入尺寸"
                addonBefore="尺寸"
                value={item.size}
                onChange={(e) => updateDefectInfo(type, index, 'size', e.target.value)}
              />
            </div>
            {/* 等级 - 下拉选择 */}
            <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center' }}>
              <span style={{
                backgroundColor: '#fafafa',
                border: '1px solid #d9d9d9',
                borderRight: 'none',
                borderRadius: '2px 0 0 2px',
                padding: '0 11px',
                height: '24px',
                lineHeight: '22px',
                fontSize: '14px',
                color: 'rgba(0, 0, 0, 0.85)'
              }}>等级</span>
              <Select
                size="small"
                placeholder="请选择质量等级"
                value={item.quality || undefined}
                style={{ flex: 1 }}
                onChange={(val) => updateDefectInfo(type, index, 'quality', val)}
              >
                <Option value="一级">I 级 (优)</Option>
                <Option value="二级">II 级 (良)</Option>
                <Option value="三级">III 级 (中)</Option>
                <Option value="四级">IV 级 (差)</Option>
              </Select>
            </div>
            {/* 备注 */}
            <div>
              <Input
                size="small"
                placeholder="请输入备注"
                addonBefore="备注"
                value={item.remark}
                onChange={(e) => updateDefectInfo(type, index, 'remark', e.target.value)}
              />
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <Layout style={{ height: "100%", background: "#fff", margin: 0, padding: 0 }}>
      {/* 左侧文件列表 (保持不变) */}
      <Sider width={250} theme="light" style={{ borderRight: "1px solid #f0f0f0", display: 'flex', flexDirection: 'column' }}>
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
            onClick={() => onPreview && onPreview()}
          >
            预览报告
          </Button>
        </div>
      </Sider>

      {/* 中间编辑区 */}
      <Content style={{ display: "flex", flexDirection: "column", background: '#f0f2f5' }}>
        {/* 顶部工具栏 (保持不变) */}
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

            <Tooltip title="重置视图">
              <Button
                type="text" ghost
                icon={<img src="/fullscreen.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />}
                style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                onClick={() => {
                  setScale(1); setRotation(0); setFlipH(1); setFlipV(1);
                  setPosition({ x: 0, y: 0 });
                  resetWindow();
                }} /></Tooltip>

            <Divider type="vertical" style={{ background: '#434343', margin: '0 8px', height: 20 }} />
            <Tooltip title="窗宽调整">
              <Button type="text" ghost
                icon={<img src="/contrast.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />}
                onClick={() => setActiveTool(activeTool === 'windowing' ? 'pan' : 'windowing')}
                style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: activeTool === 'windowing' ? '#1890ff' : 'transparent' }}
              />
            </Tooltip>
            <Tooltip title="负片">
              <Button
                type={isNegative ? 'primary' : 'text'}
                ghost={!isNegative}
                onClick={() => setIsNegative(!isNegative)}
                icon={<img src="/negative.svg" alt="negative" style={{ width: 16, height: 16, filter: 'invert(1)' }} />}
                style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: isNegative ? '#1890ff' : 'transparent' }} /></Tooltip>
            <Divider type="vertical" style={{ background: '#434343', margin: '0 8px', height: 20 }} />

            <Tooltip title="缺陷标记">
              <Button
                type={activeTool === 'defect' ? 'primary' : 'text'}
                ghost={activeTool !== 'defect'}
                icon={<img src="/circle-alert.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />}
                style={{
                  color: '#fff', width: 36, height: 32, padding: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: activeTool === 'defect' ? '#1890ff' : 'transparent'
                }}
                onClick={() => setActiveTool(activeTool === 'defect' ? 'pan' : 'defect')}
              />
            </Tooltip>

            <Tooltip title="数字识别"><Button type="text" ghost icon={<img src="/type.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} /></Tooltip>
            <Divider type="vertical" style={{ background: '#434343', margin: '0 8px', height: 20 }} />

            <Tooltip title="设置坐标原点">
              <Button
                type={activeTool === 'setOrigin' ? 'primary' : 'text'}
                ghost={activeTool !== 'setOrigin'}
                onClick={() => {
                  if (activeTool !== 'setOrigin') {
                    setTempOrigin(null);
                    setIsSettingOrigin(false);
                  }
                  setActiveTool(activeTool === 'setOrigin' ? 'pan' : 'setOrigin')
                }}
                icon={<img src="/mouse-pointer-2.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />}
                style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: activeTool === 'setOrigin' ? '#1890ff' : 'transparent' }}
              />
            </Tooltip>

            <Tooltip title="测量距离">
              <Button
                type={activeTool === 'measure' ? 'primary' : 'text'}
                ghost={activeTool !== 'measure'} icon={<img src="/ruler.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />}
                onClick={() => setActiveTool(activeTool === 'measure' ? 'pan' : 'measure')}
                style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: activeTool === 'measure' ? '#1890ff' : 'transparent' }} /></Tooltip>


            <Divider type="vertical" style={{ background: '#434343', margin: '0 8px', height: 20 }} />

            <Tooltip title="左旋90°"><Button type="text" ghost icon={<img src="/rotate-ccw.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setRotation(r => r - 90)} /></Tooltip>
            <Tooltip title="右转90°"><Button type="text" ghost icon={<img src="/rotate-cw.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setRotation(r => r + 90)} /></Tooltip>
            <Tooltip title="旋转180°"><Button type="text" ghost icon={<img src="/refresh-ccw.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setRotation(r => r + 180)} /></Tooltip>
            <Tooltip title="水平翻转"><Button type="text" ghost icon={<img src="/flip-horizontal-2.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setFlipV(v => v * -1)} /></Tooltip>
            <Tooltip title="垂直翻转"><Button type="text" ghost icon={<img src="/flip-vertical-2.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setFlipH(h => h * -1)} /></Tooltip>
          </Space>

          <Space size={8}>
            <Button
              type={activeTool === 'calibrate' ? 'primary' : 'text'}
              ghost={activeTool !== 'calibrate'}
              icon={<ColumnWidthOutlined />}
              onClick={() => {
                setActiveTool(activeTool === 'calibrate' ? 'pan' : 'calibrate');
                setCalibrateLine(null);
              }}
              style={{
                color: '#fff', fontSize: '12px', height: 28, padding: '0 12px',
                background: activeTool === 'calibrate' ? '#1890ff' : '#303030',
                borderRadius: '4px', display: 'flex', alignItems: 'center'
              }}
            >
              尺寸定标
            </Button>

            <div style={{ background: '#262626', height: 28, borderRadius: '4px', display: 'flex', alignItems: 'center', padding: '0 8px', fontSize: '11px', color: '#8c8c8c' }}>
              <LinkOutlined style={{ transform: 'rotate(-45deg)', marginRight: 4 }} />
              <div style={{ textAlign: 'center', lineHeight: 1.1 }}>
                <div>1px</div>
                <div style={{ borderTop: '1px solid #595959', marginTop: 1 }}>
                  {pixelRatio ? `${pixelRatio}mm` : '未标定'}
                </div>
              </div>
            </div>

            <div style={{ background: '#262626', height: 28, borderRadius: '4px', display: 'flex', alignItems: 'center', padding: '0 8px', fontSize: '11px', color: '#8c8c8c' }}>
              <AimOutlined style={{ color: '#1890ff', marginRight: 4 }} />
              <div style={{ textAlign: 'left', lineHeight: 1.1 }}>
                <div>原点:</div>
                <div style={{ color: '#fff' }}>
                  ({displayOrigin.x}, {displayOrigin.y})
                </div>
              </div>
            </div>

          </Space>
        </div>

        {/* 图片容器 */}
        <div style={{
          flex: 1,
          position: 'relative',
          overflow: 'hidden',
          background: '#262626',
          display: 'grid',
          gridTemplateColumns: '20px 1fr',
          gridTemplateRows: '20px 1fr',
        }}
        >
          {/* 左上角单位 */}
          <div style={{ background: '#1f1f1f', color: '#8c8c8c', fontSize: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderBottom: '1px solid #303030', borderRight: '1px solid #303030', zIndex: 20 }}>
            PX
          </div>

          {/* 顶部标尺 */}
          <div style={{ overflow: 'hidden', position: 'relative', zIndex: 10 }}>
            <Ruler type="horizontal" scale={scale} offset={imageOffset.x} length={containerSize.w} ratio={widthRatio} maxImageSize={originalSize.w} />
          </div>

          {/* 左侧标尺 */}
          <div style={{ overflow: 'hidden', position: 'relative', zIndex: 10 }}>
            <Ruler type="vertical" scale={scale} offset={imageOffset.y} length={containerSize.h} ratio={heightRatio} maxImageSize={originalSize.h} />
          </div>

          {/* 图片视口 */}
          <div
            ref={setCanvasContainer}
            style={{ position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            {selectedFile ? (
              <div
                ref={imageWrapperRef}
                onWheel={handleWheel}

                onMouseDown={handleMouseDownWrapper}
                onMouseMove={handleMouseMoveWrapper}
                onMouseUp={handleMouseUpWrapper}
                onMouseLeave={handleMouseLeaveWrapper}
                onDoubleClick={handleDoubleClickWrapper}

                style={{
                  position: "relative",
                  display: 'inline-block',
                  transform: `translate(${position.x}px, ${position.y}px) scale(${scale * flipH}, ${scale * flipV}) rotate(${rotation}deg)`,
                  transformOrigin: 'center center',
                  transition: 'none',
                  cursor: cursorStyle
                }}
                onTransitionEnd={() => updateImageOffset()}
              >
                <canvas
                  ref={canvasRef}
                  style={{
                    maxHeight: "calc(100vh - 280px)",
                    maxWidth: "100%",
                    boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
                    display: 'block',
                    userSelect: (activeTool === 'measure' || activeTool === 'calibrate' || activeTool === 'setOrigin') ? 'none' : 'auto',
                    filter: isNegative ? 'invert(100%)' : 'none'
                  }}
                />

                {/* --- 1. Window Level 选框 --- */}
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

                {/* --- 2. 缺陷标注层 (SVG) --- */}
                <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 100 }}>

                  {/* A. 绘制已保存的矩形 (增加 label 和 color) */}
                  {defectRects.map((rect, idx) => (
                    <g key={`rect-${idx}`}>
                      <rect
                        x={rect.x} y={rect.y} width={rect.w} height={rect.h}
                        stroke={rect.color} strokeWidth={2 / scale} fill="none"
                      />
                      {/* 缺陷名字标签 */}
                      <text
                        x={rect.x} y={rect.y - 5}
                        fill={rect.color} fontSize={14 / scale} fontWeight="bold"
                        style={{ textShadow: '0 0 2px #000' }}
                      >
                        {rect.label}
                      </text>
                    </g>
                  ))}

                  {/* B. 绘制已保存的多边形 */}
                  {defectPolygons.map((poly, idx) => (
                    <g key={`poly-${idx}`}>
                      <polygon
                        points={poly.points.map(p => `${p.x},${p.y}`).join(' ')}
                        stroke={poly.color} strokeWidth={2 / scale} fill="none"
                      />
                      {/* 缺陷名字标签 - 取第一个点上方 */}
                      <text
                        x={poly.points[0].x} y={poly.points[0].y - 5}
                        fill={poly.color} fontSize={14 / scale} fontWeight="bold"
                        style={{ textShadow: '0 0 2px #000' }}
                      >
                        {poly.label}
                      </text>
                    </g>
                  ))}

                  {/* C. 绘制已保存的圆形 */}
                  {defectCircles.map((circle, idx) => (
                    <g key={`circle-${idx}`}>
                      <circle
                        cx={circle.x}
                        cy={circle.y}
                        r={circle.r}
                        stroke={circle.color}
                        strokeWidth={2 / scale}
                        fill="none"
                      />
                      {/* 缺陷名字标签 - 圆顶上方 */}
                      <text
                        x={circle.x} y={circle.y - circle.r - 5}
                        fill={circle.color} fontSize={14 / scale} fontWeight="bold"
                        style={{ textShadow: '0 0 2px #000' }}
                      >
                        {circle.label}
                      </text>
                    </g>
                  ))}

                  {/* D. 绘制当前正在拖拽的矩形 (虚线框, 默认红色) */}
                  {activeTool === 'defect' && drawingType === 'rect' && currentDefectRect && (
                    <rect
                      x={currentDefectRect.x}
                      y={currentDefectRect.y}
                      width={currentDefectRect.w}
                      height={currentDefectRect.h}
                      stroke="#f5222d" strokeWidth={2 / scale} strokeDasharray="4 2" fill="rgba(245, 34, 45, 0.1)"
                    />
                  )}

                  {/* E. 绘制当前正在绘制的多边形 (蓝色折线 + 橡皮筋线) */}
                  {activeTool === 'defect' && drawingType === 'polygon' && currentPolygonPoints.length > 0 && (
                    <>
                      <polyline
                        points={currentPolygonPoints.map(p => `${p.x},${p.y}`).join(' ')}
                        fill="none" stroke="#1890ff" strokeWidth={2 / scale}
                      />
                      {currentPolygonPoints.map((p, idx) => (
                        <circle key={`pt-${idx}`} cx={p.x} cy={p.y} r={3 / scale} fill="#fff" stroke="#1890ff" strokeWidth={1 / scale} />
                      ))}
                      {cursorInImage && (
                        <line
                          x1={currentPolygonPoints[currentPolygonPoints.length - 1].x}
                          y1={currentPolygonPoints[currentPolygonPoints.length - 1].y}
                          x2={cursorInImage.x}
                          y2={cursorInImage.y}
                          stroke="#1890ff" strokeWidth={1 / scale} strokeDasharray="4 2"
                        />
                      )}
                    </>
                  )}

                  {/* F. 绘制当前正在绘制的圆形 (虚线圆) */}
                  {activeTool === 'defect' && drawingType === 'circle' && currentDefectCircle && (
                    <circle
                      cx={currentDefectCircle.x}
                      cy={currentDefectCircle.y}
                      r={currentDefectCircle.r}
                      stroke="#f5222d"
                      strokeWidth={2 / scale}
                      strokeDasharray="4 2"
                      fill="rgba(245, 34, 45, 0.1)"
                    />
                  )}

                </svg>

                {/* 3. 坐标原点十字线 */}
                {activeTool === 'setOrigin' && tempOrigin && (
                  <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 12 }}>
                    <line x1={tempOrigin.x} y1={0} x2={tempOrigin.x} y2="100%" stroke="#f5222d" strokeWidth={1 / scale} />
                    <line x1={0} y1={tempOrigin.y} x2="100%" y2={tempOrigin.y} stroke="#f5222d" strokeWidth={1 / scale} />
                    <text x={tempOrigin.x + 10} y={tempOrigin.y - 6} fill="#f5222d" fontSize={12 / scale} style={{ userSelect: 'none' }}>x</text>
                    <text x={tempOrigin.x + 6} y={tempOrigin.y + 14} fill="#f5222d" fontSize={12 / scale} style={{ userSelect: 'none' }}>y</text>
                  </svg>
                )}

                {/* 4. 标定线绘制层 */}
                {activeTool === 'calibrate' && calibrateLine && (
                  <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 15 }}>
                    <line x1={calibrateLine.x1} y1={calibrateLine.y1} x2={calibrateLine.x2} y2={calibrateLine.y2} stroke="#faad14" strokeWidth={2 / scale} strokeDasharray="4 2" />
                    <circle cx={calibrateLine.x1} cy={calibrateLine.y1} r={3 / scale} fill="#faad14" />
                    <circle cx={calibrateLine.x2} cy={calibrateLine.y2} r={3 / scale} fill="#faad14" />
                  </svg>
                )}

                <GeometricMeasureTool
                  visible={activeTool === 'measure'}
                  imageUrl={previewUrl}
                  width={imgSize.w}
                  height={imgSize.h}
                  pixelRatio={pixelRatio}
                  scale={scale}
                  rotation={rotation}
                  flipH={flipH}
                  flipV={flipV}
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

          {/* 悬浮工具条 */}
          {activeTool === 'defect' && (
            <div style={{
              position: 'absolute',
              left: '32px',
              top: '32px',
              zIndex: 300
            }}>
              <DefectMarking
                currentType={drawingType}
                onTypeChange={setDrawingType}
                onClose={() => setActiveTool('pan')}
              />
            </div>
          )}

        </div>

        {/* 底部状态条 */}
        <div style={{ height: 28, background: '#f8f9fa', borderTop: '1px solid #e9ecef', display: 'flex', alignItems: 'center', padding: '0 16px', fontSize: '11px', color: '#6c757d' }}>
          {/* 显示图像尺寸和实时鼠标坐标 */}
          图像尺寸：{originalSize.w}*{originalSize.h}，鼠标位置：{mousePos.x}*{mousePos.y},当前工具: {activeTool === 'calibrate' ? '尺寸定标' : activeTool === 'measure' ? '测量' : activeTool === 'setOrigin' ? '设置原点' : activeTool === 'defect' ? '缺陷标注' : '窗位窗宽'}
        </div>
      </Content>

      {/* 右侧审核信息 (重构区域) */}
      <Sider width={320} theme="light" style={{ borderLeft: "1px solid #f0f0f0", display: 'flex', flexDirection: 'column', background: '#fff' }}>
        {/* 修改点：设置 height: 100% 和 overflowY: auto，
            确保内容超出时，这个容器内部出现滚动条，而不是把页面撑开。
           */}
        <div style={{ flex: 1, padding: '20px 16px', overflowY: 'auto', height: '100%' }}>
          <Space direction="vertical" style={{ width: '100%' }} size={24}>

            {/* 1. 底片信息 (垂直布局，可编辑，带折叠) */}
            <div>
              {/* 修改点：
                        1. 图标放在文字前面 (flex-direction: row 是默认)
                        2. 增加背景色和圆角
                    */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: 12,
                  cursor: 'pointer',
                  userSelect: 'none',
                  backgroundColor: '#e6f7ff', // 与左侧选中背景色一致
                  padding: '8px 12px',
                  borderRadius: '4px'
                }}
                onClick={() => setShowFilmInfo(!showFilmInfo)}
              >
                {/* 图标在前 */}
                {showFilmInfo ?
                  <UpOutlined style={{ fontSize: '12px', color: '#1890ff', marginRight: 8 }} /> :
                  <DownOutlined style={{ fontSize: '12px', color: '#1890ff', marginRight: 8 }} />
                }
                <Title level={5} style={{ margin: 0, fontSize: '15px' }}>底片信息</Title>
              </div>

              {/* 修改点：内容根据状态显示或隐藏 */}
              {showFilmInfo && (
                // 修改点：布局改为 horizontal，并设置 labelCol 和 wrapperCol
                <Form
                  form={filmInfoForm}
                  layout="horizontal"
                  size="small"
                  labelCol={{ span: 10 }}
                  wrapperCol={{ span: 14 }}
                  labelAlign="left"
                  style={{ padding: '0 8px' }} // 稍微缩进一点内容
                  onValuesChange={autoSaveFilmInfo}
                >
                  <Form.Item name="weldId" label="焊口编号" style={{ marginBottom: 12 }}>
                    <Input placeholder="输入焊口编号" />
                  </Form.Item>
                  <Form.Item name="filmNumber" label="片号" style={{ marginBottom: 12 }}>
                    <Input placeholder="输入片号" />
                  </Form.Item>
                  <Form.Item name="filmDensity" label="底片黑度" style={{ marginBottom: 12 }}>
                    <Input placeholder="输入底片黑度" />
                  </Form.Item>
                  <Form.Item name="sensitivity" label="像质计灵敏度" style={{ marginBottom: 0 }}>
                    <Input placeholder="输入像质计灵敏度" />
                  </Form.Item>
                </Form>
              )}
            </div>

            <Divider style={{ margin: '0' }} />

            {/* 2. 缺陷信息 (卡片列表布局，带折叠功能) */}
            <div>
              {/* 修改点：
                        1. 图标放在文字前面
                        2. 增加背景色和圆角
                    */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: 12,
                  cursor: 'pointer',
                  userSelect: 'none',
                  backgroundColor: '#e6f7ff', // 与左侧选中背景色一致
                  padding: '8px 12px',
                  borderRadius: '4px'
                }}
                onClick={() => setShowDefectList(!showDefectList)}
              >
                {/* 图标在前 */}
                {showDefectList ?
                  <UpOutlined style={{ fontSize: '12px', color: '#1890ff', marginRight: 8 }} /> :
                  <DownOutlined style={{ fontSize: '12px', color: '#1890ff', marginRight: 8 }} />
                }
                <Title level={5} style={{ margin: 0, fontSize: '15px' }}>缺陷信息</Title>
              </div>

              {showDefectList && (
                <div style={{ display: 'flex', flexDirection: 'column', padding: '0 4px' }}>
                  {/* 渲染所有类型的缺陷 */}
                  {(() => {
                    let globalCount = 0;
                    return (
                      <>
                        {/* 矩形 */}
                        {defectRects.map((rect, idx) => {
                          const comp = renderDefectCard(rect, idx, 'rect', globalCount);
                          globalCount++;
                          return comp;
                        })}
                        {/* 多边形 */}
                        {defectPolygons.map((poly, idx) => {
                          const comp = renderDefectCard(poly, idx, 'polygon', globalCount);
                          globalCount++;
                          return comp;
                        })}
                        {/* 圆形 */}
                        {defectCircles.map((circle, idx) => {
                          const comp = renderDefectCard(circle, idx, 'circle', globalCount);
                          globalCount++;
                          return comp;
                        })}

                        {globalCount === 0 && (
                          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无缺陷标注" />
                        )}
                      </>
                    );
                  })()}
                </div>
              )}
            </div>


          </Space>
        </div>
      </Sider>

      {/* 4. 像素标定弹窗 */}
      <Modal
        title="像素标定"
        open={calibrateModalVisible}
        onOk={handleCalibrateConfirm}
        onCancel={() => {
          setCalibrateModalVisible(false);
          setCalibrateLine(null);
          setActiveTool('pan');
        }}
        okText="确认"
        cancelText="取消"
        width={300}
        centered
        maskClosable={false}
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">选择的距离 (像素)：</Text>
          <div style={{ fontSize: '16px', fontWeight: 'bold', marginTop: 4 }}>
            {measuredPixelDistance} px
          </div>
        </div>
        <div>
          <Text type="secondary">实际长度 (毫米)：</Text>
          <InputNumber
            style={{ width: '100%', marginTop: 4 }}
            placeholder="请输入实际长度"
            value={actualLength}
            onChange={(val) => setActualLength(val)}
            addonAfter="mm"
            autoFocus
          />
        </div>
      </Modal>

      {/* 5. 新增：缺陷类型选择弹窗 */}
      <Modal
        title="选择缺陷类型"
        open={labelModalVisible}
        onOk={handleLabelConfirm}
        onCancel={() => {
          setLabelModalVisible(false);
          setPendingShape(null);
          setSelectedLabelCode(null);
        }}
        okText="确认"
        cancelText="取消"
        width={320}
        centered
        maskClosable={false}
        destroyOnClose
      >
        {!isDefectTypesFromBackend && (
          <Alert
            message="缺陷类型加载失败，使用默认数据"
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
          />
        )}
        <div style={{ marginBottom: 16 }}>请选择当前区域的缺陷类型：</div>
        <Select
          style={{ width: '100%' }}
          placeholder="请选择"
          value={selectedLabelCode}
          onChange={setSelectedLabelCode}
          defaultOpen
          listHeight={200}
        >
          {DEFECT_TYPES.map(type => (
            <Option key={type.code} value={type.code}>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                {/* 颜色方块 */}
                <div style={{
                  width: 12,
                  height: 12,
                  background: type.color,
                  marginRight: 8,
                  borderRadius: 2
                }} />
                {type.name}
              </div>
            </Option>
          ))}
        </Select>
      </Modal>

    </Layout>
  );
};

const isSevere = (type: string) => {
  const severeKeywords = ['裂纹', '未熔合', '未焊透', 'crack', 'unfused', 'incomplete'];
  return severeKeywords.some(k => type.toLowerCase().includes(k));
};

export default ReportEditorPage;