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
  UndoOutlined,
  RedoOutlined,
  VerticalAlignBottomOutlined,
  VerticalAlignTopOutlined,
  DeleteOutlined,
  DownOutlined,
  UpOutlined,
  ReloadOutlined,
  FullscreenExitOutlined,
  RightOutlined as CollapseRightOutlined, // 为了区分普通向右箭头
} from "@ant-design/icons";
import { useRequest, useDebounceFn } from "ahooks";
import { reportAPI, defectTypeAPI, getUserId, defectRecordAPI } from "../../utils/api";

// 移除本地 Mock defectRecordAPI
// const defectRecordAPI = { ... };
import { TaskFile, Report, DefectType, DefectRecord } from "../../utils/data";
import GeometricMeasureTool from './tool/GeometricMeasureTool';
import { useWindowLevelTool } from './tool/WindowLevelTool';
import Ruler from './tool/Ruler';
import DefectMarking, { DrawingType } from './tool/DefectMarking';
import PositionAndSizeTool, { PositionSizeType } from './tool/PositionAndSizeTool';

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

// --- 焊缝位置矩形（来自 location_0.pt B路径，直接使用模型 bbox）---
interface WeldLocationRect {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  keypoints: { x: number; y: number }[];
}

// --- 椭圆工具相关接口 ---
interface EllipseShape {
  cx: number;
  cy: number;
  rx: number;
  ry: number;
  rotation: number;
}

interface EllipseDragState {
  active: boolean;
  type: 'move' | 'rotate' | 'resize-t' | 'resize-b' | 'resize-l' | 'resize-r' | null;
  startMouse: { x: number, y: number };
  startShape: EllipseShape;
  startRotationAngle?: number;
}

interface EllipseToolState {
  mode: 'idle' | 'placing' | 'editing';
  shape: EllipseShape | null;
  drag: EllipseDragState;
  isVisible: boolean;
}

// 垂直成像状态（复用 EllipseShape，但 ry 固定很小，rotation 固定为 0）
interface VerticalDragState {
  active: boolean;
  type: 'move' | 'resize-l' | 'resize-r' | null;  // 只允许左右拉伸
  startMouse: { x: number, y: number };
  startShape: EllipseShape;
}

interface VerticalToolState {
  mode: 'idle' | 'placing' | 'editing';
  shape: EllipseShape | null;  // cx, cy, rx, ry=15(固定), rotation=0(固定)
  drag: VerticalDragState;
  isVisible: boolean;
}

// --- 撤销/重做历史记录接口 ---
interface HistorySnapshot {
  rects: SavedRect[];
  polygons: SavedPolygon[];
  circles: SavedCircle[];
}

// --- 数学工具函数 ---
const HANDLE_SIZE = 8;
const ROTATE_HANDLE_OFFSET = 30;

function rotateVector(dx: number, dy: number, angle: number) {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return { x: dx * cos - dy * sin, y: dx * sin + dy * cos };
}

function getRotatedPoint(lx: number, ly: number, shape: EllipseShape) {
  const cos = Math.cos(shape.rotation);
  const sin = Math.sin(shape.rotation);
  return { x: shape.cx + (lx * cos - ly * sin), y: shape.cy + (lx * sin + ly * cos) };
}

function hitTestRect(x: number, y: number, cx: number, cy: number) {
  return x >= cx - HANDLE_SIZE && x <= cx + HANDLE_SIZE &&
    y >= cy - HANDLE_SIZE && y <= cy + HANDLE_SIZE;
}

function hitTestEllipse(x: number, y: number, shape: EllipseShape) {
  const dx = x - shape.cx;
  const dy = y - shape.cy;
  const cos = Math.cos(-shape.rotation);
  const sin = Math.sin(-shape.rotation);
  const lx = dx * cos - dy * sin;
  const ly = dx * sin + dy * cos;
  return (lx * lx) / (shape.rx * shape.rx) + (ly * ly) / (shape.ry * shape.ry) <= 1;
}

/**
 * 将矫正后坐标点反变换回原图坐标系（CSS 变换作用前的坐标系）。
 * AI 检测结果的 bbox 存储在矫正后坐标系中，需要逆变换使 CSS transform 能正确对齐。
 * @param px - 矫正后图像中的 x 坐标（像素）
 * @param py - 矫正后图像中的 y 坐标（像素）
 * @param corrW - 矫正后图像的宽度（像素）
 * @param corrH - 矫正后图像的高度（像素）
 * @param rotationDeg - 矫正旋转角度（0/90/180/270/-90）
 * @param flipH - 水平翻转系数（1 不翻转, -1 翻转）
 */
function inverseTransformPoint(
  px: number, py: number,
  corrW: number, corrH: number,
  rotationDeg: number, flipH: number
): { x: number; y: number } {
  // 归一化旋转角度到 0/90/180/270
  const r = ((rotationDeg % 360) + 360) % 360;
  // 正向变换顺序：先旋转，再水平翻转
  // 逆变换必须反序：先撤销翻转，再撤销旋转
  if (flipH === -1) {
    px = corrW - px;
  }
  let x: number, y: number;
  if (r === 0) { x = px; y = py; }
  else if (r === 90) { x = py; y = corrW - px; }
  else if (r === 180) { x = corrW - px; y = corrH - py; }
  else /* 270 */ { x = corrH - py; y = px; }
  return { x, y };
}

/**
 * 将原图坐标点正向变换到矫正后坐标系（inverseTransformPoint 的逆操作）。
 * 用于将用户手动标注的坐标（在原图坐标系中）转换为与 AI 检测结果相同的存储坐标系。
 * @param px - 原图中的 x 坐标（像素）
 * @param py - 原图中的 y 坐标（像素）
 * @param rawW - 原图宽度（像素）
 * @param rawH - 原图高度（像素）
 * @param rotationDeg - 矫正旋转角度（0/90/180/270）
 * @param flipH - 水平翻转系数（1 不翻转, -1 翻转）
 */
