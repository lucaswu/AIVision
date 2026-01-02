import React, { useState, useMemo } from 'react';

interface GeometricMeasureToolProps {
  visible: boolean;
  imageUrl: string;
  width: number;
  height: number;
  pixelRatio?: number; // 像素/毫米 比例
}

const GeometricMeasureTool: React.FC<GeometricMeasureToolProps> = ({
  visible,
  imageUrl,
  width,
  height,
  pixelRatio = 1, 
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [currPoint, setCurrPoint] = useState<{ x: number; y: number } | null>(null);

  // 放大镜配置
  const MAGNIFIER_SIZE = 150; 
  const ZOOM_SCALE = 3;       

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault(); // 阻止默认事件
    e.stopPropagation(); // 阻止冒泡，防止触发外层的平移
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setStartPoint({ x, y });
    setCurrPoint({ x, y });
    setIsDragging(true);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(width, e.clientX - rect.left));
    const y = Math.max(0, Math.min(height, e.clientY - rect.top));
    setCurrPoint({ x, y });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const measureData = useMemo(() => {
    if (!startPoint || !currPoint) return null;
    const dx = currPoint.x - startPoint.x;
    const dy = currPoint.y - startPoint.y;

    // 1. 长度 (修正为保留2位小数)
    const distPx = Math.sqrt(dx * dx + dy * dy);
    const lengthMm = (distPx * pixelRatio).toFixed(2);

    // 2. 角度 (0->90->0->90, 修正为保留2位小数)
    let angleVal = Math.abs((Math.atan(dy / dx) * 180) / Math.PI);
    if (isNaN(angleVal)) angleVal = 0;

    return {
      length: lengthMm,
      angle: angleVal.toFixed(2),
    };
  }, [startPoint, currPoint, pixelRatio]);

  if (!visible) return null;

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
              stroke="red" strokeWidth="1.5"
            />
            {/* 十字标记稍微缩小一点，更精致 */}
            <line x1={startPoint.x - 4} y1={startPoint.y} x2={startPoint.x + 4} y2={startPoint.y} stroke="red" strokeWidth="1" />
            <line x1={startPoint.x} y1={startPoint.y - 4} x2={startPoint.x} y2={startPoint.y + 4} stroke="red" strokeWidth="1" />
            
            <line x1={currPoint.x - 4} y1={currPoint.y} x2={currPoint.x + 4} y2={currPoint.y} stroke="red" strokeWidth="1" />
            <line x1={currPoint.x} y1={currPoint.y - 4} x2={currPoint.x} y2={currPoint.y + 4} stroke="red" strokeWidth="1" />
            
            {measureData && (
              <text x={currPoint.x + 15} y={currPoint.y + 5} fill="red" fontSize="12" style={{ textShadow: '1px 1px 2px #000' }}>
                <tspan x={currPoint.x + 15} dy="-1.2em">长度: {measureData.length}mm</tspan>
                <tspan x={currPoint.x + 15} dy="1.2em">角度: {measureData.angle}°</tspan>
              </text>
            )}
          </>
        )}
      </svg>

      {isDragging && currPoint && (
        <div
          style={{
            // [修复 1] 位置改为 absolute，相对于父容器(即图片)定位
            position: 'absolute', 
            // [修复 1] 固定在左上角
            top: 0, 
            left: 0, 
            width: MAGNIFIER_SIZE,
            height: MAGNIFIER_SIZE,
            border: '2px solid #fff', // 加粗一点边框防止和背景混淆
            borderRadius: '4px',
            overflow: 'hidden',
            backgroundColor: '#000',
            boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
            zIndex: 30, // 确保在红线之上
            pointerEvents: 'none'
          }}
        >
          <div
            style={{
              width: '100%', height: '100%',
              backgroundImage: `url(${imageUrl})`,
              backgroundRepeat: 'no-repeat',
              backgroundSize: `${width * ZOOM_SCALE}px ${height * ZOOM_SCALE}px`,
              backgroundPosition: `
                ${-currPoint.x * ZOOM_SCALE + MAGNIFIER_SIZE / 2}px 
                ${-currPoint.y * ZOOM_SCALE + MAGNIFIER_SIZE / 2}px
              `,
            }}
          />
          {/* 十字准星不变 */}
          <div style={{ position: 'absolute', top: '50%', left: 0, width: '100%', height: 1, background: 'rgba(255,0,0,0.5)' }} />
          <div style={{ position: 'absolute', left: '50%', top: 0, width: 1, height: '100%', background: 'rgba(255,0,0,0.5)' }} />
        </div>
      )}
    </div>
  );
};

export default GeometricMeasureTool;