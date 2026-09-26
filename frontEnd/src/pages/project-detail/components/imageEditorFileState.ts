import type { TaskFile } from "../../../utils/data";
import { orientationFromCorrection } from "./orientation";

export interface FilmInfoFormValues {
  filmPixelValue: string;
  resolution: string;
  specification: string;
  inspectionDate: string;
  filmNumber: string;
  filmDensity: string;
  sensitivity: string;
  normalizedSnr: string;
}

// 焊口编辑态：一张底片可以维护多个焊口编号，id 为客户端生成的稳定标识，
// 用于在保存前就能被缺陷条目引用（见 DefectBase.weldJointId）
export interface WeldJointDraft {
  id: string;
  weldNo: string;
}

export interface HistorySnapshotState<TSavedRect = unknown, TSavedPolygon = unknown, TSavedCircle = unknown> {
  rects: TSavedRect[];
  polygons: TSavedPolygon[];
  circles: TSavedCircle[];
  pixelRatio: number;
}

export interface EllipseToolStateShape {
  cx: number;
  cy: number;
  rx: number;
  ry: number;
  rotation: number;
}

export interface EllipseToolStateValue {
  mode: "idle" | "placing" | "editing";
  shape: EllipseToolStateShape | null;
  drag: {
    active: boolean;
    type: "move" | "rotate" | "resize-t" | "resize-b" | "resize-l" | "resize-r" | null;
    startMouse: { x: number; y: number };
    startShape: EllipseToolStateShape;
  };
  isVisible: boolean;
}

export interface VerticalToolStateValue {
  mode: "idle" | "placing" | "editing";
  shape: EllipseToolStateShape | null;
  drag: {
    active: boolean;
    type: "move" | "resize-l" | "resize-r" | null;
    startMouse: { x: number; y: number };
    startShape: EllipseToolStateShape;
  };
  isVisible: boolean;
}

export function buildInitialFilmInfo(file: TaskFile): FilmInfoFormValues {
  return {
    filmPixelValue: file.FilmPixelValue || "",
    resolution: file.Resolution || "",
    specification: file.Specification || "",
    inspectionDate: file.InspectionDate || "",
    filmNumber: file.FilmNumber || "",
    filmDensity: file.FilmDensity || "",
    sensitivity: file.Sensitivity || "",
    normalizedSnr: file.NormalizedSnr || "",
  };
}

export function buildInitialWeldJoints(file: TaskFile): WeldJointDraft[] {
  if (!file.WeldJoints || file.WeldJoints.length === 0) return [];
  return [...file.WeldJoints]
    .sort((a, b) => (a.SortOrder ?? 0) - (b.SortOrder ?? 0))
    .map((joint) => ({ id: joint.WeldJointId, weldNo: joint.WeldNo || "" }));
}

// crypto.randomUUID() 只在安全上下文（HTTPS 或 http://localhost）里存在，
// 客户现场常见通过局域网 IP + 明文 HTTP 访问，此时它是 undefined，直接调用会抛异常。
// crypto.getRandomValues() 不受安全上下文限制，优先用它拼出标准 UUID v4；
// 两者都不可用时（极旧浏览器）再退化到时间戳 + 随机数，仅要求前端本地唯一即可。
export function createWeldJointId(): string {
  const cryptoObj: Crypto | undefined = typeof crypto !== "undefined" ? crypto : undefined;
  if (cryptoObj && typeof cryptoObj.randomUUID === "function") {
    return cryptoObj.randomUUID();
  }
  if (cryptoObj && typeof cryptoObj.getRandomValues === "function") {
    const bytes = cryptoObj.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function createEmptyHistorySnapshot<
  TSavedRect = unknown,
  TSavedPolygon = unknown,
  TSavedCircle = unknown,
>(): HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle> {
  return {
    rects: [],
    polygons: [],
    circles: [],
    pixelRatio: 0,
  };
}

export function createIdleEllipseToolState(): EllipseToolStateValue {
  return {
    mode: "idle",
    shape: null,
    drag: {
      active: false,
      type: null,
      startMouse: { x: 0, y: 0 },
      startShape: { cx: 0, cy: 0, rx: 0, ry: 0, rotation: 0 },
    },
    isVisible: false,
  };
}

export function createIdleVerticalToolState(): VerticalToolStateValue {
  return {
    mode: "idle",
    shape: null,
    drag: {
      active: false,
      type: null,
      startMouse: { x: 0, y: 0 },
      startShape: { cx: 0, cy: 0, rx: 0, ry: 0, rotation: 0 },
    },
    isVisible: false,
  };
}

// 用户手动矫正（相对原始图片的绝对方向）优先于 AI 矫正；
// 这样即使重新分析改变了 AI 矫正参数，用户认定的方向依然生效
export function buildInitialImageTransform(file: TaskFile) {
  const hasUserOrientation = file.UserRotation != null || file.UserFlip != null;
  return {
    orientation: hasUserOrientation
      ? orientationFromCorrection(file.UserRotation, file.UserFlip)
      : orientationFromCorrection(file.CorrectionRotation, file.CorrectionFlip),
    position: { x: 0, y: 0 },
  };
}
