import type { TaskFile } from "../../../utils/data";

export interface FilmInfoFormValues {
  filmPixelValue: string;
  resolution: string;
  specification: string;
  inspectionDate: string;
  weldId: string;
  filmNumber: string;
  filmDensity: string;
  sensitivity: string;
  normalizedSnr: string;
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
    weldId: file.WeldId || "",
    filmNumber: file.FilmNumber || "",
    filmDensity: file.FilmDensity || "",
    sensitivity: file.Sensitivity || "",
    normalizedSnr: file.NormalizedSnr || "",
  };
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

export function buildInitialImageTransform(file: TaskFile) {
  return {
    rotation: file.CorrectionRotation ?? 0,
    flipH: file.CorrectionFlip ? -1 : 1,
    flipV: 1,
    position: { x: 0, y: 0 },
  };
}
