import React, { useState, useRef, useCallback, useEffect } from 'react';
import { message } from 'antd';
import {
  applyWindowLevelToRawData,
  calculateStatsFromRawData,
  getDecodedImageFromCache,
  getEditorInitialWindow,
  preprocessToGrayCache,
  renderDisplayDataToCanvas,
  type ImageStats,
} from '@/utils/highBitImage';

export { preprocessToGrayCache } from '@/utils/highBitImage';

// Hook 入参
interface UseWindowLevelToolProps {
  activeTool: string;
  scale: number;
  imageFile?: File;
  rotation?: number; // 当前旋转角度（度），用于坐标逆变换
  flipH?: number;    // 水平翻转系数（1 不翻转, -1 翻转）
  flipV?: number;    // 垂直翻转系数（1 不翻转, -1 翻转）
}

export const useWindowLevelTool = ({ activeTool, scale, imageFile, rotation = 0, flipH = 1, flipV = 1 }: UseWindowLevelToolProps) => {
  // 原始灰度数据（真正的原始数据）
  const [rawGrayData, setRawGrayData] = useState<Float32Array | null>(null);
  const [imageWidth, setImageWidth] = useState(0);
  const [imageHeight, setImageHeight] = useState(0);

  // 图片是否已加载并渲染完成
  const [imageReady, setImageReady] = useState(false);

  // 用 ref 同步跟踪 imageFile，使 updateDisplay 无需将 imageFile 列入 deps，
  // 避免 imageFile 变化时触发 updateDisplay → 用旧 rawGrayData 渲染出错误图片
  const imageFileRef = useRef<File | undefined>(undefined);
  imageFileRef.current = imageFile;

  // 加载版本号：每次开始加载新图片时递增。
  // rawGrayData 对应的版本号存在 grayDataVersionRef 中。
  // renderToCanvas 对比两者，不一致说明是过期数据，直接跳过，防止旧图闪烁。
  const loadVersionRef = useRef(0);
  const grayDataVersionRef = useRef(0);

  // 窗宽窗位参数
  const [windowData, setWindowData] = useState({ ww: 255, wl: 128 });

  // ROI 选择状态
  const [dragStart, setDragStart] = useState<{ x: number, y: number } | null>(null);
  const [dragCurrent, setDragCurrent] = useState<{ x: number, y: number } | null>(null);

  // Canvas引用
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // 缓存全图统计信息
  const imageStatsRef = useRef<ImageStats | null>(null);

  // 节流控制
  const lastCalcTime = useRef<number>(0);

  // ==========================================================================
  // 核心：在原始灰度数据上应用窗宽窗位
  // ==========================================================================
  const applyWindowLevelToGrayData = useCallback((
    data: Float32Array,
    ww: number,
    wl: number
  ): Uint8Array => {
    return applyWindowLevelToRawData(data, ww, wl);
  }, []);

  // ==========================================================================
  // 渲染：将处理后的灰度数据绘制到Canvas
  // ==========================================================================
  const renderToCanvas = useCallback((processedData: Uint8Array) => {
    const canvas = canvasRef.current;
    if (!canvas || !processedData || imageWidth === 0 || imageHeight === 0) return;

    // 版本号不一致说明 rawGrayData 是过期数据（属于上一张图），直接跳过，防止旧图闪烁
    if (grayDataVersionRef.current !== loadVersionRef.current) return;
    if (!imageFileRef.current) return;

    renderDisplayDataToCanvas(canvas, processedData, imageWidth, imageHeight);

    // 直接同步标记就绪（不用 rAF），canvas 有 visibility:hidden 保护，
    // 不会在 imageReady=false 期间显示，故无需 rAF 来避免 SVG 提前出现的闪烁
    setImageReady(true);
  }, [imageWidth, imageHeight]);

  // ==========================================================================
  // 更新显示
  // ==========================================================================
  const updateDisplay = useCallback(() => {
    // 用 ref 检查 imageFile，避免将 imageFile 列入 deps（否则 imageFile 变化时会
    // 立即触发此 effect，此时 rawGrayData 还是旧图数据，导致渲染出错误图片/闪屏）
    if (!imageFileRef.current || !rawGrayData) return;

    const processed = applyWindowLevelToGrayData(
      rawGrayData,
      windowData.ww,
      windowData.wl
    );

    renderToCanvas(processed);
  }, [rawGrayData, windowData, applyWindowLevelToGrayData, renderToCanvas]);

  // ==========================================================================
  // 更新窗宽窗位
  // ==========================================================================
  const updateWindowLevel = useCallback((newWW: number, newWL: number) => {
    const stats = imageStatsRef.current;

    const w = stats
      ? Math.max(1, Math.min(stats.max - stats.min || 1, newWW))
      : Math.max(1, newWW);

    let l: number;
    if (stats) {
      l = Math.max(stats.min, Math.min(stats.max, newWL));
    } else {
      l = Math.max(0, Math.min(255, newWL));
    }

    setWindowData({ ww: Math.round(w), wl: Math.round(l) });
  }, []);

  // ==========================================================================
  // 加载图像文件（关键：直接读取原始数据）
  // ==========================================================================
  useEffect(() => {
    if (!imageFile) {
      setRawGrayData(null);
      setImageWidth(0);
      setImageHeight(0);
      setImageReady(false);
      imageStatsRef.current = null;

      // 清空画布
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx?.clearRect(0, 0, canvas.width, canvas.height);
      }
      return;
    }

    // 切换新图片时，递增加载版本号，使所有过期的 renderToCanvas 调用失效
    loadVersionRef.current += 1;
    const myVersion = loadVersionRef.current;

    // 立即清空旧数据和画布，防止 updateDisplay 用旧灰度数据渲染新图
    setImageReady(false);
    setRawGrayData(null);
    setImageWidth(0);
    setImageHeight(0);
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
    }

    // 取消标志：effect 清理时置 true，阻止过期的异步回调更新状态（竞态保护）
    let cancelled = false;

    const loadImage = async () => {
      try {
        // 解码并缓存灰度数据（若已有缓存则立即返回，否则在后台完成解码）
        await preprocessToGrayCache(imageFile);

        if (cancelled) return;

        const cached = getDecodedImageFromCache(imageFile);
        if (!cached) return;

        const initialWindow = getEditorInitialWindow(cached);

        imageStatsRef.current = cached.stats;
        setWindowData({
          ww: Math.round(initialWindow.ww),
          wl: Math.round(initialWindow.wl),
        });
        grayDataVersionRef.current = myVersion;
        setRawGrayData(cached.rawData);
        setImageWidth(cached.width);
        setImageHeight(cached.height);
      } catch (error) {
        if (!cancelled) {
          console.error('图像加载失败:', error);
          message.error('图像加载失败');
        }
      }
    };

    loadImage();

    // effect 清理：标记取消，防止旧请求的异步回调污染新图片的状态
    return () => { cancelled = true; };
  }, [imageFile]);

  // 监听窗宽窗位变化，更新显示
  useEffect(() => {
    updateDisplay();
  }, [updateDisplay]);

  // ==========================================================================
  // ROI 计算
  // ==========================================================================
  const computeROI = useCallback((
    startX: number,
    startY: number,
    endX: number,
    endY: number,
    isRealtime: boolean = false
  ) => {
    const canvas = canvasRef.current;
    if (!rawGrayData || imageWidth === 0 || !canvas) return;

    // 获取Canvas的显示尺寸（本地坐标系，对应原始图像坐标系）
    const displayWidth = canvas.clientWidth;
    const displayHeight = canvas.clientHeight;

    // 计算显示尺寸与原始尺寸的比例
    const scaleX = imageWidth / displayWidth;
    const scaleY = imageHeight / displayHeight;

    // 计算显示坐标系中的ROI
    const rawX = Math.min(startX, endX);
    const rawY = Math.min(startY, endY);
    const rawW = Math.abs(endX - startX);
    const rawH = Math.abs(endY - startY);

    if (rawW <= 2 || rawH <= 2) return;

    // 转换到原始图像坐标系
    const imageX = Math.floor(rawX * scaleX);
    const imageY = Math.floor(rawY * scaleY);
    const imageW = Math.floor(rawW * scaleX);
    const imageH = Math.floor(rawH * scaleY);

    // 限制在图像范围内
    const finalX = Math.max(0, Math.min(imageX, imageWidth - 1));
    const finalY = Math.max(0, Math.min(imageY, imageHeight - 1));
    const finalW = Math.min(imageW, imageWidth - finalX);
    const finalH = Math.min(imageH, imageHeight - finalY);

    const step = isRealtime ? 3 : 1;

    const stats = calculateStatsFromRawData(
      rawGrayData,
      finalX,
      finalY,
      finalW,
      finalH,
      imageWidth,
      step
    );

    if (!stats) return;

    const calcWW = Math.max(1, Math.min(4 * stats.std, stats.max - stats.min));
    const calcWL = stats.mean;

    updateWindowLevel(calcWW, calcWL);

    if (!isRealtime) {
      message.destroy();
    }
  }, [rawGrayData, imageWidth, imageHeight, updateWindowLevel]);

  // ==========================================================================
  // 鼠标事件
  // ==========================================================================
  // 将鼠标视口坐标转换到图像 Canvas 的 CSS 本地坐标系。
  // CSS transform 顺序：scale(sx,sy) · rotate(r)，逆变换必须反序：先 scale^-1，再 rotate^-1。
  // 若先 rotate^-1 再 scale^-1（即旧写法），在 flip≠1 且 rotation≠0 时坐标会出错。
  const getLocalCoordinates = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const vx = e.clientX - centerX;
    const vy = e.clientY - centerY;
    // 第一步：撤销 scale·flip（flipH=±1，所以 ÷(scale·flipH) 等价于 ×flipH÷scale）
    const ux = vx * flipH / scale;
    const uy = vy * flipV / scale;
    // 第二步：撤销 rotation
    const rad = -(rotation * Math.PI / 180);
    const dx = ux * Math.cos(rad) - uy * Math.sin(rad);
    const dy = ux * Math.sin(rad) + uy * Math.cos(rad);
    const canvas = canvasRef.current;
    const halfW = canvas ? canvas.clientWidth / 2 : 0;
    const halfH = canvas ? canvas.clientHeight / 2 : 0;
    return {
      x: dx + halfW,
      y: dy + halfH,
    };
  }, [rotation, flipH, flipV, scale]);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool !== 'windowing') return;

    e.preventDefault();
    e.stopPropagation();

    const { x, y } = getLocalCoordinates(e);

    setDragStart({ x, y });
    setDragCurrent({ x, y });
  }, [activeTool, getLocalCoordinates]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool !== 'windowing' || !dragStart) return;

    const { x, y } = getLocalCoordinates(e);

    setDragCurrent({ x, y });

    const now = Date.now();
    if (now - lastCalcTime.current > 40) {
      computeROI(dragStart.x, dragStart.y, x, y, true);
      lastCalcTime.current = now;
    }
  }, [activeTool, dragStart, getLocalCoordinates, computeROI]);

  const handleMouseUp = useCallback(() => {
    if (activeTool !== 'windowing' || !dragStart || !dragCurrent) {
      setDragStart(null);
      setDragCurrent(null);
      return;
    }

    computeROI(dragStart.x, dragStart.y, dragCurrent.x, dragCurrent.y, false);

    setDragStart(null);
    setDragCurrent(null);
  }, [activeTool, dragStart, dragCurrent, computeROI]);

  // ==========================================================================
  // 重置窗口
  // ==========================================================================
  const resetWindow = useCallback(() => {
    const stats = imageStatsRef.current;

    if (stats) {
      const resetWW = stats.max - stats.min;
      const resetWL = (stats.max + stats.min) / 2;
      updateWindowLevel(resetWW, resetWL);
    } else {
      updateWindowLevel(255, 128);
    }
  }, [updateWindowLevel]);

  // ==========================================================================
  // 重置图片就绪状态（供外部调用，如切换文件时）
  // ==========================================================================
  const resetImageReady = useCallback(() => {
    setImageReady(false);
  }, []);

  return {
    windowWidth: windowData.ww,
    windowLevel: windowData.wl,
    imageStats: imageStatsRef.current,
    windowWidthMin: 1,
    windowWidthMax: Math.max(1, Math.round((imageStatsRef.current?.max ?? 255) - (imageStatsRef.current?.min ?? 0))),
    windowLevelMin: Math.floor(imageStatsRef.current?.min ?? 0),
    windowLevelMax: Math.ceil(imageStatsRef.current?.max ?? 255),
    imageReady, // 图片是否已加载并渲染完成
    resetImageReady, // 重置图片就绪状态
    imageWidth,
    imageHeight,
    isSelecting: !!(dragStart && dragCurrent),
    selectionRect: dragStart && dragCurrent ? {
      left: Math.min(dragStart.x, dragCurrent.x),
      top: Math.min(dragStart.y, dragCurrent.y),
      width: Math.abs(dragCurrent.x - dragStart.x),
      height: Math.abs(dragCurrent.y - dragStart.y),
    } : null,
    canvasRef,
    handlers: {
      onMouseDown: handleMouseDown,
      onMouseMove: handleMouseMove,
      onMouseUp: handleMouseUp,
      onMouseLeave: handleMouseUp,
    },
    resetWindow,
    setManualWindowLevel: updateWindowLevel,
  };
};
