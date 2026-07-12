/**
 * D4 方向模型：90° 倍数旋转 + 水平翻转的规范形。
 *
 * 约定与 CorrectionRotation/CorrectionFlip（以及 ImageEditorViewer 中
 * forwardTransformPoint/inverseTransformPoint）完全一致：
 *   显示结果 = 先旋转 rotation（顺时针为正），再水平翻转（flip 为 true 时）。
 *
 * 任意"旋转 90° 倍数 + 水平/垂直翻转"的组合都可归一到该形式
 * （垂直翻转 ≡ 旋转 180° + 水平翻转），因此两个字段即可无损表达全部 8 种方向。
 */

export type RightAngle = 0 | 90 | 180 | 270;

export interface Orientation {
  rotation: RightAngle;
  flip: boolean;
}

export const IDENTITY_ORIENTATION: Orientation = { rotation: 0, flip: false };

export function normalizeRotation(deg: number): RightAngle {
  return ((((deg % 360) + 360) % 360)) as RightAngle;
}

export function orientationsEqual(a: Orientation, b: Orientation): boolean {
  return a.rotation === b.rotation && a.flip === b.flip;
}

/** 从矫正字段（可能为 null/undefined/-90）构造规范方向 */
export function orientationFromCorrection(
  rotation?: number | null,
  flip?: boolean | null
): Orientation {
  return { rotation: normalizeRotation(rotation ?? 0), flip: !!flip };
}

/**
 * 在当前显示结果之上追加屏幕旋转 delta（度，顺时针为正）。
 * 组合恒等式：R(Δ)∘F = F∘R(-Δ)，翻转态下内部旋转角反向，
 * 保证按钮的视觉方向（屏幕上的左旋/右旋）在镜像状态下依然符合直觉。
 */
export function rotateOrientation(o: Orientation, delta: number): Orientation {
  return {
    rotation: normalizeRotation(o.rotation + (o.flip ? -delta : delta)),
    flip: o.flip,
  };
}

/** 在当前显示结果之上追加屏幕水平翻转 */
export function flipOrientationH(o: Orientation): Orientation {
  return { rotation: o.rotation, flip: !o.flip };
}

/** 在当前显示结果之上追加屏幕垂直翻转（≡ 水平翻转 + 180° 旋转） */
export function flipOrientationV(o: Orientation): Orientation {
  return { rotation: normalizeRotation(o.rotation + 180), flip: !o.flip };
}

/** 方向作用后的画幅尺寸（90/270 时宽高互换） */
export function orientedSize(
  w: number,
  h: number,
  o: Orientation
): { w: number; h: number } {
  return o.rotation === 90 || o.rotation === 270 ? { w: h, h: w } : { w, h };
}

/**
 * 将源坐标系（宽 srcW、高 srcH）中的点变换到该方向的显示坐标系。
 * 与 ImageEditorViewer 中 forwardTransformPoint 的数学定义一致。
 */
export function applyOrientationToPoint(
  px: number,
  py: number,
  srcW: number,
  srcH: number,
  o: Orientation
): { x: number; y: number } {
  const r = o.rotation;
  let x: number, y: number;
  if (r === 0) { x = px; y = py; }
  else if (r === 90) { x = srcH - py; y = px; }
  else if (r === 180) { x = srcW - px; y = srcH - py; }
  else /* 270 */ { x = py; y = srcW - px; }
  if (o.flip) {
    const outW = r === 90 || r === 270 ? srcH : srcW;
    x = outW - x;
  }
  return { x, y };
}

/**
 * applyOrientationToPoint 的逆变换：
 * 将显示坐标系中的点（显示画幅由 srcW/srcH 经方向换算得出）还原回源坐标系。
 */
export function unapplyOrientationFromPoint(
  px: number,
  py: number,
  srcW: number,
  srcH: number,
  o: Orientation
): { x: number; y: number } {
  const r = o.rotation;
  if (o.flip) {
    const outW = r === 90 || r === 270 ? srcH : srcW;
    px = outW - px;
  }
  if (r === 0) return { x: px, y: py };
  if (r === 90) return { x: py, y: srcH - px };
  if (r === 180) return { x: srcW - px, y: srcH - py };
  /* 270 */ return { x: srcW - py, y: px };
}
