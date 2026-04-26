import type { DefectRecord } from "../../../utils/data";

export interface ParsedWeldLocationShape {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  keypoints: { x: number; y: number }[];
}

export interface ParsedDefectOriginState {
  point: { x: number; y: number } | null;
  meta: { positioningType: number | null; originText: string | null } | null;
}

interface DefectTypeColor {
  name: string;
  color: string;
}

interface DefectBaseState {
  label: string;
  color: string;
  position?: string;
  size?: string;
  quality?: string;
  remark?: string;
  _positionMode?: "auto" | "manual";
  _positionLinear?: string;
  _positionClock?: string;
  defectRecordId?: string;
  _isCorrectedCoord?: boolean;
}

export interface HydratedSavedRect extends DefectBaseState {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface HydratedSavedCircle extends DefectBaseState {
  x: number;
  y: number;
  r: number;
}

export interface HydratedSavedPolygon extends DefectBaseState {
  points: { x: number; y: number }[];
}

interface HydrateDefectRecordsParams {
  defectRecords: DefectRecord[];
  weldShapes: ParsedWeldLocationShape[];
  originPoint: { x: number; y: number } | null;
  originLabel?: string;
  pixelRatio: number;
  hasPixelCalibration: boolean;
  defectTypes: DefectTypeColor[];
}

interface ParsedPosition {
  position: string;
  linear: string;
  clock: string;
  mode: "auto" | "manual";
}

type ParsedGeometry =
  | { type: "rect"; x?: number; y?: number; w?: number; h?: number }
  | { type: "circle"; x?: number; y?: number; r?: number }
  | { type: "polygon"; points?: { x: number; y: number }[] }
  | null;

export function parseWeldLocationShapes(
  weldLocation?: string | null
): ParsedWeldLocationShape[] {
  if (!weldLocation) return [];

  try {
    const detections: Array<{
      bbox?: number[];
      keypoints?: Array<{ id: number; x: number; y: number }>;
    }> = JSON.parse(weldLocation);

    if (!Array.isArray(detections) || detections.length === 0) {
      return [];
    }

    return detections
      .map((detection) => {
        const bbox = Array.isArray(detection.bbox) ? detection.bbox : [];
        if (bbox.length < 4) return null;

        const [x1, y1, x2, y2] = bbox;
        const keypoints = Array.isArray(detection.keypoints)
          ? detection.keypoints
              .filter((keypoint) => keypoint.x > 1 && keypoint.y > 1)
              .map((keypoint) => ({ x: keypoint.x, y: keypoint.y }))
          : [];

        return { x1, y1, x2, y2, keypoints };
      })
      .filter((shape): shape is ParsedWeldLocationShape => shape !== null);
  } catch {
    return [];
  }
}

export function parseDefectOrigin(
  defectPosition?: string | null
): ParsedDefectOriginState {
  if (!defectPosition) {
    return { point: null, meta: null };
  }

  try {
    const parsed = JSON.parse(defectPosition);
    const originX =
      typeof parsed?.origin_x === "number" ? parsed.origin_x : null;
    const originY =
      typeof parsed?.origin_y === "number" ? parsed.origin_y : null;

    if (originX === null || originY === null) {
      return { point: null, meta: null };
    }

    return {
      point: { x: originX, y: originY },
      meta: {
        positioningType:
          typeof parsed?.positioning_type === "number"
            ? parsed.positioning_type
            : null,
        originText:
          typeof parsed?.origin_text === "string" ? parsed.origin_text : null,
      },
    };
  } catch {
    return { point: null, meta: null };
  }
}

export function hydrateDefectRecords({
  defectRecords,
  weldShapes,
  originPoint,
  originLabel = "+",
  pixelRatio,
  hasPixelCalibration,
  defectTypes,
}: HydrateDefectRecordsParams): {
  rects: HydratedSavedRect[];
  circles: HydratedSavedCircle[];
  polygons: HydratedSavedPolygon[];
} {
  const rects: HydratedSavedRect[] = [];
  const circles: HydratedSavedCircle[] = [];
  const polygons: HydratedSavedPolygon[] = [];

  defectRecords.forEach((defectRecord) => {
    const geometry = parseGeometry(defectRecord.Geometry);
    const size = calculateDisplaySize(geometry, pixelRatio, hasPixelCalibration, defectRecord.Size);
    const parsedPosition = parseStoredPosition(defectRecord.Position || "");
    let linearPosition = parsedPosition.linear;
    let clockPosition = parsedPosition.clock;

    if (originPoint && parsedPosition.mode === "auto") {
      linearPosition = recalculateLinearPosition(
        geometry,
        originPoint.x,
        pixelRatio,
        originLabel
      );
    }

    if (weldShapes.length > 0 && parsedPosition.mode === "auto") {
      clockPosition = recalculateClockPosition(geometry, weldShapes);
    }

    const position =
      parsedPosition.mode === "auto"
        ? buildDefectPosition(linearPosition, clockPosition)
        : parsedPosition.position;

    const baseState: DefectBaseState = {
      label: defectRecord.DefectName || "未知",
      color:
        defectTypes.find((defectType) => defectType.name === defectRecord.DefectName)
          ?.color || "#f5222d",
      position,
      _positionMode: parsedPosition.mode,
      _positionLinear:
        parsedPosition.mode === "auto" ? linearPosition : parsedPosition.linear,
      _positionClock:
        parsedPosition.mode === "auto" ? clockPosition : parsedPosition.clock,
      size,
      quality: defectRecord.Grade || "",
      remark: defectRecord.Remark || "",
      defectRecordId: defectRecord.DefectRecordId,
      _isCorrectedCoord: true,
    };

    if (geometry?.type === "circle") {
      circles.push({
        x: geometry.x ?? 0,
        y: geometry.y ?? 0,
        r: geometry.r ?? 25,
        ...baseState,
      });
      return;
    }

    if (geometry?.type === "polygon" && Array.isArray(geometry.points)) {
      polygons.push({
        points: geometry.points,
        ...baseState,
      });
      return;
    }

    rects.push({
      x: geometry?.type === "rect" ? geometry.x ?? 0 : 0,
      y: geometry?.type === "rect" ? geometry.y ?? 0 : 0,
      w: geometry?.type === "rect" ? geometry.w ?? 50 : 50,
      h: geometry?.type === "rect" ? geometry.h ?? 50 : 50,
      ...baseState,
    });
  });

  return { rects, circles, polygons };
}

function parseGeometry(geometry?: string): ParsedGeometry {
  if (!geometry) return null;

  try {
    return JSON.parse(geometry) as ParsedGeometry;
  } catch {
    return null;
  }
}

function calculateDisplaySize(
  geometry: ParsedGeometry,
  pixelRatio: number,
  hasPixelCalibration: boolean,
  storedSize?: string
): string {
  if (storedSize) return storedSize;
  if (!geometry) return "";

  try {
    if (geometry.type === "rect" && geometry.w && geometry.h) {
      const areaPx = geometry.w * geometry.h;
      return formatArea(areaPx, pixelRatio, hasPixelCalibration);
    }

    if (geometry.type === "circle" && geometry.r) {
      const areaPx = Math.PI * geometry.r * geometry.r;
      return formatArea(areaPx, pixelRatio, hasPixelCalibration);
    }

    if (
      geometry.type === "polygon" &&
      Array.isArray(geometry.points) &&
      geometry.points.length >= 3
    ) {
      let areaPx = 0;
      for (let index = 0; index < geometry.points.length; index += 1) {
        const current = geometry.points[index];
        const next = geometry.points[(index + 1) % geometry.points.length];
        areaPx += current.x * next.y - next.x * current.y;
      }

      return formatArea(Math.abs(areaPx) / 2, pixelRatio, hasPixelCalibration);
    }
  } catch {
    return "";
  }

  return "";
}

function formatArea(
  areaPx: number,
  pixelRatio: number,
  hasPixelCalibration: boolean
): string {
  if (hasPixelCalibration) {
    return `${(areaPx * pixelRatio * pixelRatio).toFixed(2)}mm²`;
  }

  return `${areaPx.toFixed(2)}px²`;
}

function recalculateLinearPosition(
  geometry: ParsedGeometry,
  originX: number,
  pixelRatio: number,
  originLabel: string
): string {
  if (!geometry) return "";

  if (geometry.type === "rect" && geometry.w != null) {
    return formatDefectPosition(
      geometry.x ?? 0,
      (geometry.x ?? 0) + geometry.w,
      originX,
      pixelRatio,
      originLabel
    );
  }

  if (geometry.type === "circle" && geometry.r != null) {
    return formatDefectPosition(
      (geometry.x ?? 0) - geometry.r,
      (geometry.x ?? 0) + geometry.r,
      originX,
      pixelRatio,
      originLabel
    );
  }

  if (
    geometry.type === "polygon" &&
    Array.isArray(geometry.points) &&
    geometry.points.length >= 1
  ) {
    const xs = geometry.points.map((point) => point.x);
    return formatDefectPosition(
      Math.min(...xs),
      Math.max(...xs),
      originX,
      pixelRatio,
      originLabel
    );
  }

  return "";
}

function recalculateClockPosition(
  geometry: ParsedGeometry,
  weldShapes: ParsedWeldLocationShape[]
): string {
  if (!geometry) return "";

  const center = getGeometryCenter(geometry);
  if (!center) return "";

  const ellipse = getNearestEllipseParams(weldShapes, center.x, center.y);
  if (!ellipse) return "";

  return getClockPositionLabel(
    center.x,
    center.y,
    ellipse.cx,
    ellipse.cy,
    ellipse.rx,
    ellipse.ry
  );
}

function getGeometryCenter(
  geometry: ParsedGeometry
): { x: number; y: number } | null {
  if (!geometry) return null;

  if (geometry.type === "rect" && geometry.w != null && geometry.h != null) {
    return {
      x: (geometry.x ?? 0) + geometry.w / 2,
      y: (geometry.y ?? 0) + geometry.h / 2,
    };
  }

  if (geometry.type === "circle") {
    return {
      x: geometry.x ?? 0,
      y: geometry.y ?? 0,
    };
  }

  if (
    geometry.type === "polygon" &&
    Array.isArray(geometry.points) &&
    geometry.points.length >= 1
  ) {
    const xs = geometry.points.map((point) => point.x);
    const ys = geometry.points.map((point) => point.y);
    return {
      x: (Math.min(...xs) + Math.max(...xs)) / 2,
      y: (Math.min(...ys) + Math.max(...ys)) / 2,
    };
  }

  return null;
}

function formatDefectPosition(
  minX: number,
  maxX: number,
  originX: number,
  pixelRatio: number,
  originLabel = "+"
): string {
  const rawLeft = minX - originX;
  const rawRight = maxX - originX;

  if (pixelRatio > 0) {
    return `${originLabel}->${(rawLeft * pixelRatio).toFixed(2)}~${(
      rawRight * pixelRatio
    ).toFixed(2)}mm`;
  }

  return `${originLabel}->${Math.round(rawLeft)}~${Math.round(rawRight)}px`;
}

function parseStoredPosition(position?: string): ParsedPosition {
  const normalized = (position || "").trim();
  if (!normalized) {
    return { position: "", linear: "", clock: "", mode: "auto" };
  }

  const linear = extractLinearPosition(normalized);
  const clock = extractClockPosition(normalized);
  const rebuilt = [linear, clock].filter(Boolean).join(" ").trim();
  const linearLooksAuto = !linear || /^[^~\s]+->.+~.+(?:mm|px)$/.test(linear);
  const withoutLinear = linear ? normalized.replace(linear, " ") : normalized;
  const residue = withoutLinear.replace(/\d+'-\d+'/g, " ").replace(/\s+/g, " ").trim();
  const mode = linearLooksAuto && residue === "" ? "auto" : "manual";

  return {
    position: rebuilt || normalized,
    linear,
    clock,
    mode,
  };
}

function extractClockPosition(position?: string): string {
  if (!position) return "";
  const matches = position.match(/\d+'-\d+'/g);
  return matches && matches.length > 0 ? matches[matches.length - 1] : "";
}

function extractLinearPosition(position?: string): string {
  if (!position) return "";
  const clock = extractClockPosition(position);
  const withoutClock = clock ? position.replace(/\d+'-\d+'/g, " ") : position;
  return withoutClock.replace(/\s+/g, " ").trim();
}

function buildDefectPosition(linear: string, clock: string): string {
  return [linear.trim(), clock.trim()].filter(Boolean).join(" ").trim();
}

function getClockPositionLabel(
  ax: number,
  ay: number,
  cx: number,
  cy: number,
  rx: number,
  ry: number
): string {
  if (rx <= 0 || ry <= 0) return "";

  const clockLabels = ["12'", "1'", "2'", "3'", "4'", "5'", "6'", "7'", "8'", "9'", "10'", "11'"];
  const phi = Math.atan2((ay - cy) / ry, (ax - cx) / rx);
  const shifted = ((phi + Math.PI / 2) + 2 * Math.PI) % (2 * Math.PI);
  const sectorIndex = Math.floor(shifted / (2 * Math.PI / 12)) % 12;
  const nextIndex = (sectorIndex + 1) % 12;

  return `${clockLabels[sectorIndex]}-${clockLabels[nextIndex]}`;
}

function getNearestEllipseParams(
  shapes: ParsedWeldLocationShape[],
  ax: number,
  ay: number
): { cx: number; cy: number; rx: number; ry: number } | null {
  if (shapes.length === 0) return null;

  let bestShape = shapes[0];
  if (shapes.length > 1) {
    let minDistance = Infinity;

    for (const shape of shapes) {
      const keypoints = shape.keypoints;
      const cx =
        keypoints.length >= 2
          ? (Math.max(...keypoints.map((keypoint) => keypoint.x)) +
              Math.min(...keypoints.map((keypoint) => keypoint.x))) /
            2
          : (shape.x1 + shape.x2) / 2;
      const cy =
        keypoints.length >= 2
          ? (Math.max(...keypoints.map((keypoint) => keypoint.y)) +
              Math.min(...keypoints.map((keypoint) => keypoint.y))) /
            2
          : (shape.y1 + shape.y2) / 2;
      const distance = Math.hypot(ax - cx, ay - cy);
      if (distance < minDistance) {
        minDistance = distance;
        bestShape = shape;
      }
    }
  }

  const keypoints = bestShape.keypoints;
  if (keypoints.length >= 2) {
    const xs = keypoints.map((keypoint) => keypoint.x);
    const ys = keypoints.map((keypoint) => keypoint.y);
    return {
      cx: (Math.max(...xs) + Math.min(...xs)) / 2,
      cy: (Math.max(...ys) + Math.min(...ys)) / 2,
      rx: (Math.max(...xs) - Math.min(...xs)) / 2,
      ry: (Math.max(...ys) - Math.min(...ys)) / 2,
    };
  }

  return {
    cx: (bestShape.x1 + bestShape.x2) / 2,
    cy: (bestShape.y1 + bestShape.y2) / 2,
    rx: (bestShape.x2 - bestShape.x1) / 2,
    ry: (bestShape.y2 - bestShape.y1) / 2,
  };
}
