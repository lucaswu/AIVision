import { useState, useRef, useCallback, useEffect } from 'react';
import { message } from 'antd';

// Hook 入参
interface UseWindowLevelToolProps {
  activeTool: string;
  scale: number;
  imageFile?: File;
}

interface ImageStats {
  mean: number;
  std: number;
  min: number;
  max: number;
}

export const useWindowLevelTool = ({ activeTool, scale, imageFile }: UseWindowLevelToolProps) => {
  // 原始灰度数据（真正的原始数据）
  const [rawGrayData, setRawGrayData] = useState<Uint8Array | null>(null);
  const [imageWidth, setImageWidth] = useState(0);
  const [imageHeight, setImageHeight] = useState(0);
  
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
  // 辅助函数：从灰度数组计算统计信息
  // ==========================================================================
  const calculateStatsFromGrayData = useCallback((
    data: Uint8Array,
    x: number = 0,
    y: number = 0,
    w: number = -1,
    h: number = -1,
    imgWidth: number = 0,
    step: number = 1
  ): ImageStats | null => {
    // 如果未指定区域，使用全图
    const width = w === -1 ? imgWidth : w;
    const height = h === -1 ? data.length / imgWidth : h;
    
    let sum = 0;
    let count = 0;
    const values: number[] = [];
    let min = 255;
    let max = 0;

    for (let row = y; row < y + height; row += step) {
      for (let col = x; col < x + width; col += step) {
        const index = row * imgWidth + col;
        
        if (index >= 0 && index < data.length) {
          const val = data[index];
          values.push(val);
          sum += val;
          
          if (val < min) min = val;
          if (val > max) max = val;
          
          count++;
        }
      }
    }

    if (count === 0) return null;

    const mean = sum / count;
    let sumSqDiff = 0;
    for (const v of values) {
      sumSqDiff += (v - mean) ** 2;
    }
    const std = Math.sqrt(sumSqDiff / count);

    return { mean, std, min, max };
  }, []);

  // ==========================================================================
  // 核心：在原始灰度数据上应用窗宽窗位
  // ==========================================================================
  const applyWindowLevelToGrayData = useCallback((
    data: Uint8Array,
    ww: number,
    wl: number
  ): Uint8Array => {
    const window_min = wl - ww / 2;
    const window_max = wl + ww / 2;
    const result = new Uint8Array(data.length);
    
    for (let i = 0; i < data.length; i++) {
      const val = data[i];
      
      if (val <= window_min) {
        result[i] = 0;
      } else if (val >= window_max) {
        result[i] = 255;
      } else {
        result[i] = Math.round(((val - window_min) / ww) * 255);
      }
    }
    
    return result;
  }, []);

  // ==========================================================================
  // 渲染：将处理后的灰度数据绘制到Canvas
  // ==========================================================================
  const renderToCanvas = useCallback((processedData: Uint8Array) => {
    const canvas = canvasRef.current;
    if (!canvas || !processedData || imageWidth === 0 || imageHeight === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 设置Canvas尺寸
    canvas.width = imageWidth;
    canvas.height = imageHeight;

    // 创建RGBA ImageData
    const imageData = new ImageData(imageWidth, imageHeight);
    const rgbaData = imageData.data;
    
    for (let i = 0; i < processedData.length; i++) {
      const idx = i * 4;
      const gray = processedData[i];
      rgbaData[idx] = gray;     // R
      rgbaData[idx + 1] = gray; // G
      rgbaData[idx + 2] = gray; // B
      rgbaData[idx + 3] = 255;  // A
    }
    
    ctx.putImageData(imageData, 0, 0);
  }, [imageWidth, imageHeight]);

  // ==========================================================================
  // 更新显示
  // ==========================================================================
  const updateDisplay = useCallback(() => {
    if (!rawGrayData) return;
    
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
    
    const w = Math.max(1, newWW);
    
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
    if (!imageFile) return;

    const loadImage = async () => {
      try {
        // 创建临时Image对象加载
        const img = new Image();
        const url = URL.createObjectURL(imageFile);
        
        await new Promise<void>((resolve, reject) => {
          img.onload = () => resolve();
          img.onerror = reject;
          img.src = url;
        });

        const width = img.naturalWidth;
        const height = img.naturalHeight;

        // 使用临时Canvas提取像素数据
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = width;
        tempCanvas.height = height;
        
        const tempCtx = tempCanvas.getContext('2d', {
          willReadFrequently: true,
        });
        
        if (!tempCtx) {
          throw new Error('无法创建Canvas上下文');
        }

        // 绘制图像
        tempCtx.drawImage(img, 0, 0);
        
        // 获取RGBA数据
        const imageData = tempCtx.getImageData(0, 0, width, height);
        const rgbaData = imageData.data;
        
        // 转换为单通道灰度数据（这才是真正的"原始数据"）
        const grayData = new Uint8Array(width * height);
        for (let i = 0; i < grayData.length; i++) {
          const idx = i * 4;
          // 使用标准灰度转换公式
          grayData[i] = Math.round(
            0.299 * rgbaData[idx] +
            0.587 * rgbaData[idx + 1] +
            0.114 * rgbaData[idx + 2]
          );
        }

        // 保存原始数据
        setRawGrayData(grayData);
        setImageWidth(width);
        setImageHeight(height);

        // 计算全图统计
        const stats = calculateStatsFromGrayData(grayData, 0, 0, -1, -1, width, 2);
        
        if (stats) {
          imageStatsRef.current = stats;
          
          // 应用自动窗位
          const autoWW = Math.max(1, Math.min(4 * stats.std, stats.max - stats.min));
          const autoWL = stats.mean;
          
          console.log(`图像加载完成: ${width}x${height}`);
          console.log(`像素范围: [${stats.min}, ${stats.max}]`);
          console.log(`均值: ${stats.mean.toFixed(2)}, 标准差: ${stats.std.toFixed(2)}`);
          console.log(`自动窗宽窗位: WW=${autoWW.toFixed(1)}, WL=${autoWL.toFixed(1)}`);
          
          updateWindowLevel(autoWW, autoWL);
        } else {
          updateWindowLevel(255, 128);
        }

        URL.revokeObjectURL(url);
        
      } catch (error) {
        console.error('图像加载失败:', error);
        message.error('图像加载失败');
      }
    };

    loadImage();
  }, [imageFile, calculateStatsFromGrayData, updateWindowLevel]);

  // 监听窗宽窗位变化，更新显示
  useEffect(() => {
    updateDisplay();
  }, [updateDisplay]);

  // ==========================================================================
  // 🔧 修复：ROI 计算 - 添加坐标转换
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

    // 🔑 关键修复：获取Canvas的显示尺寸
    const displayWidth = canvas.clientWidth;
    const displayHeight = canvas.clientHeight;
    
    // 🔑 关键修复：计算显示尺寸与原始尺寸的比例
    const scaleX = imageWidth / displayWidth;
    const scaleY = imageHeight / displayHeight;

    // 计算显示坐标系中的ROI
    const rawX = Math.min(startX, endX);
    const rawY = Math.min(startY, endY);
    const rawW = Math.abs(endX - startX);
    const rawH = Math.abs(endY - startY);

    if (rawW <= 2 || rawH <= 2) return;

    // 🔑 关键修复：转换到原始图像坐标系
    const imageX = Math.floor(rawX * scaleX);
    const imageY = Math.floor(rawY * scaleY);
    const imageW = Math.floor(rawW * scaleX);
    const imageH = Math.floor(rawH * scaleY);

    // 限制在图像范围内
    const finalX = Math.max(0, Math.min(imageX, imageWidth - 1));
    const finalY = Math.max(0, Math.min(imageY, imageHeight - 1));
    const finalW = Math.min(imageW, imageWidth - finalX);
    const finalH = Math.min(imageH, imageHeight - finalY);

    console.log('ROI坐标转换:', {
      显示坐标: { x: rawX, y: rawY, w: rawW, h: rawH },
      显示尺寸: { w: displayWidth, h: displayHeight },
      原始尺寸: { w: imageWidth, h: imageHeight },
      缩放比例: { x: scaleX.toFixed(2), y: scaleY.toFixed(2) },
      图像坐标: { x: finalX, y: finalY, w: finalW, h: finalH }
    });

    const step = isRealtime ? 3 : 1;

    const stats = calculateStatsFromGrayData(
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
      // message.success(
      //   `ROI调整: 窗位 ${calcWL.toFixed(0)} / 窗宽 ${calcWW.toFixed(0)} ` +
      //   `(范围: [${stats.min}, ${stats.max}])`
      // );
    }
  }, [rawGrayData, imageWidth, imageHeight, calculateStatsFromGrayData, updateWindowLevel]);

  // ==========================================================================
  // 鼠标事件
  // ==========================================================================
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool !== 'windowing') return;
    
    e.preventDefault();
    e.stopPropagation();

    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / scale;
    const y = (e.clientY - rect.top) / scale;

    setDragStart({ x, y });
    setDragCurrent({ x, y });
  }, [activeTool, scale]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool !== 'windowing' || !dragStart) return;
    
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / scale;
    const y = (e.clientY - rect.top) / scale;

    setDragCurrent({ x, y });
    
    const now = Date.now();
    if (now - lastCalcTime.current > 40) {
      computeROI(dragStart.x, dragStart.y, x, y, true);
      lastCalcTime.current = now;
    }
  }, [activeTool, dragStart, scale, computeROI]);

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
      // message.info(
      //   `窗宽窗位已重置 (WW=${resetWW.toFixed(0)}, WL=${resetWL.toFixed(0)})`
      // );
    } else {
      updateWindowLevel(255, 128);
      // message.info('窗宽窗位已重置');
    }
  }, [updateWindowLevel]);

  return {
    windowWidth: windowData.ww,
    windowLevel: windowData.wl,
    imageStats: imageStatsRef.current,
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
