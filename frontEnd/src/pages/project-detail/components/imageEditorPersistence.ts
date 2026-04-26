import type { TaskFile } from "../../../utils/data";
import {
  buildDefectRecordPayloads,
  type CircleDefectRecordInput,
  type PolygonDefectRecordInput,
  type RectDefectRecordInput,
} from "./imageEditorDefectRecords";
import type { FilmInfoFormValues } from "./imageEditorFileState";

export interface ReviewFilePayload {
  ManualResult: string;
  PlateQuality: string;
  FilmPixelValue: string;
  Resolution: string;
  Specification: string;
  InspectionDate: string;
  WeldId: string;
  FilmNumber: string;
  FilmDensity: string;
  Sensitivity: string;
  NormalizedSnr: string;
}

export interface ReportPersistenceApi {
  reviewFile: (taskFileId: string, data: ReviewFilePayload) => Promise<unknown>;
  updateFileLocation: (
    taskFileId: string,
    data: { WeldLocation?: string; DefectPosition?: string }
  ) => Promise<unknown>;
}

export interface DefectRecordPersistenceApi {
  replace: (taskFileId: string, data: unknown[]) => Promise<unknown>;
  deleteByTaskFileId: (taskFileId: string) => Promise<unknown>;
}

export interface PersistDefectRecordsParams {
  taskFileId: string;
  defectRects: RectDefectRecordInput[];
  defectPolygons: PolygonDefectRecordInput[];
  defectCircles: CircleDefectRecordInput[];
  defectRecordApi: DefectRecordPersistenceApi;
}

export interface SaveReviewSessionParams extends PersistDefectRecordsParams {
  selectedFile: TaskFile;
  filmInfoValues: FilmInfoFormValues;
  originPoint: { x: number; y: number } | null;
  reportApi: ReportPersistenceApi;
}

export function buildReviewFilePayload(
  selectedFile: TaskFile,
  filmInfoValues: FilmInfoFormValues
): ReviewFilePayload {
  return {
    ManualResult: selectedFile.VisionResult || "{}",
    PlateQuality: "",
    FilmPixelValue: filmInfoValues.filmPixelValue,
    Resolution: filmInfoValues.resolution,
    Specification: filmInfoValues.specification,
    InspectionDate: filmInfoValues.inspectionDate,
    WeldId: filmInfoValues.weldId,
    FilmNumber: filmInfoValues.filmNumber,
    FilmDensity: filmInfoValues.filmDensity,
    Sensitivity: filmInfoValues.sensitivity,
    NormalizedSnr: filmInfoValues.normalizedSnr,
  };
}

export function syncFilmInfoToTaskFile(
  selectedFile: TaskFile,
  filmInfoValues: FilmInfoFormValues
) {
  selectedFile.FilmPixelValue = filmInfoValues.filmPixelValue;
  selectedFile.Resolution = filmInfoValues.resolution;
  selectedFile.Specification = filmInfoValues.specification;
  selectedFile.InspectionDate = filmInfoValues.inspectionDate;
  selectedFile.WeldId = filmInfoValues.weldId;
  selectedFile.FilmNumber = filmInfoValues.filmNumber;
  selectedFile.FilmDensity = filmInfoValues.filmDensity;
  selectedFile.Sensitivity = filmInfoValues.sensitivity;
  selectedFile.NormalizedSnr = filmInfoValues.normalizedSnr;
}

export function buildDefectPositionPayload(originPoint: { x: number; y: number }) {
  return JSON.stringify({
    detected: true,
    positioning_type: 0,
    origin_x: originPoint.x,
    origin_y: originPoint.y,
    origin_text: null,
    detections: [],
  });
}

export async function persistDefectRecords({
  taskFileId,
  defectRects,
  defectPolygons,
  defectCircles,
  defectRecordApi,
}: PersistDefectRecordsParams) {
  const allDefects = buildDefectRecordPayloads(
    taskFileId,
    defectRects,
    defectPolygons,
    defectCircles
  );

  if (allDefects.length > 0) {
    await defectRecordApi.replace(taskFileId, allDefects);
    return { allDefects, mode: "replace" as const };
  }

  await defectRecordApi.deleteByTaskFileId(taskFileId);
  return { allDefects, mode: "delete" as const };
}

export async function saveReviewSession({
  selectedFile,
  filmInfoValues,
  originPoint,
  reportApi,
  defectRecordApi,
  taskFileId,
  defectRects,
  defectPolygons,
  defectCircles,
}: SaveReviewSessionParams) {
  const reviewPayload = buildReviewFilePayload(selectedFile, filmInfoValues);
  await reportApi.reviewFile(taskFileId, reviewPayload);
  syncFilmInfoToTaskFile(selectedFile, filmInfoValues);

  const defectPersistence = await persistDefectRecords({
    taskFileId,
    defectRects,
    defectPolygons,
    defectCircles,
    defectRecordApi,
  });

  if (originPoint) {
    const defectPosition = buildDefectPositionPayload(originPoint);
    await reportApi.updateFileLocation(taskFileId, { DefectPosition: defectPosition });
    selectedFile.DefectPosition = defectPosition;
  }

  return defectPersistence;
}
