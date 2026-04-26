export interface RectDefectRecordInput {
  label: string;
  position?: string;
  size?: string;
  quality?: string;
  remark?: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PolygonDefectRecordInput {
  label: string;
  position?: string;
  size?: string;
  quality?: string;
  remark?: string;
  points: { x: number; y: number }[];
}

export interface CircleDefectRecordInput {
  label: string;
  position?: string;
  size?: string;
  quality?: string;
  remark?: string;
  x: number;
  y: number;
  r: number;
}

export interface DefectRecordPayload {
  TaskFileId: string;
  DefectName: string;
  Position: string;
  Geometry: string;
  Size: string;
  Grade: string;
  Remark: string;
}

function createBaseDefectRecordPayload(taskFileId: string, defect: {
  label: string;
  position?: string;
  size?: string;
  quality?: string;
  remark?: string;
}) {
  return {
    TaskFileId: taskFileId,
    DefectName: defect.label,
    Position: defect.position || "",
    Size: defect.size || "",
    Grade: defect.quality || "",
    Remark: defect.remark || "",
  };
}

export function buildDefectRecordPayloads(
  taskFileId: string,
  defectRects: RectDefectRecordInput[],
  defectPolygons: PolygonDefectRecordInput[],
  defectCircles: CircleDefectRecordInput[]
): DefectRecordPayload[] {
  return [
    ...defectRects.map((defect) => ({
      ...createBaseDefectRecordPayload(taskFileId, defect),
      Geometry: JSON.stringify({
        type: "rect",
        x: defect.x,
        y: defect.y,
        w: defect.w,
        h: defect.h,
      }),
    })),
    ...defectPolygons.map((defect) => ({
      ...createBaseDefectRecordPayload(taskFileId, defect),
      Geometry: JSON.stringify({
        type: "polygon",
        points: defect.points,
      }),
    })),
    ...defectCircles.map((defect) => ({
      ...createBaseDefectRecordPayload(taskFileId, defect),
      Geometry: JSON.stringify({
        type: "circle",
        x: defect.x,
        y: defect.y,
        r: defect.r,
      }),
    })),
  ];
}
