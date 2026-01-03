import React, { useState, useMemo } from 'react';
import ReactDOM from 'react-dom';

interface GeometricMeasureToolProps {
  visible: boolean;
  imageUrl: string;
  width: number;
  height: number;
  pixelRatio?: number;
  scale?: number;
  container?: HTMLDivElement | null;
}

const GeometricMeasureTool: React.FC<GeometricMeasureToolProps> = ({
  visible,
  imageUrl,
  width,
  height,
  pixelRatio = 1,
  scale = 1,
  container, 
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [currPoint, setCurrPoint] = useState<{ x: number; y: number } | null>(null);

  const MAGNIFIER_SIZE = 150; 
  const ZOOM_SCALE = 3;       

  const getCoordinate = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / scale;
    const y = (e.clientY - rect.top) / scale;
    return {
      x: Math.max(0, Math.min(width, x)),
      y: Math.max(0, Math.min(height, y))
    };
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const point = getCoordinate(e);
    setStartPoint(point);
    setCurrPoint(point);
    setIsDragging(true);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const point = getCoordinate(e);
    setCurrPoint(point);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const measureData = useMemo(() => {
    if (!startPoint || !currPoint) return null;
    const dx = currPoint.x - startPoint.x;
    const dy = currPoint.y - startPoint.y;

    const distPx = Math.sqrt(dx * dx + dy * dy);
    const lengthMm = (distPx * pixelRatio).toFixed(2);
    let angleVal = Math.abs((Math.atan(dy / dx) * 180) / Math.PI);
    if (isNaN(angleVal)) angleVal = 0;

    return {
      length: lengthMm,
      angle: angleVal.toFixed(2),
    };
  }, [startPoint, currPoint, pixelRatio]);

  if (!visible) return null;

  const portalTarget = container || document.body;

  // 2. 动态计算样式
  const magnifierStyle: React.CSSProperties = container ? {
    // 方案 A：成功获取到容器
    position: 'absolute', // 相对于父容器(灰色背景)定位
    left: 10,  
    top: 10,   
    width: MAGNIFIER_SIZE,
    height: MAGNIFIER_SIZE,
    border: '2px solid #fff',
    borderRadius: '4px',
    overflow: 'hidden',
    backgroundColor: '#000',
    boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
    zIndex: 9999,
    pointerEvents: 'none', 
  } : {
    // 方案 B：未获取到容器（降级方案，防止报错）
    position: 'fixed', 
    left: 310, 
    top: 58,   
    width: MAGNIFIER_SIZE,
    height: MAGNIFIER_SIZE,
    border: '2px solid #fff',
    borderRadius: '4px',
    overflow: 'hidden',
    backgroundColor: '#000',
    zIndex: 9999, 
    pointerEvents: 'none',
  };

  return (
    <div
      style={{
        position: 'absolute',
        top: 0, left: 0, width: '100%', height: '100%',
        zIndex: 20,
        cursor: 'crosshair',
        userSelect: 'none',
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <svg width="100%" height="100%" style={{ position: 'absolute', pointerEvents: 'none' }}>
        {startPoint && currPoint && (
          <>
            <line
              x1={startPoint.x} y1={startPoint.y}
              x2={currPoint.x} y2={currPoint.y}
              stroke="red" 
              strokeWidth={1.5 / scale} 
            />
            {/* 十字准星装饰线 */}
            <line x1={startPoint.x - 4 / scale} y1={startPoint.y} x2={startPoint.x + 4 / scale} y2={startPoint.y} stroke="red" strokeWidth={1 / scale} />
            <line x1={startPoint.x} y1={startPoint.y - 4 / scale} x2={startPoint.x} y2={startPoint.y + 4 / scale} stroke="red" strokeWidth={1 / scale} />
            <line x1={currPoint.x - 4 / scale} y1={currPoint.y} x2={currPoint.x + 4 / scale} y2={currPoint.y} stroke="red" strokeWidth={1 / scale} />
            <line x1={currPoint.x} y1={currPoint.y - 4 / scale} x2={currPoint.x} y2={currPoint.y + 4 / scale} stroke="red" strokeWidth={1 / scale} />
            
            {measureData && (
              <text 
                x={currPoint.x + 15 / scale} 
                y={currPoint.y + 5 / scale} 
                fill="red" 
                fontSize={12 / scale} 
                style={{ textShadow: '1px 1px 2px #000' }}
              >
                <tspan x={currPoint.x + 15 / scale} dy={-1.2 * (12 / scale) + "px"}>长度: {measureData.length}mm</tspan>
                <tspan x={currPoint.x + 15 / scale} dy={2.4 * (12 / scale) + "px"}>角度: {measureData.angle}°</tspan>
              </text>
            )}
          </>
        )}
      </svg>

      {/* 渲染放大镜 Portal */}
      {isDragging && currPoint && ReactDOM.createPortal(
        <div style={magnifierStyle}>
          <div
            style={{
              width: '100%', height: '100%',
              backgroundImage: `url(${imageUrl})`,
              backgroundRepeat: 'no-repeat',
              // 背景图大小需要根据缩放比例计算
              backgroundSize: `${width * ZOOM_SCALE}px ${height * ZOOM_SCALE}px`,
              // 背景图位置：让当前鼠标点对应的图像位置居中显示
              backgroundPosition: `
                ${-currPoint.x * ZOOM_SCALE + MAGNIFIER_SIZE / 2}px 
                ${-currPoint.y * ZOOM_SCALE + MAGNIFIER_SIZE / 2}px
              `,
            }}
          />
          {/* 放大镜中心的红色十字线 */}
          <div style={{ position: 'absolute', top: '50%', left: 0, width: '100%', height: 1, background: 'rgba(255,0,0,0.5)' }} />
          <div style={{ position: 'absolute', left: '50%', top: 0, width: 1, height: '100%', background: 'rgba(255,0,0,0.5)' }} />
        </div>,
        portalTarget 
      )}
    </div>
  );
};

export default GeometricMeasureTool;