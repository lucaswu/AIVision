import { describe, expect, it, vi } from "vitest";
import type { TaskFile } from "../../../utils/data";
import {
  buildDefectPositionPayload,
  buildReviewFilePayload,
  persistDefectRecords,
  saveReviewSession,
  syncFilmInfoToTaskFile,
} from "./imageEditorPersistence";
import type { FilmInfoFormValues } from "./imageEditorFileState";

function buildTaskFile(overrides: Partial<TaskFile> = {}): TaskFile {
  return {
    TaskFileId: "task-file-1",
    FileId: "file-1",
    FileName: "film-001.png",
    Status: "completed",
    ReviewStatus: "PENDING",
    VisionResult: '{"result":"ok"}',
    ...overrides,
  };
}

function buildFilmInfoValues(
  overrides: Partial<FilmInfoFormValues> = {}
): FilmInfoFormValues {
  return {
    filmPixelValue: "1024",
    resolution: "4 lp/mm",
    specification: "NB/T 47013",
    inspectionDate: "2026-04-26",
    weldId: "W-01",
    filmNumber: "P-001",
    filmDensity: "2.5",
    sensitivity: "1.8%",
    normalizedSnr: "18.2",
    ...overrides,
  };
}

describe("imageEditorPersistence", () => {
  it("builds the manual review payload from the selected file and film info", () => {
    const payload = buildReviewFilePayload(buildTaskFile(), buildFilmInfoValues());

    expect(payload).toEqual({
      ManualResult: '{"result":"ok"}',
      PlateQuality: "",
      FilmPixelValue: "1024",
      Resolution: "4 lp/mm",
      Specification: "NB/T 47013",
      InspectionDate: "2026-04-26",
      WeldId: "W-01",
      FilmNumber: "P-001",
      FilmDensity: "2.5",
      Sensitivity: "1.8%",
      NormalizedSnr: "18.2",
    });
  });

  it("syncs auto-saved film info back into the current task file", () => {
    const file = buildTaskFile();
    const values = buildFilmInfoValues({ filmNumber: "P-009", normalizedSnr: "22.3" });

    syncFilmInfoToTaskFile(file, values);

    expect(file.FilmNumber).toBe("P-009");
    expect(file.NormalizedSnr).toBe("22.3");
    expect(file.Specification).toBe("NB/T 47013");
  });

  it("replaces stored defects when there are annotations to save", async () => {
    const defectRecordApi = {
      replace: vi.fn().mockResolvedValue(undefined),
      deleteByTaskFileId: vi.fn().mockResolvedValue(undefined),
    };

    const result = await persistDefectRecords({
      taskFileId: "task-file-1",
      defectRects: [
        {
          label: "Porosity",
          position: "中心",
          size: "3mm",
          quality: "II",
          remark: "note",
          x: 10,
          y: 20,
          w: 30,
          h: 40,
        },
      ],
      defectPolygons: [],
      defectCircles: [],
      defectRecordApi,
    });

    expect(result.mode).toBe("replace");
    expect(defectRecordApi.replace).toHaveBeenCalledTimes(1);
    expect(defectRecordApi.deleteByTaskFileId).not.toHaveBeenCalled();
  });

  it("deletes stored defects when there are no annotations left", async () => {
    const defectRecordApi = {
      replace: vi.fn().mockResolvedValue(undefined),
      deleteByTaskFileId: vi.fn().mockResolvedValue(undefined),
    };

    const result = await persistDefectRecords({
      taskFileId: "task-file-1",
      defectRects: [],
      defectPolygons: [],
      defectCircles: [],
      defectRecordApi,
    });

    expect(result.mode).toBe("delete");
    expect(defectRecordApi.deleteByTaskFileId).toHaveBeenCalledWith("task-file-1");
    expect(defectRecordApi.replace).not.toHaveBeenCalled();
  });

  it("saves review info, annotations and origin point together", async () => {
    const selectedFile = buildTaskFile();
    const filmInfoValues = buildFilmInfoValues();
    const reportApi = {
      reviewFile: vi.fn().mockResolvedValue(undefined),
      updateFileLocation: vi.fn().mockResolvedValue(undefined),
    };
    const defectRecordApi = {
      replace: vi.fn().mockResolvedValue(undefined),
      deleteByTaskFileId: vi.fn().mockResolvedValue(undefined),
    };

    await saveReviewSession({
      selectedFile,
      taskFileId: selectedFile.TaskFileId,
      filmInfoValues,
      originPoint: { x: 120, y: 48 },
      reportApi,
      defectRecordApi,
      defectRects: [
        {
          label: "Porosity",
          x: 10,
          y: 20,
          w: 30,
          h: 40,
        },
      ],
      defectPolygons: [],
      defectCircles: [],
    });

    expect(reportApi.reviewFile).toHaveBeenCalledWith(
      "task-file-1",
      expect.objectContaining({
        FilmNumber: "P-001",
        ManualResult: '{"result":"ok"}',
      })
    );
    expect(defectRecordApi.replace).toHaveBeenCalledTimes(1);
    expect(reportApi.updateFileLocation).toHaveBeenCalledWith("task-file-1", {
      DefectPosition: buildDefectPositionPayload({ x: 120, y: 48 }),
    });
    expect(selectedFile.DefectPosition).toBe(
      buildDefectPositionPayload({ x: 120, y: 48 })
    );
    expect(selectedFile.WeldId).toBe("W-01");
  });

  it("stops before saving defects when review info persistence fails", async () => {
    const selectedFile = buildTaskFile();
    const reportApi = {
      reviewFile: vi.fn().mockRejectedValue(new Error("review failed")),
      updateFileLocation: vi.fn().mockResolvedValue(undefined),
    };
    const defectRecordApi = {
      replace: vi.fn().mockResolvedValue(undefined),
      deleteByTaskFileId: vi.fn().mockResolvedValue(undefined),
    };

    await expect(
      saveReviewSession({
        selectedFile,
        taskFileId: selectedFile.TaskFileId,
        filmInfoValues: buildFilmInfoValues(),
        originPoint: { x: 120, y: 48 },
        reportApi,
        defectRecordApi,
        defectRects: [{ label: "Porosity", x: 10, y: 20, w: 30, h: 40 }],
        defectPolygons: [],
        defectCircles: [],
      })
    ).rejects.toThrow("review failed");

    expect(defectRecordApi.replace).not.toHaveBeenCalled();
    expect(reportApi.updateFileLocation).not.toHaveBeenCalled();
  });

  it("stops before saving origin when defect persistence fails", async () => {
    const selectedFile = buildTaskFile();
    const reportApi = {
      reviewFile: vi.fn().mockResolvedValue(undefined),
      updateFileLocation: vi.fn().mockResolvedValue(undefined),
    };
    const defectRecordApi = {
      replace: vi.fn().mockRejectedValue(new Error("replace failed")),
      deleteByTaskFileId: vi.fn().mockResolvedValue(undefined),
    };

    await expect(
      saveReviewSession({
        selectedFile,
        taskFileId: selectedFile.TaskFileId,
        filmInfoValues: buildFilmInfoValues(),
        originPoint: { x: 120, y: 48 },
        reportApi,
        defectRecordApi,
        defectRects: [{ label: "Porosity", x: 10, y: 20, w: 30, h: 40 }],
        defectPolygons: [],
        defectCircles: [],
      })
    ).rejects.toThrow("replace failed");

    expect(reportApi.reviewFile).toHaveBeenCalledTimes(1);
    expect(reportApi.updateFileLocation).not.toHaveBeenCalled();
  });
});
