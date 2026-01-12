import React, { useRef, useEffect } from 'react';

interface RulerProps {
  type: 'horizontal' | 'vertical';
  scale: number;            // 当前缩放倍数
  offset: number;           // 图片起点相对于容器的偏移量 (px)
  length: number;           // 标尺总长度 (容器宽度或高度)
  ratio?: number;           // 关键参数：原始分辨率 / 显示分辨率 (默认为 1)
  canvasSize?: number;      // 标尺本身的厚度 (px)
  maxImageSize?: number;    //  图片的原始最大尺寸 (px)
}

const Ruler: React.FC<RulerProps> = ({
  type,
  scale,
  offset,
  length,
  ratio = 1, 
  canvasSize = 20,
  maxImageSize = 0 //  默认为 0，但实际上父组件应该传入有效值
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 1. 清空与背景设置
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#1f1f1f'; 
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    ctx.strokeStyle = '#fdf7f7ff';
    ctx.fillStyle = '#f1eeeeff'; 
    ctx.font = '10px sans-serif';
    ctx.lineWidth = 1;
    ctx.beginPath();

    // 2. 动态计算刻度步长 (Step)
    const targetScreenGap = 80; 
    const rawStep = targetScreenGap * ratio / scale;

    const niceSteps = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000];
    let step = niceSteps[niceSteps.length - 1];
    for (const s of niceSteps) {
        if (rawStep <= s) {
            step = s;
            break;
        }
    }

    // 3. 计算可见区域对应的图片坐标范围
    const minImageVal = ((0 - offset) / scale) * ratio;
    const maxImageVal = ((length - offset) / scale) * ratio;
    
    const startLoop = Math.floor(minImageVal / step) * step;
    const endLoop = Math.ceil(maxImageVal / step) * step;

    // 4. 循环绘制
    for (let val = startLoop; val <= endLoop; val += step) {
      //如果在图片范围之外 (小于0 或 大于最大尺寸)，则跳过不绘制
      // 注意：这里使用 loose check，允许一定的浮点误差，或者严格拦截
      if (val < 0 || (maxImageSize > 0 && val > maxImageSize)) {
        continue;
      }

      // 将图片像素坐标映射回屏幕坐标进行绘制
      const screenPos = offset + (val / ratio) * scale;
      
      // 绘制主刻度
      if (type === 'horizontal') {
        ctx.moveTo(screenPos, 0);
        ctx.lineTo(screenPos, canvasSize);
        ctx.fillText(Math.round(val).toString(), screenPos + 2, 10); 
      } else {
        ctx.moveTo(0, screenPos);
        ctx.lineTo(canvasSize, screenPos);
        ctx.save();
        ctx.translate(10, screenPos + 10);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText(Math.round(val).toString(), 0, 0);
        ctx.restore();
      }
    }

    // 绘制图片结束的边界线，让用户清楚知道哪里是终点
    if (maxImageSize > 0) {
       const endScreenPos = offset + (maxImageSize / ratio) * scale;
       // 只有当结束线在可视范围内才绘制
       if (endScreenPos >= 0 && endScreenPos <= length) {
           ctx.strokeStyle = '#ff4d4f'; // 使用红色或其他颜色标记边界
           ctx.beginPath();
           if (type === 'horizontal') {
               ctx.moveTo(endScreenPos, 0);
               ctx.lineTo(endScreenPos, canvasSize);
           } else {
               ctx.moveTo(0, endScreenPos);
               ctx.lineTo(canvasSize, endScreenPos);
           }
           ctx.stroke();
           ctx.strokeStyle = '#fdf7f7ff'; // 还原颜色
       }
    }

    ctx.stroke();

  }, [scale, offset, length, type, ratio, canvasSize, maxImageSize]); // 依赖项加入 maxImageSize

  return (
    <canvas
      ref={canvasRef}
      width={type === 'horizontal' ? length : canvasSize}
      height={type === 'horizontal' ? canvasSize : length}
      style={{ display: 'block' }}
    />
  );
};

export default Ruler;