import { useState, useRef, useCallback } from 'react';
import { message } from 'antd';

// SVG 滤镜参数
interface WindowLevelParams {
  slope: number;
  intercept: number;
}

// Hook 入参
interface UseWindowLevelToolProps {
  activeTool: string;       // 当前激活的工具
  scale: number;            // 当前缩放倍数
  imageUrl?: string;        // 图片地址（用于重置或校验）
}

export const useWindowLevelTool = ({ activeTool, scale }: UseWindowLevelToolProps) => {
  // 1. 维护直观的窗宽窗位数值状态 (默认全宽: 255, 中间位: 128)
  // ww: Window Width, wl: Window Level
  const [windowData, setWindowData] = useState({ ww: 255, wl: 128 });

  // 2. 核心状态：SVG滤镜参数 (由 ww/wl 计算得出)
  const [windowParams, setWindowParams] = useState<WindowLevelParams>({ slope: 1, intercept: 0 });
  
  // 3. 交互状态：鼠标拖拽 ROI
  const [dragStart, setDragStart] = useState<{ x: number, y: number } | null>(null);
  const [dragCurrent, setDragCurrent] = useState<{ x: number, y: number } | null>(null);
  
  // 引用图片元素，用于 Canvas 读取像素
  const imgRef = useRef<HTMLImageElement>(null);
  // 用于节流的时间戳
  const lastCalcTime = useRef<number>(0);

  // --------------------------------------------------------------------------
  // 统一更新函数：根据新的 WW 和 WL，计算 SVG 参数并更新所有状态
  // --------------------------------------------------------------------------
  const updateWindowLevel = useCallback((newWW: number, newWL: number) => {
    // 限制范围，防止除以0 (最小窗宽设为1)
    const w = Math.max(1, newWW);
    const l = newWL;

    // SVG feComponentTransfer 线性变换公式推导：
    // 目标: 将 [L - W/2, L + W/2] 映射到 [0, 1] (或0-255)
    // y = (x - (L - W/2)) * (1/W)  <-- 归一化域
    // y = x * (1/W) - (L/W - 0.5)
    // 对应 SVG linear: slope * x + intercept
    
    // 这里我们基于 0-1 范围计算 slope，但在 Web SVG Filter 中：
    // 如果 slope = 255/W，intercept = 0.5 - L/W，通常能得到正确视觉效果
    // (前提是输入像素已经被视为 0-1 范围)
    
    const slope = 255 / w;
    const intercept = 0.5 - (l / w);

    // 同步更新数值状态 (给 UI 滑块用)
    setWindowData({ ww: Math.round(w), wl: Math.round(l) });
    // 同步更新滤镜参数 (给 SVG 用)
    setWindowParams({ slope, intercept });
  }, []);
  

  // 重置功能 (恢复到原始线性映射)
  const resetWindow = useCallback(() => {
    updateWindowLevel(255, 128);
    message.info('窗宽窗位已重置');
  }, [updateWindowLevel]);


  // 手动设置功能 (供 Slider 使用)
  const setManualWindowLevel = useCallback((ww: number, wl: number) => {
    updateWindowLevel(ww, wl);
  }, [updateWindowLevel]);


  // --------------------------------------------------------------------------
  // 核心算法：计算 ROI 区域的均值和标准差，并自动应用
  // --------------------------------------------------------------------------
  const computeROI = useCallback((startX: number, startY: number, endX: number, endY: number, isRealtime: boolean = false) => {
    const img = imgRef.current;
    if (!img) return;

    // 1. 创建离屏 Canvas 读取像素
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    try {
      ctx.drawImage(img, 0, 0);
    } catch (e) {
      console.error("CORS Error", e);
      return;
    }

    // 2. 坐标转换
    // startX/Y 已经是相对于 imageWrapper 的坐标(未除scale前)，但我们在 MouseMove 里已经除过 scale 了
    // 所以传入 computeROI 的已经是“容器内坐标”
    const displayWidth = img.width; 
    const displayHeight = img.height;
    
    const rawX = Math.min(startX, endX);
    const rawY = Math.min(startY, endY);
    const rawW = Math.abs(endX - startX);
    const rawH = Math.abs(endY - startY);

    // 映射到原始图片分辨率
    const ratioX = img.naturalWidth / displayWidth;
    const ratioY = img.naturalHeight / displayHeight;

    const finalX = rawX * ratioX;
    const finalY = rawY * ratioY;
    const finalW = rawW * ratioX;
    const finalH = rawH * ratioY;

    // 区域太小不计算
    if (finalW <= 2 || finalH <= 2) return;

    // 3. 获取像素数据
    const imageData = ctx.getImageData(finalX, finalY, finalW, finalH).data;
    
    // 4. 统计计算
    let sum = 0;
    let count = 0;
    const values: number[] = [];
    
    // 性能优化: 实时拖动时降采样 (每10个像素取1个)，松手时全采样(每1个)
    const step = isRealtime ? 10 : 1; 

    // imageData 是 [R, G, B, A, ...] 格式，每像素占4位
    // 每次循环跳过 4 * step
    for (let i = 0; i < imageData.length; i += (4 * step)) {
        const val = imageData[i]; // 取 R 通道 (灰度图 R=G=B)
        values.push(val);
        sum += val;
        count++;
    }

    if (count === 0) return;

    const mean = sum / count; // 窗位 (Level)

    let sumSqDiff = 0;
    for (let v of values) {
        sumSqDiff += (v - mean) ** 2;
    }
    const std = Math.sqrt(sumSqDiff / count);
    
    // 窗宽 (Width) = 4倍标准差 (覆盖约95%像素)
    const calcWW = Math.max(10, 4 * std);
    const calcWL = mean;

    // 5. 应用计算结果
    updateWindowLevel(calcWW, calcWL);

    // 仅在松手时提示，避免刷屏
    if (!isRealtime) {
        message.destroy(); 
        message.success(`ROI调整: 窗位 ${calcWL.toFixed(0)} / 窗宽 ${calcWW.toFixed(0)}`);
    }

  }, [updateWindowLevel]); // 依赖 updateWindowLevel

  // --------------------------------------------------------------------------
  // 鼠标事件处理 (绑定到容器 div)
  // --------------------------------------------------------------------------
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool !== 'windowing') return;
    
    e.preventDefault(); 
    e.stopPropagation();

    const rect = e.currentTarget.getBoundingClientRect();
    
    // 坐标除以 scale，抵消 CSS transform: scale() 的影响
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
    
    // 节流计算 (40ms ≈ 25fps)
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

    // 鼠标松开，做一次高精度计算
    computeROI(dragStart.x, dragStart.y, dragCurrent.x, dragCurrent.y, false);

    setDragStart(null);
    setDragCurrent(null);
  }, [activeTool, dragStart, dragCurrent, computeROI]);

  // 返回 API
  return {
    // 状态
    windowParams,      // 给 SVG Filter 用
    windowWidth: windowData.ww, // 给 UI Slider 用
    windowLevel: windowData.wl, // 给 UI Slider 用
    
    // 交互状态
    isSelecting: !!(dragStart && dragCurrent),
    selectionRect: dragStart && dragCurrent ? {
        left: Math.min(dragStart.x, dragCurrent.x),
        top: Math.min(dragStart.y, dragCurrent.y),
        width: Math.abs(dragCurrent.x - dragStart.x),
        height: Math.abs(dragCurrent.y - dragStart.y),
    } : null,
    
    // 引用与绑定
    imgRef, 
    handlers: {
        onMouseDown: handleMouseDown,
        onMouseMove: handleMouseMove,
        onMouseUp: handleMouseUp,
        onMouseLeave: handleMouseUp
    },

    // 操作方法
    resetWindow,
    setManualWindowLevel
  };
};

// --------------------------------------------------------------------------
// SVG Filter 组件 (无逻辑，纯渲染)
// --------------------------------------------------------------------------
export const WindowLevelSVGFilter = ({ id, slope, intercept }: { id: string } & WindowLevelParams) => (
  <svg style={{ position: 'absolute', width: 0, height: 0, pointerEvents: 'none' }}>
    <defs>
      <filter id={id}>
        <feComponentTransfer>
          <feFuncR type="linear" slope={slope} intercept={intercept} />
          <feFuncG type="linear" slope={slope} intercept={intercept} />
          <feFuncB type="linear" slope={slope} intercept={intercept} />
        </feComponentTransfer>
      </filter>
    </defs>
  </svg>
);