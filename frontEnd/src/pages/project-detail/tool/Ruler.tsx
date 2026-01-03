import React, { useRef, useEffect } from 'react';

interface RulerProps {
  type: 'horizontal' | 'vertical';
  scale: number;            // 当前缩放倍数
  offset: number;           // 图片起点相对于容器的偏移量 (px)
  length: number;           // 标尺总长度 (容器宽度或高度)
  ratio?: number;           // 关键参数：原始分辨率 / 显示分辨率 (默认为 1)
  canvasSize?: number;      // 标尺本身的厚度 (px)
}

const Ruler: React.FC<RulerProps> = ({
  type,
  scale,
  offset,
  length,
  ratio = 1, // 默认为 1
  canvasSize = 20
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
    // 目标：在屏幕上，刻度之间的间距保持在 80px 左右，这样文字才放得下
    // 公式: ScreenGap = ImageStep / ratio * scale
    // 推导: ImageStep = ScreenGap * ratio / scale
    const targetScreenGap = 80; 
    const rawStep = targetScreenGap * ratio / scale;

    // 找一个“整齐”的步长 (如 10, 50, 100, 500...)
    const niceSteps = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000];
    let step = niceSteps[niceSteps.length - 1];
    for (const s of niceSteps) {
        if (rawStep <= s) {
            step = s;
            break;
        }
    }

    // 3. 计算可见区域对应的图片坐标范围
    // 屏幕坐标映射公式: Screen = offset + (ImageVal / ratio) * scale
    // 反推图片坐标: ImageVal = (Screen - offset) / scale * ratio
    
    // 计算视口左边界和右边界对应的图片像素值
    const minImageVal = ((0 - offset) / scale) * ratio;
    const maxImageVal = ((length - offset) / scale) * ratio;
    
    // 对齐循环的起始点 (例如从 100, 200 开始，而不是 103, 203)
    const startLoop = Math.floor(minImageVal / step) * step;
    const endLoop = Math.ceil(maxImageVal / step) * step;

    // 4. 循环绘制
    for (let val = startLoop; val <= endLoop; val += step) {
      // 将图片像素坐标映射回屏幕坐标进行绘制
      const screenPos = offset + (val / ratio) * scale;
      
      // 绘制主刻度
      if (type === 'horizontal') {
        ctx.moveTo(screenPos, 0);
        ctx.lineTo(screenPos, canvasSize);
        // 绘制文字 (显示真实的像素值)
        ctx.fillText(Math.round(val).toString(), screenPos + 2, 10); 
      } else {
        ctx.moveTo(0, screenPos);
        ctx.lineTo(canvasSize, screenPos);
        // 垂直文字旋转
        ctx.save();
        ctx.translate(10, screenPos + 10);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText(Math.round(val).toString(), 0, 0);
        ctx.restore();
      }
    }

    ctx.stroke();

  }, [scale, offset, length, type, ratio, canvasSize]);

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