function forwardTransformPoint(
  px: number, py: number,
  rawW: number, rawH: number,
  rotationDeg: number, flipH: number
): { x: number; y: number } {
  const r = ((rotationDeg % 360) + 360) % 360;
  // 正向变换顺序：先旋转，再水平翻转（与 inverseTransformPoint 逆序一致）
  let x: number, y: number;
  if (r === 0) { x = px; y = py; }
  else if (r === 90) { x = rawH - py; y = px; }
  else if (r === 180) { x = rawW - px; y = rawH - py; }
  else /* 270 */ { x = py; y = rawW - px; }
  // 矫正后图像的宽度（旋转 90/270° 后宽高互换）
  const corrW = (r === 90 || r === 270) ? rawH : rawW;
  if (flipH === -1) { x = corrW - x; }
  return { x, y };
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
  const [pageSize, setPageSize] = useState(10);

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

  // --- Full Screen Ref ---
  const editorContainerRef = useRef<HTMLDivElement>(null);
  const [isFullScreen, setIsFullScreen] = useState(false);

  useEffect(() => {
    const handleFullScreenChange = () => {
      setIsFullScreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullScreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullScreenChange);
    };
  }, []);

  const toggleFullScreen = () => {
    if (!document.fullscreenElement) {
      editorContainerRef.current?.requestFullscreen().catch(err => {
        message.error(`Error attempting to enable full-screen mode: ${err.message} (${err.name})`);
      });
    } else {
      document.exitFullscreen();
    }
  };

  //  坐标原点状态管理
  const [originPoint, setOriginPoint] = useState<{ x: number, y: number } | null>(null);
  const [isSettingOrigin, setIsSettingOrigin] = useState(false);
  const [tempOrigin, setTempOrigin] = useState<{ x: number, y: number } | null>(null);

  // 标定相关状态
  const [pixelRatio, setPixelRatio] = useState<number>(1);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibrateLine, setCalibrateLine] = useState<{ x1: number, y1: number, x2: number, y2: number } | null>(null);
  const [calibrateModalVisible, setCalibrateModalVisible] = useState(false);
  const [measuredPixelDistance, setMeasuredPixelDistance] = useState(0);
  const [actualLength, setActualLength] = useState<number | null>(null);
  // 测量距离前的尺寸定标确认弹窗
  const [calibratePromptModalVisible, setCalibratePromptModalVisible] = useState(false);
  const [measureAfterCalibrate, setMeasureAfterCalibrate] = useState(false);

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

  // --- 3. 新增：位置和尺寸工具状态 ---
  const [positionSizeType, setPositionSizeType] = useState<PositionSizeType | null>(null);

  // --- 4. 椭圆工具状态 ---
  const [ellipseState, setEllipseState] = useState<EllipseToolState>({
    mode: 'idle',
    shape: null,
    drag: {
      active: false,
      type: null,
      startMouse: { x: 0, y: 0 },
      startShape: { cx: 0, cy: 0, rx: 0, ry: 0, rotation: 0 }
    },
    isVisible: false
  });

  // --- 5. 垂直成像工具状态 ---
  const [verticalState, setVerticalState] = useState<VerticalToolState>({
    mode: 'idle',
    shape: null,
    drag: {
      active: false,
      type: null,
      startMouse: { x: 0, y: 0 },
      startShape: { cx: 0, cy: 0, rx: 0, ry: 0, rotation: 0 }
    },
    isVisible: false
  });

  // --- 6. 定位标记成像状态（复用设置坐标原点的状态，共享同一个原点数据） ---
  const [isSettingPositioning, setIsSettingPositioning] = useState(false);

  // --- 7. 焊缝位置矩形（来自 location_0.pt B路径检测结果，每张图片加载时解析） ---
  // 每个元素: { x1, y1, x2, y2, keypoints } (像素坐标, 矫正后坐标系)
  const [weldLocationShapes, setWeldLocationShapes] = useState<WeldLocationRect[]>([]);

  // --- 8. 缺陷位置检测2原点（来自 location_1.pt D路径，仅 center_mark 十字架原点） ---
  const [defectOriginPoint, setDefectOriginPoint] = useState<{ x: number; y: number } | null>(null);

  // --- 9. 是否显示定位坐标（焊缝位置矩形 + 缺陷位置检测2原点） ---
  const [showPositioningCoords, setShowPositioningCoords] = useState(true);

  // 暂存刚画完但未分类的形状数据
  const [pendingShape, setPendingShape] = useState<any>(null);
  const [pendingShapeType, setPendingShapeType] = useState<DrawingType>('rect');

  // --- 新增：折叠状态 ---
  const [showDefectList, setShowDefectList] = useState(true);
  const [showFilmInfo, setShowFilmInfo] = useState(true); // 底片信息折叠状态

  // --- 新增：每个缺陷项的展开状态 ---
  const [expandedDefects, setExpandedDefects] = useState<Set<string>>(new Set());

  // --- 新增：鼠标悬停的高亮缺陷 Key ---
  const [hoveredDefectKey, setHoveredDefectKey] = useState<string | null>(null);

  // --- 标记是否为初始加载（防止自动保存时触发） ---
  const isInitialLoadRef = useRef(true);

  // --- 原始数据引用 (用于不可用的Reset状态判断) ---
  const originalFilmInfoRef = useRef<any>({});
  const originalDefectsRef = useRef<HistorySnapshot>({
    rects: [], polygons: [], circles: []
  });

  // --- 历史记录状态 ---
  const [history, setHistory] = useState<HistorySnapshot[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  // 一个引用来避免闭包陷阱（在某些回调中）
  const historyRef = useRef<HistorySnapshot[]>([]);
  const historyIndexRef = useRef(-1);

  const updateHistoryState = (newHistory: HistorySnapshot[], newIndex: number) => {
    setHistory(newHistory);
    setHistoryIndex(newIndex);
    historyRef.current = newHistory;
    historyIndexRef.current = newIndex;
  };

  // --- 统一更新缺陷状态并记录历史 ---
  const updateAllDefects = (
    newRects: SavedRect[],
    newPolys: SavedPolygon[],
    newCircles: SavedCircle[],
    recordHistory: boolean = true
  ) => {
    // 1. 更新 React 状态 (渲染用)
    setDefectRects(newRects);
    setDefectPolygons(newPolys);
    setDefectCircles(newCircles);

    if (recordHistory) {
      // 2. 截断未来分支 (如果当前不在最新)
      const currentHistory = historyRef.current.slice(0, historyIndexRef.current + 1);

      // 3. 构造新快照
      const snapshot: HistorySnapshot = {
        rects: JSON.parse(JSON.stringify(newRects)),
        polygons: JSON.parse(JSON.stringify(newPolys)),
        circles: JSON.parse(JSON.stringify(newCircles))
      };

      // 4. 入栈
      const nextHistory = [...currentHistory, snapshot];

      // 5. 限制历史长度（如50步）
      if (nextHistory.length > 50) nextHistory.shift();

      updateHistoryState(nextHistory, nextHistory.length - 1);
    }
  };

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
    // 当切换到位置和尺寸工具时，重置子类型为 null（默认不选中任何选项）
    if (activeTool === 'positionSize') {
      setPositionSizeType(null);
    }
  }, [activeTool]);

  // --- 椭圆工具初始化/重置 ---
  useEffect(() => {
    if (activeTool === 'positionSize' && positionSizeType === 'elliptical') {
      setEllipseState({
        mode: 'placing',
        shape: { cx: 0, cy: 0, rx: 120, ry: 60, rotation: 0 },
        drag: {
          active: false,
          type: null,
          startMouse: { x: 0, y: 0 },
          startShape: { cx: 0, cy: 0, rx: 0, ry: 0, rotation: 0 }
        },
        isVisible: true
      });
      message.info("请移动鼠标选择位置，点击左键固定");
    } else {
      // 如果切出椭圆工具，重置状态
      setEllipseState(prev => ({ ...prev, mode: 'idle', isVisible: false }));
    }
  }, [activeTool, positionSizeType]);

  // --- 垂直成像工具初始化/重置 ---
  useEffect(() => {
    if (activeTool === 'positionSize' && positionSizeType === 'vertical') {
      setVerticalState({
        mode: 'placing',
        shape: { cx: 0, cy: 0, rx: 180, ry: 15, rotation: 0 },  // ry 固定为 15，非常扁平
        drag: {
          active: false,
          type: null,
          startMouse: { x: 0, y: 0 },
          startShape: { cx: 0, cy: 0, rx: 0, ry: 0, rotation: 0 }
        },
        isVisible: true
      });
      message.info("垂直成像：请移动鼠标选择位置，点击左键固定");
    } else {
      // 如果切出垂直工具，重置状态
      setVerticalState(prev => ({ ...prev, mode: 'idle', isVisible: false }));
    }
  }, [activeTool, positionSizeType]);

  // --- 定位标记成像工具初始化/重置 ---
  useEffect(() => {
    if (activeTool === 'positionSize' && positionSizeType === 'positioning') {
      setIsSettingPositioning(false);
      setTempOrigin(null);
      message.info("定位标记成像：点击图片设置坐标原点");
    } else {
      // 如果切出定位标记工具，重置状态
      setIsSettingPositioning(false);
      if (activeTool !== 'setOrigin') {
        // 只有在不是设置原点工具时才清除 tempOrigin
        // setTempOrigin(null); // 这里不需要清除，让 setOrigin 的 useEffect 处理
      }
    }
  }, [activeTool, positionSizeType]);

  // --- 切换图片时清除椭圆、垂直成像和定位标记成像状态 ---
  useEffect(() => {
    // 当图片切换时，重置椭圆和垂直成像的状态
    setEllipseState({
      mode: 'idle',
      shape: null,
      drag: {
        active: false,
        type: null,
        startMouse: { x: 0, y: 0 },
        startShape: { cx: 0, cy: 0, rx: 0, ry: 0, rotation: 0 }
      },
      isVisible: false
    });
    setVerticalState({
      mode: 'idle',
      shape: null,
      drag: {
        active: false,
        type: null,
        startMouse: { x: 0, y: 0 },
        startShape: { cx: 0, cy: 0, rx: 0, ry: 0, rotation: 0 }
      },
      isVisible: false
    });
    // 重置定位标记成像状态（复用 originPoint 和 tempOrigin，不需要单独清除）
    setIsSettingPositioning(false);
    // 重置焊缝位置形状（新文件加载时重新解析）
    setWeldLocationShapes([]);
    // 重置缺陷位置检测2原点
    setDefectOriginPoint(null);
  }, [selectedFile]);

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
    imageReady, // 从 hook 获取图片渲染完成状态
    resetImageReady, // 重置图片就绪状态的方法
    imageWidth: rawImageWidth, // 获取同步的图片宽度
    imageHeight: rawImageHeight, // 获取同步的图片高度
  } = useWindowLevelTool({
    activeTool,
    scale,
    imageFile: imageFile,
    rotation,
    flipH,
    flipV,
  });

  // 防止切换文件瞬间闪烁：强制标记状态重置 Ref
  // 该 Ref 在切换文件时立即设为 true，只有当 imageReady 真正变回 false 后才设为 false
  const isImageResetingRef = useRef(false);

  // 旋转图片自动适配：记录已完成自动缩放的文件ID，避免重复触发
  const autoFitFileIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!imageReady) {
      isImageResetingRef.current = false;
    }
  }, [imageReady]);

  useEffect(() => {
    if (!selectedFile || !previewUrl) {
      setImageFile(undefined);
      return;
    }
    // 开始加载新图片时，先清空旧图片，确保WindowLevelTool清除状态
    setImageFile(undefined);

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

  // 旋转图片自动适配：当 90°/270° 旋转图片加载完成后，计算并设置初始缩放比例
  // 使旋转后的视觉宽高能适应容器，避免出现图片过小或溢出的问题
  useEffect(() => {
    if (!imageReady || rawImageWidth === 0 || rawImageHeight === 0 || containerSize.w === 0 || containerSize.h === 0) return;
    if (autoFitFileIdRef.current === selectedFile?.TaskFileId) return; // 当前文件已完成自动适配
    autoFitFileIdRef.current = selectedFile?.TaskFileId ?? null;

    const normR = ((rotation % 360) + 360) % 360;
    if (normR !== 90 && normR !== 270) return;

    // CSS 在 scale=1 时将画布约束在容器内的缩放系数
    const W = rawImageWidth, H = rawImageHeight;
    const cW = containerSize.w, cH = containerSize.h;
    const cssScale = Math.min(1, cW / W, cH / H);
    // 旋转 90° 后：视觉宽 = H*cssScale*s，视觉高 = W*cssScale*s
    // 令视觉尺寸适应容器：s = min(cW/(H*cssScale), cH/(W*cssScale))
    const autoScale = Math.min(cW / (H * cssScale), cH / (W * cssScale));
    setScale(parseFloat(autoScale.toFixed(2)));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageReady, rawImageWidth, rawImageHeight, containerSize.w, containerSize.h]);

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
  } else if (activeTool === 'positionSize' && positionSizeType === 'positioning') {
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
    const vx = e.clientX - centerX;
    const vy = e.clientY - centerY;
    // 正确的逆变换顺序：先撤销 scale·flip，再撤销 rotation
    // CSS transform: scale(sx,sy)·rotate(r)，逆变换反序：rotate^-1 · scale^-1
    const ux = vx * flipH / scale;
    const uy = vy * flipV / scale;
    const rad = -rotation * (Math.PI / 180);
    const localX = ux * Math.cos(rad) - uy * Math.sin(rad);
    const localY = ux * Math.sin(rad) + uy * Math.cos(rad);
    return {
      x: localX + imgSize.w / 2,
      y: localY + imgSize.h / 2
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

  // 反向转换：从真实坐标转换回图像坐标（用于SVG绘制）
  const calculateImageCoordinates = (trueX: number, trueY: number) => {
    const ratioX = (originalSize.w > 0 && imgSize.w > 0) ? originalSize.w / imgSize.w : 1;
    const ratioY = (originalSize.h > 0 && imgSize.h > 0) ? originalSize.h / imgSize.h : 1;
    return {
      x: trueX / ratioX,
      y: trueY / ratioY
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
    else if (activeTool === 'positionSize' && positionSizeType === 'elliptical') {
      e.stopPropagation();
      e.preventDefault();
      const { x, y } = getImageCoordinates(e);

      // 1. 放置模式：点击确认放置
      if (ellipseState.mode === 'placing') {
        const newShape = { ...ellipseState.shape!, cx: x, cy: y };
        setEllipseState({
          ...ellipseState,
          mode: 'editing',
          shape: newShape
        });
        message.success("已固定。可拖拽调整或重新放置");
        return;
      }

      // 2. 编辑模式：命中检测
      if (ellipseState.mode === 'editing' && ellipseState.shape) {
        const s = ellipseState.shape;
        // 计算四个关键点
        const pRight = getRotatedPoint(s.rx, 0, s);
        const pLeft = getRotatedPoint(-s.rx, 0, s);
        const pBottom = getRotatedPoint(0, s.ry, s);
        const pTop = getRotatedPoint(0, -s.ry, s);
        const pRotate = getRotatedPoint(0, -s.ry - ROTATE_HANDLE_OFFSET, s);

        let action: EllipseDragState['type'] = null;
        if (Math.hypot(x - pRotate.x, y - pRotate.y) < HANDLE_SIZE + 4) action = 'rotate';
        else if (hitTestRect(x, y, pRight.x, pRight.y)) action = 'resize-r';
        else if (hitTestRect(x, y, pLeft.x, pLeft.y)) action = 'resize-l';
        else if (hitTestRect(x, y, pBottom.x, pBottom.y)) action = 'resize-b';
        else if (hitTestRect(x, y, pTop.x, pTop.y)) action = 'resize-t';
        else if (hitTestEllipse(x, y, s)) action = 'move';

        if (action) {
          setEllipseState(prev => ({
            ...prev,
            drag: {
              active: true,
              type: action,
              startMouse: { x, y },
              startShape: { ...s },
              startRotationAngle: action === 'rotate' ? Math.atan2(y - s.cy, x - s.cx) : undefined
            }
          }));
        }
      }
    }
    else if (activeTool === 'positionSize' && positionSizeType === 'vertical') {
      e.stopPropagation();
      e.preventDefault();
      const { x, y } = getImageCoordinates(e);

      // 1. 放置模式：点击确认放置
      if (verticalState.mode === 'placing') {
        const newShape = { ...verticalState.shape!, cx: x, cy: y };
        setVerticalState({
          ...verticalState,
          mode: 'editing',
          shape: newShape
        });
        message.success("垂直成像已固定。可拖拽平移或左右拉伸");
        return;
      }

      // 2. 编辑模式：命中检测（只检测左右手柄和椭圆内部）
      if (verticalState.mode === 'editing' && verticalState.shape) {
        const s = verticalState.shape;
        // 垂直成像：只有左右两个手柄（9' 和 3'）
        const pLeft = { x: s.cx - s.rx, y: s.cy };   // 9' 位置（最左）
        const pRight = { x: s.cx + s.rx, y: s.cy };  // 3' 位置（最右）

        let action: VerticalDragState['type'] = null;
        if (hitTestRect(x, y, pLeft.x, pLeft.y)) action = 'resize-l';
        else if (hitTestRect(x, y, pRight.x, pRight.y)) action = 'resize-r';
        else if (hitTestEllipse(x, y, s)) action = 'move';

        if (action) {
          setVerticalState(prev => ({
            ...prev,
            drag: {
              active: true,
              type: action,
              startMouse: { x, y },
              startShape: { ...s }
            }
          }));
        }
      }
    }
    else if (activeTool === 'positionSize' && positionSizeType === 'positioning') {
      e.stopPropagation();
      e.preventDefault();
      const { x, y } = getImageCoordinates(e);
      setIsSettingPositioning(true);
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
    else if (activeTool === 'positionSize' && positionSizeType === 'elliptical') {
      const { x, y } = getImageCoordinates(e);
      if (ellipseState.mode === 'placing' && ellipseState.shape) {
        // 放置中：跟随鼠标
        setEllipseState(prev => ({
          ...prev,
          shape: { ...prev.shape!, cx: x, cy: y }
        }));
      }
      else if (ellipseState.mode === 'editing' && ellipseState.drag.active && ellipseState.shape) {
        // 编辑中：拖拽处理
        const drag = ellipseState.drag;
        const dx = x - drag.startMouse.x;
        const dy = y - drag.startMouse.y;
        const s = ellipseState.shape;
        const startS = drag.startShape;

        let newShape = { ...s };

        if (drag.type === 'move') {
          newShape.cx = startS.cx + dx;
          newShape.cy = startS.cy + dy;
        } else if (drag.type === 'rotate') {
          const currentAngle = Math.atan2(y - s.cy, x - s.cx);
          const angleDiff = currentAngle - (drag.startRotationAngle || 0);
          // 保持 rotation 为弧度，与数学辅助函数（rotateVector, getRotatedPoint）
          // 和 SVG 渲染（rotate(rotation * 180 / Math.PI)）保持一致
          newShape.rotation = startS.rotation + angleDiff;
        } else {
          // 缩放逻辑：将世界坐标系中的鼠标增量转换到椭圆本地坐标系
          // 通过反向旋转 -startS.rotation，使增量与椭圆坐标轴对齐
          const localDelta = rotateVector(dx, dy, -startS.rotation);
          // 右侧/底部手柄：正向增加对应轴的半径
          // 左侧/顶部手柄：反向减少对应轴的半径（因为拖拽方向相反）
          if (drag.type === 'resize-r') newShape.rx = Math.max(10, startS.rx + localDelta.x);
          else if (drag.type === 'resize-l') newShape.rx = Math.max(10, startS.rx - localDelta.x);
          else if (drag.type === 'resize-b') newShape.ry = Math.max(10, startS.ry + localDelta.y);
          else if (drag.type === 'resize-t') newShape.ry = Math.max(10, startS.ry - localDelta.y);
        }
        setEllipseState(prev => ({ ...prev, shape: newShape }));
      }
    }
    else if (activeTool === 'positionSize' && positionSizeType === 'vertical') {
      const { x, y } = getImageCoordinates(e);
      if (verticalState.mode === 'placing' && verticalState.shape) {
        // 放置中：跟随鼠标
        setVerticalState(prev => ({
          ...prev,
          shape: { ...prev.shape!, cx: x, cy: y }
        }));
      }
      else if (verticalState.mode === 'editing' && verticalState.drag.active && verticalState.shape) {
        // 编辑中：拖拽处理
        const drag = verticalState.drag;
        const dx = x - drag.startMouse.x;
        const dy = y - drag.startMouse.y;
        const s = verticalState.shape;
        const startS = drag.startShape;

        let newShape = { ...s };

        if (drag.type === 'move') {
          // 平移：直接移动中心点
          newShape.cx = startS.cx + dx;
          newShape.cy = startS.cy + dy;
        } else {
          // 左右拉伸：只改变 rx，ry 固定为 15，rotation 固定为 0
          if (drag.type === 'resize-r') newShape.rx = Math.max(30, startS.rx + dx);  // 右侧拉伸
          else if (drag.type === 'resize-l') newShape.rx = Math.max(30, startS.rx - dx);  // 左侧拉伸
          // 保持 ry 和 rotation 不变
          newShape.ry = 15;
          newShape.rotation = 0;
        }
        setVerticalState(prev => ({ ...prev, shape: newShape }));
      }
    }
    else if (activeTool === 'positionSize' && positionSizeType === 'positioning' && isSettingPositioning) {
      const { x, y } = getImageCoordinates(e);
      setTempOrigin({ x, y });
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
    else if (activeTool === 'positionSize' && positionSizeType === 'elliptical') {
      if (ellipseState.drag.active) {
        setEllipseState(prev => ({
          ...prev,
          drag: { ...prev.drag, active: false }
        }));
      }
    }
    else if (activeTool === 'positionSize' && positionSizeType === 'vertical') {
      if (verticalState.drag.active) {
        setVerticalState(prev => ({
          ...prev,
          drag: { ...prev.drag, active: false }
        }));
      }
    }
    else if (activeTool === 'positionSize' && positionSizeType === 'positioning' && isSettingPositioning && tempOrigin) {
      setIsSettingPositioning(false);
      const trueCoords = calculateTrueCoordinates(tempOrigin.x, tempOrigin.y);
      setOriginPoint(trueCoords);
      message.success(`定位标记已设置（坐标原点）: (${trueCoords.x}, ${trueCoords.y})`);
      setTempOrigin(null);
      // 不切换工具，允许用户继续调整定位标记
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
        setMeasuredPixelDistance(Math.round(dist)); // 四舍五入为整数
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
    if (activeTool === 'positionSize' && positionSizeType === 'positioning') setIsSettingPositioning(false);
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
      // 如果是从测量距离触发的标定，标定完成后进入测量模式
      if (measureAfterCalibrate) {
        setActiveTool('measure');
        setMeasureAfterCalibrate(false);
      } else {
        setActiveTool('pan');
      }
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

    // 用户标注坐标来自 getImageCoordinates()，在原图（Canvas 本地）坐标系中。
    // 存储需与 AI 检测结果保持一致，即矫正后坐标系（CorrectionRotation/Flip 已应用）。
    // 当存在矫正变换时，需将原图坐标正向变换到矫正后坐标系。
    const corrRotation = selectedFile?.CorrectionRotation ?? 0;
    const corrFlipH = selectedFile?.CorrectionFlip ? -1 : 1;
    const needsFwdTransform = corrRotation !== 0 || corrFlipH === -1;

    if (pendingShapeType === 'rect') {
      // 先转换到原图像素坐标，再正向变换到矫正后坐标系
      let rx1 = pendingShape.x * widthRatio;
      let ry1 = pendingShape.y * heightRatio;
      let rx2 = (pendingShape.x + pendingShape.w) * widthRatio;
      let ry2 = (pendingShape.y + pendingShape.h) * heightRatio;

      if (needsFwdTransform) {
        const p1 = forwardTransformPoint(rx1, ry1, trueImageW, trueImageH, corrRotation, corrFlipH);
        const p2 = forwardTransformPoint(rx2, ry2, trueImageW, trueImageH, corrRotation, corrFlipH);
        rx1 = Math.min(p1.x, p2.x); ry1 = Math.min(p1.y, p2.y);
        rx2 = Math.max(p1.x, p2.x); ry2 = Math.max(p1.y, p2.y);
      }

      const newRect: SavedRect = {
        ...pendingShape,
        x: rx1, y: ry1, w: rx2 - rx1, h: ry2 - ry1,
        label, color, ...defaultExtra, size: ''
      };
      updateAllDefects([...defectRects, newRect], defectPolygons, defectCircles, true);
    } else if (pendingShapeType === 'polygon') {
      const newPoints = pendingShape.points.map((p: { x: number; y: number }) => {
        const rawX = p.x * widthRatio;
        const rawY = p.y * heightRatio;
        if (needsFwdTransform) {
          return forwardTransformPoint(rawX, rawY, trueImageW, trueImageH, corrRotation, corrFlipH);
        }
        return { x: rawX, y: rawY };
      });
      const newPoly: SavedPolygon = {
        points: newPoints,
        label, color, ...defaultExtra
      };
      updateAllDefects(defectRects, [...defectPolygons, newPoly], defectCircles, true);
    } else if (pendingShapeType === 'circle') {
      let cx = pendingShape.x * widthRatio;
      let cy = pendingShape.y * heightRatio;
      if (needsFwdTransform) {
        ({ x: cx, y: cy } = forwardTransformPoint(cx, cy, trueImageW, trueImageH, corrRotation, corrFlipH));
      }
      const newCircle: SavedCircle = {
        ...pendingShape,
        x: cx, y: cy,
        r: pendingShape.r * widthRatio,
        label, color, ...defaultExtra
      };
      updateAllDefects(defectRects, defectPolygons, [...defectCircles, newCircle], true);
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
  }, [files, currentPage, pageSize]);

  useEffect(() => {
    if (files.length > 0 && !selectedFile) {
      setSelectedFile(files[0]);
    }
  }, [files]);

  // 使用 useRef 保存之前的 TaskFileId，避免重复加载
  const prevTaskFileIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (selectedFile && selectedFile.TaskFileId !== prevTaskFileIdRef.current) {
      // 切换瞬间，如果当前图片是就绪的（说明是旧图），则标记为重置中，防止闪烁
      // 如果当前图片本身就不就绪（如首屏加载），则不需要锁，否则会导致死锁（因为解锁逻辑依赖 imageReady 变 false 的动作）
      if (imageReady) {
        isImageResetingRef.current = true;
      }

      // 记录当前处理的文件ID
      prevTaskFileIdRef.current = selectedFile.TaskFileId;

      // 从后端加载底片信息字段
      // 从后端加载底片信息字段
      const initialFilmInfo = {
        weldId: selectedFile.WeldId || '',
        filmNumber: selectedFile.FilmNumber || '',
        filmDensity: selectedFile.FilmDensity || '',
        sensitivity: selectedFile.Sensitivity || '',
      };
      filmInfoForm.setFieldsValue(initialFilmInfo);
      originalFilmInfoRef.current = initialFilmInfo;

      // 立即清空缺陷列表，防止在加载新数据前显示旧数据或发生时序闪烁
      setDefectRects([]);
      setDefectCircles([]);
      setDefectPolygons([]);

      // 切换图片时，如果当前是测量距离工具，则重置为平移工具
      if (activeTool === 'measure') {
        setActiveTool('pan');
      }

      // 从后端加载缺陷记录
      defectRecordAPI.getByTaskFileId(selectedFile.TaskFileId).then(resp => {
        if (resp.Data && resp.Data.length > 0) {
          // 将后端 DefectRecord 转换为前端格式，根据几何类型分类
          const loadedRects: SavedRect[] = [];
          const loadedCircles: SavedCircle[] = [];
          const loadedPolygons: SavedPolygon[] = [];

          resp.Data.forEach((dr: DefectRecord) => {
            // 从 Geometry 字段解析几何坐标（保持原始坐标，即矫正后坐标系）
            let geometry: any = null;
            try {
              geometry = dr.Geometry ? JSON.parse(dr.Geometry) : null;
            } catch (e) {
              console.warn('Failed to parse defect geometry:', dr.Geometry);
            }

            const baseInfo = {
              label: dr.DefectName || '未知',
              color: DEFECT_TYPES.find(d => d.name === dr.DefectName)?.color || '#f5222d',
              position: dr.Position || '',
              size: dr.Size || '',
              quality: dr.Grade || '',
              remark: dr.Remark || '',
              defectRecordId: dr.DefectRecordId,
              // 标记该坐标来自 AI（矫正后坐标系），渲染时需逆变换
              _isCorrectedCoord: true,
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

          // 初始化原始数据Ref
          const initialSnapshot = {
            rects: JSON.parse(JSON.stringify(loadedRects)),
            polygons: JSON.parse(JSON.stringify(loadedPolygons)),
            circles: JSON.parse(JSON.stringify(loadedCircles))
          };
          originalDefectsRef.current = initialSnapshot;

          // 初始化历史记录：放入初始状态
          updateHistoryState([initialSnapshot], 0);
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

      // 解析焊缝位置检测结果（B路径，来自 location_0.pt，12个关键点拟合椭圆）
      const parseWeldLocationShapes = (): WeldLocationRect[] => {
        if (!selectedFile?.WeldLocation) return [];
        try {
          const detections: Array<{
            class: string;
            bbox: number[];
            keypoints: Array<{ id: number; x: number; y: number }>;
          }> = JSON.parse(selectedFile.WeldLocation);
          if (!Array.isArray(detections) || detections.length === 0) return [];

          return detections.map(det => {
            const [x1, y1, x2, y2] = det.bbox;
            const kps = (det.keypoints || [])
              .filter(k => k.x > 1 && k.y > 1)
              .map(k => ({ x: k.x, y: k.y }));
            return { x1, y1, x2, y2, keypoints: kps };
          });
        } catch (e) {
          console.warn('Failed to parse WeldLocation:', e);
          return [];
        }
      };
      setWeldLocationShapes(parseWeldLocationShapes());

      // 解析缺陷位置检测2结果（D路径，来自 location_1.pt，仅 center_mark 十字架原点）
      const parseDefectOrigin = (): { x: number; y: number } | null => {
        if (!selectedFile?.DefectPosition) return null;
        try {
          const dp = JSON.parse(selectedFile.DefectPosition);
          if (typeof dp.origin_x === 'number' && typeof dp.origin_y === 'number') {
            return { x: dp.origin_x, y: dp.origin_y };
          }
        } catch (e) {
          console.warn('Failed to parse DefectPosition:', e);
        }
        return null;
      };
      setDefectOriginPoint(parseDefectOrigin());

      // 立即重置图片就绪状态，确保缺陷信息隐藏，直到新图片渲染完成
      resetImageReady();

      autoFitFileIdRef.current = null; // 重置，允许新图片触发自动适配
      resetWindow();
      setScale(1);
      // 使用矫正信息初始化旋转/翻转，让图片以正确方向显示
      setRotation(selectedFile.CorrectionRotation ?? 0);
      setFlipH(selectedFile.CorrectionFlip ? -1 : 1);
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
          PlateQuality: '',
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

  // 使用 Hook 返回的同步尺寸计算比例，避免 useEffect 更新 originalSize 带来的渲染延迟（闪烁根本原因）
  const trueImageW = rawImageWidth > 0 ? rawImageWidth : originalSize.w;
  const trueImageH = rawImageHeight > 0 ? rawImageHeight : originalSize.h;

  const widthRatio = (trueImageW > 0 && imgSize.w > 0) ? (trueImageW / imgSize.w) : 1;
  const heightRatio = (trueImageH > 0 && imgSize.h > 0) ? (trueImageH / imgSize.h) : 1;

  // 旋转90°/270°后，水平轴对应原图高度、垂直轴对应原图宽度，标尺需交换 ratio 和 maxImageSize
  const corrNormR = ((rotation % 360) + 360) % 360;
  const isAxesSwapped = corrNormR === 90 || corrNormR === 270;
  const rulerHorizRatio = isAxesSwapped ? heightRatio : widthRatio;
  const rulerVertRatio = isAxesSwapped ? widthRatio : heightRatio;
  const rulerHorizMax = isAxesSwapped ? trueImageH : trueImageW;
  const rulerVertMax = isAxesSwapped ? trueImageW : trueImageH;

  const displayOrigin = useMemo(() => {
    // 如果是设置原点工具或定位标记成像工具，且有临时原点，显示临时坐标
    if ((activeTool === 'setOrigin' || (activeTool === 'positionSize' && positionSizeType === 'positioning')) && tempOrigin) {
      return calculateTrueCoordinates(tempOrigin.x, tempOrigin.y);
    }
    return originPoint || { x: 0, y: 0 };
  }, [activeTool, positionSizeType, tempOrigin, originPoint, originalSize, imgSize]);

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
      (newArr[index] as any)[field] = value;
      // 调用统一更新函数（包含历史记录）
      updateAllDefects(newArr, defectPolygons, defectCircles, true);
    } else if (type === 'polygon') {
      const newArr = [...defectPolygons];
      if (field === 'label') {
        const match = DEFECT_TYPES.find(d => d.name === value);
        if (match) newArr[index].color = match.color;
      }
      (newArr[index] as any)[field] = value;
      // 调用统一更新函数
      updateAllDefects(defectRects, newArr, defectCircles, true);
    } else if (type === 'circle') {
      const newArr = [...defectCircles];
      if (field === 'label') {
        const match = DEFECT_TYPES.find(d => d.name === value);
        if (match) newArr[index].color = match.color;
      }
      (newArr[index] as any)[field] = value;
      // 调用统一更新函数
      updateAllDefects(defectRects, defectPolygons, newArr, true);
    }
    // 触发自动保存 (updateAllDefects 改变了 state, useEffect 会监听到并触发)
  };

  const deleteDefect = (type: 'rect' | 'polygon' | 'circle', index: number) => {
    if (type === 'rect') {
      const newArr = [...defectRects];
      newArr.splice(index, 1);
      updateAllDefects(newArr, defectPolygons, defectCircles, true);
    } else if (type === 'polygon') {
      const newArr = [...defectPolygons];
      newArr.splice(index, 1);
      updateAllDefects(defectRects, newArr, defectCircles, true);
    } else if (type === 'circle') {
      const newArr = [...defectCircles];
      newArr.splice(index, 1);
      updateAllDefects(defectRects, defectPolygons, newArr, true);
    }
  };

  // --- 重置功能 ---
  const handleResetFilmInfo = () => {
    if (!selectedFile) return;
    filmInfoForm.setFieldsValue(originalFilmInfoRef.current);
    message.success("底片信息已重置");
    // 触发自动保存以同步后端
    autoSaveFilmInfo();
  };

  // --- 撤销/重做/重置 功能 ---

  const handleUndo = () => {
    if (historyIndexRef.current > 0) {
      const prevIndex = historyIndexRef.current - 1;
      const snapshot = historyRef.current[prevIndex];
      // 恢复快照，但不记录历史（recordHistory=false）
      updateAllDefects(snapshot.rects, snapshot.polygons, snapshot.circles, false);
      // 单独更新索引
      setHistoryIndex(prevIndex);
      historyIndexRef.current = prevIndex;
      message.success("已撤销");
    }
  };

  const handleRedo = () => {
    if (historyIndexRef.current < historyRef.current.length - 1) {
      const nextIndex = historyIndexRef.current + 1;
      const snapshot = historyRef.current[nextIndex];
      // 恢复快照，不记录历史
      updateAllDefects(snapshot.rects, snapshot.polygons, snapshot.circles, false);
      setHistoryIndex(nextIndex);
      historyIndexRef.current = nextIndex;
      message.success("已重做");
    }
  };

  const handleResetDefects = () => {
    if (!selectedFile) return;
    // 重置也是一种操作，应该被记录进历史，这样用户可以"撤销重置"
    // 获取原始数据
    const original = originalDefectsRef.current;

    // 使用统一更新函数，recordHistory=true，这样会把原始状态作为新的一步压入栈
    updateAllDefects(
      JSON.parse(JSON.stringify(original.rects)),
      JSON.parse(JSON.stringify(original.polygons)),
      JSON.parse(JSON.stringify(original.circles)),
      true
    );
    message.success("缺陷信息已恢复初始状态");
  };

  // 计算重置按钮是否可用：如果当前状态与原始状态完全一致（深比较），则不可用
  const isResetDisabled = useMemo(() => {
    // 简单比较 JSON 字符串
    // 注意：顺序可能会影响，但在严格控制下一般没问题。更严谨可以用 lodash.isEqual
    // 这里为了性能和简单，假设顺序一致性。由于我们总是整体替换，顺序应该是一致的。
    if (!selectedFile) return true;
    const current = { rects: defectRects, polygons: defectPolygons, circles: defectCircles };
    // 忽略 undefined 差异（JSON.stringify 会把 undefined 字段去掉）
    return JSON.stringify(current) === JSON.stringify(originalDefectsRef.current);
  }, [defectRects, defectPolygons, defectCircles, selectedFile]);

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
      <div
        key={defectKey}
        onMouseEnter={() => setHoveredDefectKey(defectKey)}
        onMouseLeave={() => setHoveredDefectKey(null)}
        style={{
          background: globalIndex % 2 === 0 ? '#f6ffed' : '#fffbe6',
          border: `1px solid ${item.color || '#f0f0f0'}`,
          borderLeft: `5px solid ${item.color || '#f0f0f0'}`,
          borderRadius: '4px',
          marginBottom: '8px',
          padding: isExpanded ? '12px' : '8px 12px',
          transition: 'all 0.2s',
          boxShadow: hoveredDefectKey === defectKey ? '0 4px 12px rgba(0,0,0,0.15)' : 'none',
          transform: hoveredDefectKey === defectKey ? 'translateY(-2px)' : 'none'
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
      <Sider width={280} theme="light" style={{ borderRight: "1px solid #f0f0f0", overflow: 'hidden' }}>
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
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

        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
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
        </div>
      </Sider>

      {/* 中间编辑区 */}
      <Content
        ref={editorContainerRef}
        style={{ display: "flex", flexDirection: "column", background: '#f0f2f5', height: '100%', overflow: 'hidden' }}
      >
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

            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="重置视图">
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
            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="窗宽调整">
              <Button type="text" ghost
                icon={<img src="/contrast.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />}
                onClick={() => setActiveTool(activeTool === 'windowing' ? 'pan' : 'windowing')}
                style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: activeTool === 'windowing' ? '#1890ff' : 'transparent' }}
              />
            </Tooltip>
            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="负片">
              <Button
                type={isNegative ? 'primary' : 'text'}
                ghost={!isNegative}
                onClick={() => setIsNegative(!isNegative)}
                icon={<img src="/negative.svg" alt="negative" style={{ width: 16, height: 16, filter: 'invert(1)' }} />}
                style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: isNegative ? '#1890ff' : 'transparent' }} /></Tooltip>
            <Divider type="vertical" style={{ background: '#434343', margin: '0 8px', height: 20 }} />

            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="缺陷标记">
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

            {/* <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="数字识别"><Button type="text" ghost icon={<img src="/type.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} /></Tooltip> */}
            <Divider type="vertical" style={{ background: '#434343', margin: '0 8px', height: 20 }} />

            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="设置坐标原点">
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

            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="测量距离">
              <Button
                type={activeTool === 'measure' ? 'primary' : 'text'}
                ghost={activeTool !== 'measure'} icon={<img src="/ruler.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />}
                onClick={() => {
                  if (activeTool === 'measure') {
                    setActiveTool('pan');
                  } else {
                    // 弹出确认框询问是否需要尺寸定标
                    setCalibratePromptModalVisible(true);
                  }
                }}
                style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: activeTool === 'measure' ? '#1890ff' : 'transparent' }} /></Tooltip>


            <Divider type="vertical" style={{ background: '#434343', margin: '0 8px', height: 20 }} />

            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="左旋90°"><Button type="text" ghost icon={<img src="/rotate-ccw.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setRotation(r => r - 90)} /></Tooltip>
            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="右转90°"><Button type="text" ghost icon={<img src="/rotate-cw.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setRotation(r => r + 90)} /></Tooltip>
            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="旋转180°"><Button type="text" ghost icon={<img src="/refresh-ccw.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setRotation(r => r + 180)} /></Tooltip>
            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="水平翻转"><Button type="text" ghost icon={<img src="/flip-horizontal-2.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setFlipV(v => v * -1)} /></Tooltip>
            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="垂直翻转"><Button type="text" ghost icon={<img src="/flip-vertical-2.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />} style={{ color: '#fff', width: 36, height: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setFlipH(h => h * -1)} /></Tooltip>

            <Divider type="vertical" style={{ background: '#434343', margin: '0 8px', height: 20 }} />
            <Tooltip getPopupContainer={() => editorContainerRef.current || document.body} title="位置和尺寸">
              <Button
                type={activeTool === 'positionSize' ? 'primary' : 'text'}
                ghost={activeTool !== 'positionSize'}
                icon={<img src="/codepen.svg" alt="alert" style={{ width: 16, height: 16, filter: 'invert(1)' }} />}
                style={{
                  color: '#fff', width: 36, height: 32, padding: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: activeTool === 'positionSize' ? '#1890ff' : 'transparent'
                }}
                onClick={() => {
                  setActiveTool(activeTool === 'positionSize' ? 'pan' : 'positionSize');
                }}
              />
            </Tooltip>
          </Space>

          <Space size={8}>
            <Button
              type="text"
              ghost
              icon={isFullScreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              onClick={toggleFullScreen}
              style={{
                color: '#fff', fontSize: '12px', height: 28, padding: '0 12px',
                background: '#303030',
                borderRadius: '4px', display: 'flex', alignItems: 'center'
              }}
            >
              {isFullScreen ? '退出全屏' : '全屏显示'}
            </Button>
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

            <Button
              onClick={() => setShowPositioningCoords(v => !v)}
              style={{
                color: '#fff', fontSize: '12px', height: 28, padding: '0 12px',
                background: '#303030',
                borderRadius: '4px', display: 'flex', alignItems: 'center'
              }}
            >
              {showPositioningCoords ? '隐藏定位坐标' : '显示定位坐标'}
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
            <Ruler type="horizontal" scale={scale} offset={imageOffset.x} length={containerSize.w} ratio={rulerHorizRatio} maxImageSize={rulerHorizMax} />
          </div>

          {/* 左侧标尺 */}
          <div style={{ overflow: 'hidden', position: 'relative', zIndex: 10 }}>
            <Ruler type="vertical" scale={scale} offset={imageOffset.y} length={containerSize.h} ratio={rulerVertRatio} maxImageSize={rulerVertMax} />
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
                  key={selectedFile?.TaskFileId || 'default-canvas'}
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

                  {/* 0. 焊缝位置层（关键点标注，来自 location_0.pt）*/}
                  {showPositioningCoords && imageReady && !isImageResetingRef.current && selectedFile?.TaskFileId === prevTaskFileIdRef.current && (
                    weldLocationShapes.map((shape, idx) => {
                      const corrRotation = selectedFile?.CorrectionRotation ?? 0;
                      const corrFlipH = selectedFile?.CorrectionFlip ? -1 : 1;
                      const normR = ((corrRotation % 360) + 360) % 360;
                      const needsInverse = corrRotation !== 0 || corrFlipH === -1;
                      const rimgW = (normR === 90 || normR === 270)
                        ? (rawImageHeight || originalSize.h) : (rawImageWidth || originalSize.w);
                      const rimgH = (normR === 90 || normR === 270)
                        ? (rawImageWidth || originalSize.w) : (rawImageHeight || originalSize.h);

                      // 从关键点拟合椭圆：计算中心和半径（关键点不足时回退到 bbox）
                      const kps = shape.keypoints;
                      let cx: number, cy: number, rx: number, ry: number;
                      if (kps.length >= 2) {
                        const xs = kps.map(k => k.x);
                        const ys = kps.map(k => k.y);
                        cx = (Math.max(...xs) + Math.min(...xs)) / 2;
                        cy = (Math.max(...ys) + Math.min(...ys)) / 2;
                        rx = (Math.max(...xs) - Math.min(...xs)) / 2;
                        ry = (Math.max(...ys) - Math.min(...ys)) / 2;
                      } else {
                        cx = (shape.x1 + shape.x2) / 2;
                        cy = (shape.y1 + shape.y2) / 2;
                        rx = (shape.x2 - shape.x1) / 2;
                        ry = (shape.y2 - shape.y1) / 2;
                      }

                      // 等距生成12个时钟位置：12'在顶部(-π/2)，顺时针依次1'…11'
                      // 这样 12'/3'/6'/9' 精确落在上/右/下/左四个正方向
                      const CLOCK_LABELS = ["12'", "1'", "2'", "3'", "4'", "5'", "6'", "7'", "8'", "9'", "10'", "11'"];
                      const clockPoints = CLOCK_LABELS.map((label, i) => {
                        const angle = -Math.PI / 2 + (2 * Math.PI * i / 12);
                        return { label, x: cx + rx * Math.cos(angle), y: cy + ry * Math.sin(angle) };
                      });

                      return (
                        <g key={`weld-loc-${idx}`}>
                          {/* 时钟位置点：12'/3'/6'/9' 为主方向（较大），其余等距插值 */}
                          {clockPoints.map((pt, ki) => {
                            let kx = pt.x, ky = pt.y;
                            if (needsInverse && rimgW > 0 && rimgH > 0) {
                              const transformed = inverseTransformPoint(kx, ky, rimgW, rimgH, corrRotation, corrFlipH);
                              kx = transformed.x; ky = transformed.y;
                            }
                            const dKx = widthRatio > 0 ? kx / widthRatio : kx;
                            const dKy = heightRatio > 0 ? ky / heightRatio : ky;
                            const isCardinal = ki % 3 === 0; // 12', 3', 6', 9'
                            return (
                              <g key={ki}>
                                <circle cx={dKx} cy={dKy}
                                  r={(isCardinal ? 5 : 3.5) / scale}
                                  fill="#fd0202"
                                  opacity={0.9}
                                />
                                <text
                                  x={dKx + 6 / scale}
                                  y={dKy - 4 / scale}
                                  fill="#fd0202"
                                  fontSize={(isCardinal ? 13 : 11) / scale}
                                  fontWeight="bold"
                                  textAnchor="start"
                                  style={{ filter: 'drop-shadow(0 0 2px #000)' }}
                                >
                                  {pt.label}
                                </text>
                              </g>
                            );
                          })}
                        </g>
                      );
                    })
                  )}

                  {/* 0-B. 缺陷位置检测2原点层（来自 location_1.pt D路径，center_mark 十字架）*/}
                  {showPositioningCoords && imageReady && !isImageResetingRef.current && selectedFile?.TaskFileId === prevTaskFileIdRef.current && defectOriginPoint && (() => {
                    const corrRotation = selectedFile?.CorrectionRotation ?? 0;
                    const corrFlipH = selectedFile?.CorrectionFlip ? -1 : 1;
                    const normR = ((corrRotation % 360) + 360) % 360;
                    const needsInverse = corrRotation !== 0 || corrFlipH === -1;
                    const rimgW = (normR === 90 || normR === 270)
                      ? (rawImageHeight || originalSize.h) : (rawImageWidth || originalSize.w);
                    const rimgH = (normR === 90 || normR === 270)
                      ? (rawImageWidth || originalSize.w) : (rawImageHeight || originalSize.h);

                    let ox = defectOriginPoint.x;
                    let oy = defectOriginPoint.y;
                    if (needsInverse && rimgW > 0 && rimgH > 0) {
                      const t = inverseTransformPoint(ox, oy, rimgW, rimgH, corrRotation, corrFlipH);
                      ox = t.x; oy = t.y;
                    }
                    const dox = widthRatio > 0 ? ox / widthRatio : ox;
                    const doy = heightRatio > 0 ? oy / heightRatio : oy;
                    const crossSize = 24 / scale;
                    const circleR = 18 / scale;
                    const strokeW = 2.5 / scale;

                    return (
                      <g key="defect-origin">
                        {/* 外圆 */}
                        <circle
                          cx={dox} cy={doy} r={circleR}
                          fill="none"
                          stroke="#00e5ff"
                          strokeWidth={strokeW}
                          opacity={0.9}
                        />
                        {/* 十字横线 */}
                        <line
                          x1={dox - crossSize} y1={doy}
                          x2={dox + crossSize} y2={doy}
                          stroke="#00e5ff" strokeWidth={strokeW}
                          opacity={0.9}
                          style={{ filter: 'drop-shadow(0 0 3px #005577)' }}
                        />
                        {/* 十字竖线 */}
                        <line
                          x1={dox} y1={doy - crossSize}
                          x2={dox} y2={doy + crossSize}
                          stroke="#00e5ff" strokeWidth={strokeW}
                          opacity={0.9}
                          style={{ filter: 'drop-shadow(0 0 3px #005577)' }}
                        />
                        {/* 中心小实心圆 */}
                        <circle
                          cx={dox} cy={doy} r={3 / scale}
                          fill="#00e5ff"
                          opacity={0.95}
                        />
                        {/* 标签 */}
                        {(() => {
                          const tx = dox + circleR + 4 / scale;
                          const ty = doy - 4 / scale;
                          let tfm = '';
                          if (corrRotation !== 0) tfm += `rotate(${-corrRotation}, ${tx}, ${ty}) `;
                          if (corrFlipH === -1) tfm += `translate(${2 * tx}, 0) scale(-1, 1)`;
                          return (
                            <text
                              x={tx}
                              y={ty}
                              fill="#00e5ff"
                              fontSize={12 / scale}
                              fontWeight="bold"
                              style={{ filter: 'drop-shadow(0 0 2px #000)' }}
                              transform={tfm || undefined}
                            >
                              0点
                            </text>
                          );
                        })()}
                      </g>
                    );
                  })()}

                  {/* A. 绘制已保存的矩形 (增加 label 和 color) */}
                  {/* 从后端加载的数据是矫正后像素坐标,需要先逆变换回原图坐标再转为 CSS 坐标 */}
                  {/*只在图片加载完成后且当前文件ID匹配时才显示缺陷信息 */}
                  {(() => {
                    // 防止切换文件瞬间闪烁：只有当 imageReady 为 true 且当前渲染的文件 ID 与已处理的 ID 一致，且不处于重置过程中时才显示
                    const isFileSynced = selectedFile?.TaskFileId === prevTaskFileIdRef.current;
                    const shouldShowDefects = imageReady && !isImageResetingRef.current && isFileSynced;

                    if (!shouldShowDefects) return null;

                    // 渲染时逆变换：使用已加载的图像尺寸（此时 rawImageWidth/Height 已有值）
                    const corrRotation = selectedFile?.CorrectionRotation ?? 0;
                    const corrFlipH = selectedFile?.CorrectionFlip ? -1 : 1;
                    const normR = ((corrRotation % 360) + 360) % 360;
                    const needsInverse = corrRotation !== 0 || corrFlipH === -1;
                    // 矫正后图像的像素尺寸（90/270°时宽高互换）
                    const rimgW = (normR === 90 || normR === 270)
                      ? (rawImageHeight || originalSize.h) : (rawImageWidth || originalSize.w);
                    const rimgH = (normR === 90 || normR === 270)
                      ? (rawImageWidth || originalSize.w) : (rawImageHeight || originalSize.h);

                    // 文字反变换：抵消 CSS 旋转和翻转，使标注文字固定正向显示
                    // SVG transform 应用顺序：先右边再左边，所以写为 rotate 然后 scale
                    const makeTextTransform = (tx: number, ty: number) => {
                      let t = '';
                      // 先抖消旋转（相对于文字中心）
                      if (corrRotation !== 0) {
                        t += `rotate(${-corrRotation}, ${tx}, ${ty}) `;
                      }
                      // 再抖消水平翻转（如果有）
                      if (corrFlipH === -1) {
                        t += `translate(${2 * tx}, 0) scale(-1, 1)`;
                      }
                      return t || undefined;
                    };

                    return defectRects.map((rect, idx) => {
                      let rx = rect.x, ry = rect.y, rw = rect.w, rh = rect.h;
                      if (needsInverse && rimgW > 0 && rimgH > 0) {
                        const p1 = inverseTransformPoint(rx, ry, rimgW, rimgH, corrRotation, corrFlipH);
                        const p2 = inverseTransformPoint(rx + rw, ry + rh, rimgW, rimgH, corrRotation, corrFlipH);
                        rx = Math.min(p1.x, p2.x); ry = Math.min(p1.y, p2.y);
                        rw = Math.abs(p2.x - p1.x); rh = Math.abs(p2.y - p1.y);
                      }
                      const displayX = widthRatio > 0 ? rx / widthRatio : rx;
                      const displayY = widthRatio > 0 ? ry / widthRatio : ry;
                      const displayW = widthRatio > 0 ? rw / widthRatio : rw;
                      const displayH = widthRatio > 0 ? rh / widthRatio : rh;
                      // 标签附着在矩形左上角上方
                      const labelX = displayX, labelY = displayY - 5;

                      return (
                        <g key={`rect-${idx}`}>
                          <rect
                            x={displayX} y={displayY} width={displayW} height={displayH}
                            stroke={rect.color}
                            strokeWidth={(hoveredDefectKey === `rect-${idx}` ? 4 : 2) / scale}
                            fill={hoveredDefectKey === `rect-${idx}` ? `${rect.color}4D` : "none"}
                          />
                          <text
                            x={labelX} y={labelY}
                            fill={rect.color}
                            fontSize={(hoveredDefectKey === `rect-${idx}` ? 18 : 14) / scale}
                            fontWeight="bold"
                            style={{ textShadow: '0 0 2px #000' }}
                            transform={makeTextTransform(labelX, labelY)}
                          >
                            {rect.label}
                          </text>
                        </g>
                      );
                    });
                  })()}

                  {/* B. 绘制已保存的多边形 */}
                  {(() => {
                    const isFileSynced = selectedFile?.TaskFileId === prevTaskFileIdRef.current;
                    const shouldShowDefects = imageReady && !isImageResetingRef.current && isFileSynced;
                    if (!shouldShowDefects) return null;

                    const corrRotation = selectedFile?.CorrectionRotation ?? 0;
                    const corrFlipH = selectedFile?.CorrectionFlip ? -1 : 1;
                    const normR = ((corrRotation % 360) + 360) % 360;
                    const needsInverse = corrRotation !== 0 || corrFlipH === -1;
                    const rimgW = (normR === 90 || normR === 270) ? (rawImageHeight || originalSize.h) : (rawImageWidth || originalSize.w);
                    const rimgH = (normR === 90 || normR === 270) ? (rawImageWidth || originalSize.w) : (rawImageHeight || originalSize.h);

                    const makeTextTransform = (tx: number, ty: number) => {
                      let t = '';
                      if (corrRotation !== 0) t += `rotate(${-corrRotation}, ${tx}, ${ty}) `;
                      if (corrFlipH === -1) t += `translate(${2 * tx}, 0) scale(-1, 1)`;
                      return t || undefined;
                    };

                    return defectPolygons.map((poly, idx) => {
                      const transformedPoints = poly.points.map(p => {
                        let { x, y } = p;
                        if (needsInverse && rimgW > 0 && rimgH > 0) {
                          ({ x, y } = inverseTransformPoint(x, y, rimgW, rimgH, corrRotation, corrFlipH));
                        }
                        return { x: widthRatio > 0 ? x / widthRatio : x, y: heightRatio > 0 ? y / heightRatio : y };
                      });
                      const pointsStr = transformedPoints.map(p => `${p.x},${p.y}`).join(' ');
                      const labelP = transformedPoints[0] || { x: 0, y: 0 };
                      const lx = labelP.x, ly = labelP.y - 5;

                      return (
                        <g key={`poly-${idx}`}>
                          <polygon
                            points={pointsStr}
                            stroke={poly.color}
                            strokeWidth={(hoveredDefectKey === `polygon-${idx}` ? 4 : 2) / scale}
                            fill={hoveredDefectKey === `polygon-${idx}` ? `${poly.color}4D` : "none"}
                          />
                          <text
                            x={lx} y={ly}
                            fill={poly.color}
                            fontSize={(hoveredDefectKey === `polygon-${idx}` ? 18 : 14) / scale}
                            fontWeight="bold"
                            style={{ textShadow: '0 0 2px #000' }}
                            transform={makeTextTransform(lx, ly)}
                          >
                            {poly.label}
                          </text>
                        </g>
                      );
                    });
                  })()}

                  {/* C. 绘制已保存的圆形 */}
                  {(() => {
                    const isFileSynced = selectedFile?.TaskFileId === prevTaskFileIdRef.current;
                    const shouldShowDefects = imageReady && !isImageResetingRef.current && isFileSynced;
                    if (!shouldShowDefects) return null;

                    const corrRotation = selectedFile?.CorrectionRotation ?? 0;
                    const corrFlipH = selectedFile?.CorrectionFlip ? -1 : 1;
                    const normR = ((corrRotation % 360) + 360) % 360;
                    const needsInverse = corrRotation !== 0 || corrFlipH === -1;
                    const rimgW = (normR === 90 || normR === 270) ? (rawImageHeight || originalSize.h) : (rawImageWidth || originalSize.w);
                    const rimgH = (normR === 90 || normR === 270) ? (rawImageWidth || originalSize.w) : (rawImageHeight || originalSize.h);

                    const makeTextTransform = (tx: number, ty: number) => {
                      let t = '';
                      if (corrRotation !== 0) t += `rotate(${-corrRotation}, ${tx}, ${ty}) `;
                      if (corrFlipH === -1) t += `translate(${2 * tx}, 0) scale(-1, 1)`;
                      return t || undefined;
                    };

                    return defectCircles.map((circle, idx) => {
                      let { x: cirX, y: cirY } = circle;
                      if (needsInverse && rimgW > 0 && rimgH > 0) {
                        ({ x: cirX, y: cirY } = inverseTransformPoint(cirX, cirY, rimgW, rimgH, corrRotation, corrFlipH));
                      }
                      const cx = widthRatio > 0 ? cirX / widthRatio : cirX;
                      const cy = widthRatio > 0 ? cirY / widthRatio : cirY;
                      const r = widthRatio > 0 ? circle.r / widthRatio : circle.r;
                      const labelX = cx, labelY = cy - r - 5;

                      return (
                        <g key={`circle-${idx}`}>
                          <circle
                            cx={cx}
                            cy={cy}
                            r={r}
                            stroke={circle.color}
                            strokeWidth={(hoveredDefectKey === `circle-${idx}` ? 4 : 2) / scale}
                            fill={hoveredDefectKey === `circle-${idx}` ? `${circle.color}4D` : "none"}
                          />
                          <text
                            x={labelX} y={labelY}
                            fill={circle.color}
                            fontSize={(hoveredDefectKey === `circle-${idx}` ? 18 : 14) / scale}
                            fontWeight="bold"
                            style={{ textShadow: '0 0 2px #000' }}
                            transform={makeTextTransform(labelX, labelY)}
                          >
                            {circle.label}
                          </text>
                        </g>
                      );
                    });
                  })()}


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

                {/* 3.5. 坐标原点垂直辅助线（定位标记成像后显示） */}
                {originPoint && (
                  <svg
                    viewBox={`0 0 ${imgSize.w} ${imgSize.h}`}
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 11 }}
                  >
                    {(() => {
                      const imageCoords = calculateImageCoordinates(originPoint.x, originPoint.y);
                      return (
                        <line
                          x1={imageCoords.x}
                          y1={0}
                          x2={imageCoords.x}
                          y2={imgSize.h}
                          stroke="rgba(245, 34, 45, 1"
                          strokeWidth={1 / scale}
                          strokeDasharray="5 5"
                        />
                      );
                    })()}
                  </svg>
                )}

                {/* 4. 标定线绘制层 */}
                {activeTool === 'calibrate' && calibrateLine && (
                  <svg
                    viewBox={`0 0 ${imgSize.w} ${imgSize.h}`}
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 15 }}
                  >
                    <line x1={calibrateLine.x1} y1={calibrateLine.y1} x2={calibrateLine.x2} y2={calibrateLine.y2} stroke="#faad14" strokeWidth={2 / scale} strokeDasharray="4 2" />
                    <circle cx={calibrateLine.x1} cy={calibrateLine.y1} r={3 / scale} fill="#faad14" />
                    <circle cx={calibrateLine.x2} cy={calibrateLine.y2} r={3 / scale} fill="#faad14" />
                  </svg>
                )}

                {/* 5. 椭圆工具绘制层 */}
                {activeTool === 'positionSize' && positionSizeType === 'elliptical' && ellipseState.shape && (
                  <svg
                    viewBox={`0 0 ${imgSize.w} ${imgSize.h}`}
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 15 }}
                  >
                    <g
                      transform={`translate(${ellipseState.shape.cx} ${ellipseState.shape.cy}) rotate(${ellipseState.shape.rotation * 180 / Math.PI})`}
                    >
                      {/* A. 椭圆本体 */}
                      <ellipse
                        cx={0} cy={0}
                        rx={ellipseState.shape.rx} ry={ellipseState.shape.ry}
                        fill="none"
                        stroke={ellipseState.mode === 'placing' ? '#00ccff' : 'rgba(255, 255, 255, 0.3)'}
                        strokeWidth={ellipseState.mode === 'placing' ? 2 / scale : 15 / scale}
                        strokeDasharray={ellipseState.mode === 'placing' ? '5 5' : 'none'}
                      />

                      {/* B. 时钟系统刻度 */}
                      {Array.from({ length: 12 }).map((_, i) => {
                        const startAngle = -Math.PI / 2;
                        const angle = startAngle + (i * (Math.PI / 6));
                        const px = ellipseState.shape!.rx * Math.cos(angle);
                        const py = ellipseState.shape!.ry * Math.sin(angle);

                        // 根据椭圆大小动态调整标签偏移量
                        // 使用椭圆较小半径的15%作为偏移，最小20像素，最大40像素
                        const minRadius = Math.min(ellipseState.shape!.rx, ellipseState.shape!.ry);
                        const labelOffset = Math.max(20, Math.min(40, minRadius * 0.15)) / scale;
                        const tx = (ellipseState.shape!.rx + labelOffset) * Math.cos(angle);
                        const ty = (ellipseState.shape!.ry + labelOffset) * Math.sin(angle);
                        const label = i === 0 ? "12'" : i + "'";

                        return (
                          <g key={`clock-${i}`}>
                            <circle cx={px} cy={py} r={3 / scale} fill="#00ccff" />
                            <text
                              x={tx} y={ty}
                              fill={(i % 3 === 0) ? "#ffcc00" : "#00ccff"}
                              fontSize={16 / scale}
                              fontWeight="bold"
                              textAnchor="middle"
                              dominantBaseline="middle"
                            >
                              {label}
                            </text>
                          </g>
                        );
                      })}

                      {/* C. 控制手柄 (仅编辑模式) */}
                      {ellipseState.mode === 'editing' && (
                        <g>
                          {/* 辅助框 */}
                          <ellipse
                            cx={0} cy={0}
                            rx={ellipseState.shape.rx} ry={ellipseState.shape.ry}
                            fill="none" stroke="#00ff00" strokeWidth={1 / scale} strokeDasharray="5 3"
                          />
                          {/* 旋转杆 */}
                          <line
                            x1={0} y1={-ellipseState.shape.ry}
                            x2={0} y2={-ellipseState.shape.ry - ROTATE_HANDLE_OFFSET}
                            stroke="#fff" strokeWidth={2 / scale}
                          />
                          {/* 旋转手柄 */}
                          <circle
                            cx={0} cy={-ellipseState.shape.ry - ROTATE_HANDLE_OFFSET}
                            r={HANDLE_SIZE / scale}
                            fill="#fff" stroke="#000" strokeWidth={1 / scale}
                          />

                          {/* 缩放手柄 */}
                          {[
                            { x: ellipseState.shape.rx, y: 0 },
                            { x: -ellipseState.shape.rx, y: 0 },
                            { x: 0, y: ellipseState.shape.ry },
                            { x: 0, y: -ellipseState.shape.ry }
                          ].map((pt, idx) => (
                            <rect
                              key={`handle-${idx}`}
                              x={pt.x - HANDLE_SIZE / scale}
                              y={pt.y - HANDLE_SIZE / scale}
                              width={HANDLE_SIZE * 2 / scale}
                              height={HANDLE_SIZE * 2 / scale}
                              fill="#fff" stroke="#000" strokeWidth={1 / scale}
                            />
                          ))}
                        </g>
                      )}
                    </g>
                  </svg>
                )}

                {/* 6. 垂直成像绘制层 */}
                {activeTool === 'positionSize' && positionSizeType === 'vertical' && verticalState.shape && (
                  <svg
                    viewBox={`0 0 ${imgSize.w} ${imgSize.h}`}
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 15 }}
                  >
                    <g>
                      {/* A. 扁平椭圆本体 */}
                      <ellipse
                        cx={verticalState.shape.cx}
                        cy={verticalState.shape.cy}
                        rx={verticalState.shape.rx}
                        ry={verticalState.shape.ry}
                        fill="none"
                        stroke={verticalState.mode === 'placing' ? '#00ccff' : 'rgba(255, 255, 255, 0.3)'}
                        strokeWidth={verticalState.mode === 'placing' ? 2 / scale : 15 / scale}
                        strokeDasharray={verticalState.mode === 'placing' ? '5 5' : 'none'}
                      />

                      {/* B. 垂直成像时钟刻度（重叠显示） */}
                      {verticalState.mode === 'editing' && (() => {
                        const s = verticalState.shape;
                        const labelOffsetY = 25 / scale;

                        // 5个位置：9', (8',10'), (12',6'), (2',4'), 3'
                        const positions = [
                          { x: s.cx - s.rx, labels: ["9'"], color: "#ffcc00" },                    // 最左：9'
                          { x: s.cx - s.rx * 0.5, labels: ["8'", "10'"], color: "#ff6666" },       // 左中：8' 和 10' 重叠
                          { x: s.cx, labels: ["12'", "6'"], color: "#ffcc00" },                    // 中间：12' 和 6' 重叠
                          { x: s.cx + s.rx * 0.5, labels: ["2'", "4'"], color: "#ff6666" },        // 右中：2' 和 4' 重叠
                          { x: s.cx + s.rx, labels: ["3'"], color: "#ffcc00" }                     // 最右：3'
                        ];

                        return positions.map((pos, idx) => (
                          <g key={`vertical-clock-${idx}`}>
                            {/* 刻度点 */}
                            {pos.labels.length === 1 ? (
                              // 单个点
                              <circle cx={pos.x} cy={s.cy} r={3 / scale} fill={pos.color} />
                            ) : (
                              // 重叠的两个点（上下分开）
                              <>
                                <circle cx={pos.x} cy={s.cy - 5 / scale} r={3 / scale} fill={pos.color} />
                                <circle cx={pos.x} cy={s.cy + 5 / scale} r={3 / scale} fill={pos.color} />
                              </>
                            )}

                            {/* 标签文字 */}
                            {pos.labels.map((label, labelIdx) => (
                              <text
                                key={`label-${labelIdx}`}
                                x={pos.x}
                                y={s.cy + (pos.labels.length === 1 ? -labelOffsetY : (labelIdx === 0 ? -labelOffsetY : labelOffsetY + 10 / scale))}
                                fill={pos.color}
                                fontSize={pos.labels.length === 1 ? 20 / scale : 16 / scale}
                                fontWeight="bold"
                                textAnchor="middle"
                              >
                                {label}
                              </text>
                            ))}

                            {/* 重叠位置的连接线 */}
                            {pos.labels.length > 1 && (
                              <>
                                <line
                                  x1={pos.x} y1={s.cy - 5 / scale}
                                  x2={pos.x} y2={s.cy - labelOffsetY + 5 / scale}
                                  stroke={pos.color} strokeWidth={1 / scale}
                                />
                                <line
                                  x1={pos.x} y1={s.cy + 5 / scale}
                                  x2={pos.x} y2={s.cy + labelOffsetY - 5 / scale}
                                  stroke={pos.color} strokeWidth={1 / scale}
                                />
                              </>
                            )}
                          </g>
                        ));
                      })()}

                      {/* C. 控制手柄（仅编辑模式，只有左右两个） */}
                      {verticalState.mode === 'editing' && (
                        <g>
                          {/* 辅助框 */}
                          <ellipse
                            cx={verticalState.shape.cx}
                            cy={verticalState.shape.cy}
                            rx={verticalState.shape.rx}
                            ry={verticalState.shape.ry}
                            fill="none" stroke="#00ff00" strokeWidth={1 / scale} strokeDasharray="5 3"
                          />

                          {/* 左右拉伸手柄 */}
                          {[
                            { x: verticalState.shape.cx - verticalState.shape.rx, y: verticalState.shape.cy },  // 9' 位置（左）
                            { x: verticalState.shape.cx + verticalState.shape.rx, y: verticalState.shape.cy }   // 3' 位置（右）
                          ].map((pt, idx) => (
                            <rect
                              key={`handle-${idx}`}
                              x={pt.x - HANDLE_SIZE / scale}
                              y={pt.y - HANDLE_SIZE / scale}
                              width={HANDLE_SIZE * 2 / scale}
                              height={HANDLE_SIZE * 2 / scale}
                              fill="#fff" stroke="#000" strokeWidth={1 / scale}
                            />
                          ))}
                        </g>
                      )}
                    </g>
                  </svg>
                )}

                {/* 7. 定位标记成像绘制层（十字线） - 复用设置坐标原点的 tempOrigin */}
                {activeTool === 'positionSize' && positionSizeType === 'positioning' && tempOrigin && (
                  <svg
                    viewBox={`0 0 ${imgSize.w} ${imgSize.h}`}
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 15 }}
                  >
                    {/* 十字线 */}
                    <line
                      x1={tempOrigin.x} y1={0}
                      x2={tempOrigin.x} y2={imgSize.h}
                      stroke="#f5222d" strokeWidth={1 / scale}
                    />
                    <line
                      x1={0} y1={tempOrigin.y}
                      x2={imgSize.w} y2={tempOrigin.y}
                      stroke="#f5222d" strokeWidth={1 / scale}
                    />
                    {/* x 和 y 标签 */}
                    <text
                      x={tempOrigin.x + 10 / scale}
                      y={tempOrigin.y - 6 / scale}
                      fill="#f5222d"
                      fontSize={12 / scale}
                      style={{ userSelect: 'none' }}
                    >
                      x
                    </text>
                    <text
                      x={tempOrigin.x + 6 / scale}
                      y={tempOrigin.y + 14 / scale}
                      fill="#f5222d"
                      fontSize={12 / scale}
                      style={{ userSelect: 'none' }}
                    >
                      y
                    </text>
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

          {/* 位置和尺寸工具条 */}
          {activeTool === 'positionSize' && (
            <div style={{
              position: 'absolute',
              left: '32px',
              top: '32px',
              zIndex: 300
            }}>
              <PositionAndSizeTool
                currentType={positionSizeType}
                onTypeChange={setPositionSizeType}
                onClose={() => setActiveTool('pan')}
              />
            </div>
          )}

        </div>

        {/* 底部状态条 */}
        <div style={{ height: 28, background: '#f8f9fa', borderTop: '1px solid #e9ecef', display: 'flex', alignItems: 'center', padding: '0 16px', fontSize: '11px', color: '#6c757d' }}>
          {/* 显示图像尺寸和实时鼠标坐标 */}
          图像尺寸：{originalSize.w}*{originalSize.h}，鼠标位置：{mousePos.x}*{mousePos.y},当前工具: {activeTool === 'calibrate' ? '尺寸定标' : activeTool === 'measure' ? '测量' : activeTool === 'setOrigin' ? '设置原点' : activeTool === 'defect' ? '缺陷标注' : activeTool === 'windowing' ? '窗位窗宽' : activeTool === 'positionSize' ? '位置和尺寸' : '平移'}
        </div>
      </Content >

      {/* 右侧审核信息 (重构区域) */}
      < Sider width={320} theme="light" style={{ borderLeft: "1px solid #f0f0f0", display: 'flex', flexDirection: 'column', background: '#fff' }}>
        {/* 设置 height: 100% 和 overflowY: auto，
            确保内容超出时，这个容器内部出现滚动条，而不是把页面撑开。
           */}
        < div style={{ flex: 1, padding: '20px 16px', overflowY: 'auto', height: '100%' }}>
          <Space direction="vertical" style={{ width: '100%' }} size={24}>

            {/* 1. 底片信息 (垂直布局，可编辑，带折叠) */}
            <div>
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
                <Title level={5} style={{ margin: 0, fontSize: '15px', flex: 1 }}>底片信息</Title>
                <Tooltip title="重置底片信息">
                  <Button
                    type="text"
                    size="small"
                    icon={<ReloadOutlined />}
                    onClick={(e) => { e.stopPropagation(); handleResetFilmInfo(); }}
                  />
                </Tooltip>
              </div>

              {/* 内容根据状态显示或隐藏 */}
              {showFilmInfo && (
                // 布局改为 horizontal，并设置 labelCol 和 wrapperCol
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
                <Title level={5} style={{ margin: 0, fontSize: '15px', flex: 1 }}>缺陷信息</Title>
                <Space size={2}>
                  <Tooltip title="撤销 (Undo)">
                    <Button
                      type="text"
                      size="small"
                      icon={<UndoOutlined />}
                      disabled={historyIndex <= 0}
                      onClick={(e) => { e.stopPropagation(); handleUndo(); }}
                    />
                  </Tooltip>
                  <Tooltip title="重做 (Redo)">
                    <Button
                      type="text"
                      size="small"
                      icon={<RedoOutlined />}
                      disabled={historyIndex >= history.length - 1}
                      onClick={(e) => { e.stopPropagation(); handleRedo(); }}
                    />
                  </Tooltip>
                  <Tooltip title="重置缺陷信息">
                    <Button
                      type="text"
                      size="small"
                      icon={<ReloadOutlined />}
                      disabled={isResetDisabled}
                      onClick={(e) => { e.stopPropagation(); handleResetDefects(); }}
                    />
                  </Tooltip>
                </Space>
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
        </div >
      </Sider >

      {/* 测量距离前的尺寸定标确认弹窗 */}
      < Modal
        title="尺寸定标确认"
        open={calibratePromptModalVisible}
        onCancel={() => setCalibratePromptModalVisible(false)}
        footer={null}
        width={360}
        centered
        maskClosable={false}
        getContainer={() => editorContainerRef.current || document.body}
      >
        <div style={{ marginBottom: 24 }}>
          <Text>是否需要先进行尺寸定标？</Text>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button
            onClick={() => {
              setCalibratePromptModalVisible(false);
              setActiveTool('measure');
            }}
          >
            否，直接测量
          </Button>
          <Button
            type="primary"
            onClick={() => {
              setCalibratePromptModalVisible(false);
              setMeasureAfterCalibrate(true);
              setActiveTool('calibrate');
              setCalibrateLine(null);
            }}
          >
            是，先定标
          </Button>
        </div>
      </Modal >

      {/* 4. 像素标定弹窗 */}
      < Modal
        title="像素标定"
        open={calibrateModalVisible}
        onOk={handleCalibrateConfirm}
        onCancel={() => {
          setCalibrateModalVisible(false);
          setCalibrateLine(null);
          setMeasureAfterCalibrate(false);
          setActiveTool('pan');
        }}
        okText="确认"
        cancelText="取消"
        width={300}
        centered
        maskClosable={false}
        getContainer={() => editorContainerRef.current || document.body}
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
      </Modal >

      {/* 5. 新增：缺陷类型选择弹窗 */}
      < Modal
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
        getContainer={() => editorContainerRef.current || document.body}
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
          getPopupContainer={() => editorContainerRef.current || document.body}
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
      </Modal >

    </Layout >
  );
};

const isSevere = (type: string) => {
  const severeKeywords = ['裂纹', '未熔合', '未焊透', 'crack', 'unfused', 'incomplete'];
  return severeKeywords.some(k => type.toLowerCase().includes(k));
};

export default ReportEditorPage;