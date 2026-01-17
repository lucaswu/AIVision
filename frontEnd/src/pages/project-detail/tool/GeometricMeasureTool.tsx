import React, { useState, useMemo, useEffect } from 'react'; 
import ReactDOM from 'react-dom';

interface GeometricMeasureToolProps {
  visible: boolean;
  imageUrl: string;
  width: number;
  height: number;
  pixelRatio?: number;
  scale?: number;
  rotation?: number; 
  flipH?: number;    
  flipV?: number;    
  container?: HTMLDivElement | null;
}

const GeometricMeasureTool: React.FC<GeometricMeasureToolProps> = ({
  visible,
  imageUrl,
  width,
  height,
  pixelRatio = 1,
  scale = 1,
  rotation = 0, 
  flipH = 1,    
  flipV = 1,    
  container, 
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [currPoint, setCurrPoint] = useState<{ x: number; y: number } | null>(null);

  const MAGNIFIER_SIZE = 150; 
  const ZOOM_SCALE = 3;       

  //  监听 visible 变化，当工具关闭时，重置所有状态
  useEffect(() => {
    if (!visible) {
      setStartPoint(null);
      setCurrPoint(null);
      setIsDragging(false);
    }
  }, [visible]);

  // 计算真实的图像坐标
  const getCoordinate = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    
    // 1. 获取元素中心点
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    // 2. 计算鼠标相对于中心的偏移量
    const dx = e.clientX - centerX;
    const dy = e.clientY - centerY;

    // 3. 逆变换顺序：先逆缩放/翻转 -> 再逆旋转
    const unscaledX = dx * flipH / scale;
    const unscaledY = dy * flipV / scale;

    const rad = -rotation * (Math.PI / 180);
    const rotatedX = unscaledX * Math.cos(rad) - unscaledY * Math.sin(rad);
    const rotatedY = unscaledX * Math.sin(rad) + unscaledY * Math.cos(rad);

    // 4. 将原点从中心移回左上角
    const finalX = rotatedX + width / 2;
    const finalY = rotatedY + height / 2;

    return {
      x: Math.max(0, Math.min(width, finalX)),
      y: Math.max(0, Math.min(height, finalY))
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

  // 文字位置计算
  const textLayout = useMemo(() => {
    if (!currPoint) return null;

    const screenOffsetX = 15;
    const screenOffsetY = 5;

    // 1. 先逆缩放 & 逆翻转
    const unscaledOffsetX = screenOffsetX * flipH / scale;
    const unscaledOffsetY = screenOffsetY * flipV / scale;

    // 2. 再逆旋转
    const rad = -rotation * (Math.PI / 180);
    const localOffsetX = unscaledOffsetX * Math.cos(rad) - unscaledOffsetY * Math.sin(rad);
    const localOffsetY = unscaledOffsetX * Math.sin(rad) + unscaledOffsetY * Math.cos(rad);

    const tx = currPoint.x + localOffsetX;
    const ty = currPoint.y + localOffsetY;

    const transformStr = `rotate(${-rotation}, ${tx}, ${ty}) translate(${tx}, ${ty}) scale(${flipH}, ${flipV}) translate(${-tx}, ${-ty})`;

    return { x: tx, y: ty, transform: transformStr };
  }, [currPoint, rotation, flipH, flipV, scale]);

  if (!visible) return null;

  const portalTarget = container || document.body;

  const magnifierStyle: React.CSSProperties = {
    position: container ? 'absolute' : 'fixed', 
    left: container ? 10 : 310,  
    top: container ? 10 : 58,   
    width: MAGNIFIER_SIZE,
    height: MAGNIFIER_SIZE,
    border: '2px solid #fff',
    borderRadius: '4px',
    overflow: 'hidden',
    backgroundColor: '#000',
    boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
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
            {/* 十字准星 */}
            <line x1={startPoint.x - 4 / scale} y1={startPoint.y} x2={startPoint.x + 4 / scale} y2={startPoint.y} stroke="red" strokeWidth={1 / scale} />
            <line x1={startPoint.x} y1={startPoint.y - 4 / scale} x2={startPoint.x} y2={startPoint.y + 4 / scale} stroke="red" strokeWidth={1 / scale} />
            <line x1={currPoint.x - 4 / scale} y1={currPoint.y} x2={currPoint.x + 4 / scale} y2={currPoint.y} stroke="red" strokeWidth={1 / scale} />
            <line x1={currPoint.x} y1={currPoint.y - 4 / scale} x2={currPoint.x} y2={currPoint.y + 4 / scale} stroke="red" strokeWidth={1 / scale} />
            
            {measureData && textLayout && (
              <text 
                x={textLayout.x} 
                y={textLayout.y} 
                fill="red" 
                fontSize={12 / scale} 
                style={{ textShadow: '1px 1px 2px #000' }}
                transform={textLayout.transform}
              >
                <tspan x={textLayout.x} dy={-1.2 * (12 / scale) + "px"}>长度: {measureData.length}mm</tspan>
                <tspan x={textLayout.x} dy={2.4 * (12 / scale) + "px"}>角度: {measureData.angle}°</tspan>
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
              backgroundSize: `${width * ZOOM_SCALE}px ${height * ZOOM_SCALE}px`,
              backgroundPosition: `
                ${-currPoint.x * ZOOM_SCALE + MAGNIFIER_SIZE / 2}px 
                ${-currPoint.y * ZOOM_SCALE + MAGNIFIER_SIZE / 2}px
              `,
            }}
          />
          <div style={{ position: 'absolute', top: '50%', left: 0, width: '100%', height: 1, background: 'rgba(255,0,0,0.5)' }} />
          <div style={{ position: 'absolute', left: '50%', top: 0, width: 1, height: '100%', background: 'rgba(255,0,0,0.5)' }} />
        </div>,
        portalTarget 
      )}
    </div>
  );
};

export default GeometricMeasureTool;