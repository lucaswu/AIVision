import { describe, it, expect } from 'vitest';
import {
  IDENTITY_ORIENTATION,
  type Orientation,
  applyOrientationToPoint,
  flipOrientationH,
  flipOrientationV,
  normalizeRotation,
  orientationFromCorrection,
  orientationsEqual,
  orientedSize,
  rotateOrientation,
  unapplyOrientationFromPoint,
} from './orientation';

const W = 400;
const H = 300;
// 非对称采样点，能区分所有 8 种 D4 方向
const SAMPLE_POINTS = [
  { x: 10, y: 20 },
  { x: 390, y: 20 },
  { x: 10, y: 280 },
  { x: 123, y: 45 },
];

const ALL_ORIENTATIONS: Orientation[] = ([0, 90, 180, 270] as const).flatMap(
  (rotation) => [
    { rotation, flip: false },
    { rotation, flip: true },
  ]
);

// —— 屏幕操作的参照实现：直接作用在"当前显示画面"的点上 ——
const screenRotate90CW = (p: { x: number; y: number }, size: { w: number; h: number }) =>
  ({ x: size.h - p.y, y: p.x });
const screenFlipH = (p: { x: number; y: number }, size: { w: number; h: number }) =>
  ({ x: size.w - p.x, y: p.y });
const screenFlipV = (p: { x: number; y: number }, size: { w: number; h: number }) =>
  ({ x: p.x, y: size.h - p.y });

describe('normalizeRotation / orientationFromCorrection', () => {
  it('归一化任意角度到 0/90/180/270', () => {
    expect(normalizeRotation(0)).toBe(0);
    expect(normalizeRotation(-90)).toBe(270);
    expect(normalizeRotation(450)).toBe(90);
    expect(normalizeRotation(-180)).toBe(180);
    expect(normalizeRotation(720)).toBe(0);
  });

  it('从矫正字段构造（含 null/undefined/-90）', () => {
    expect(orientationFromCorrection(null, null)).toEqual(IDENTITY_ORIENTATION);
    expect(orientationFromCorrection(undefined, undefined)).toEqual(IDENTITY_ORIENTATION);
    expect(orientationFromCorrection(-90, true)).toEqual({ rotation: 270, flip: true });
  });
});

describe('applyOrientationToPoint / unapplyOrientationFromPoint', () => {
  it('恒等方向不改变点', () => {
    for (const p of SAMPLE_POINTS) {
      expect(applyOrientationToPoint(p.x, p.y, W, H, IDENTITY_ORIENTATION)).toEqual(p);
    }
  });

  it('所有 8 种方向上 unapply 都是 apply 的逆', () => {
    for (const o of ALL_ORIENTATIONS) {
      for (const p of SAMPLE_POINTS) {
        const t = applyOrientationToPoint(p.x, p.y, W, H, o);
        const back = unapplyOrientationFromPoint(t.x, t.y, W, H, o);
        expect(back).toEqual(p);
      }
    }
  });

  it('变换后的点落在方向作用后的画幅内', () => {
    for (const o of ALL_ORIENTATIONS) {
      const size = orientedSize(W, H, o);
      for (const p of SAMPLE_POINTS) {
        const t = applyOrientationToPoint(p.x, p.y, W, H, o);
        expect(t.x).toBeGreaterThanOrEqual(0);
        expect(t.x).toBeLessThanOrEqual(size.w);
        expect(t.y).toBeGreaterThanOrEqual(0);
        expect(t.y).toBeLessThanOrEqual(size.h);
      }
    }
  });
});

describe('屏幕操作组合律（按钮语义 = 对当前显示画面的操作）', () => {
  it('rotateOrientation(+90) 等价于对显示结果做顺时针 90° 旋转', () => {
    for (const o of ALL_ORIENTATIONS) {
      const size = orientedSize(W, H, o);
      const composed = rotateOrientation(o, 90);
      for (const p of SAMPLE_POINTS) {
        const displayed = applyOrientationToPoint(p.x, p.y, W, H, o);
        const expected = screenRotate90CW(displayed, size);
        expect(applyOrientationToPoint(p.x, p.y, W, H, composed)).toEqual(expected);
      }
    }
  });

  it('rotateOrientation(-90) 是 rotateOrientation(+90) 的逆操作', () => {
    for (const o of ALL_ORIENTATIONS) {
      expect(rotateOrientation(rotateOrientation(o, 90), -90)).toEqual(o);
    }
  });

  it('flipOrientationH 等价于对显示结果做水平镜像', () => {
    for (const o of ALL_ORIENTATIONS) {
      const size = orientedSize(W, H, o);
      const composed = flipOrientationH(o);
      for (const p of SAMPLE_POINTS) {
        const displayed = applyOrientationToPoint(p.x, p.y, W, H, o);
        const expected = screenFlipH(displayed, size);
        expect(applyOrientationToPoint(p.x, p.y, W, H, composed)).toEqual(expected);
      }
    }
  });

  it('flipOrientationV 等价于对显示结果做垂直镜像', () => {
    for (const o of ALL_ORIENTATIONS) {
      const size = orientedSize(W, H, o);
      const composed = flipOrientationV(o);
      for (const p of SAMPLE_POINTS) {
        const displayed = applyOrientationToPoint(p.x, p.y, W, H, o);
        const expected = screenFlipV(displayed, size);
        expect(applyOrientationToPoint(p.x, p.y, W, H, composed)).toEqual(expected);
      }
    }
  });

  it('两次相同翻转回到原方向；180° = 两次 90°', () => {
    for (const o of ALL_ORIENTATIONS) {
      expect(flipOrientationH(flipOrientationH(o))).toEqual(o);
      expect(flipOrientationV(flipOrientationV(o))).toEqual(o);
      expect(rotateOrientation(o, 180)).toEqual(rotateOrientation(rotateOrientation(o, 90), 90));
    }
  });

  it('垂直镜像 ≡ 水平镜像 + 180° 旋转', () => {
    for (const o of ALL_ORIENTATIONS) {
      expect(flipOrientationV(o)).toEqual(rotateOrientation(flipOrientationH(o), 180));
    }
  });

  it('orientationsEqual 区分全部 8 种方向', () => {
    for (const a of ALL_ORIENTATIONS) {
      for (const b of ALL_ORIENTATIONS) {
        expect(orientationsEqual(a, b)).toBe(a.rotation === b.rotation && a.flip === b.flip);
      }
    }
  });
});
