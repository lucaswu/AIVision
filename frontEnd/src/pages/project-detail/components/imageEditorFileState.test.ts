import { describe, expect, it } from "vitest";
import {
  buildInitialFilmInfo,
  buildInitialImageTransform,
  buildInitialWeldJoints,
  createEmptyHistorySnapshot,
  createIdleEllipseToolState,
  createIdleVerticalToolState,
} from "./imageEditorFileState";

describe("imageEditorFileState", () => {
  it("builds initial film info from task file fields with empty-string fallbacks", () => {
    expect(
      buildInitialFilmInfo({
        TaskFileId: "task-file-1",
        FileId: "file-1",
        FileName: "image-1.png",
        Status: "completed",
        ReviewStatus: "PENDING",
        FilmPixelValue: "12bit",
        Resolution: "0.1mm",
        Specification: "AB-1",
        InspectionDate: "2026-04-26",
        FilmNumber: "F-07",
        FilmDensity: "2.5",
        Sensitivity: "A",
        NormalizedSnr: "1.23",
      })
    ).toEqual({
      filmPixelValue: "12bit",
      resolution: "0.1mm",
      specification: "AB-1",
      inspectionDate: "2026-04-26",
      filmNumber: "F-07",
      filmDensity: "2.5",
      sensitivity: "A",
      normalizedSnr: "1.23",
    });

    expect(
      buildInitialFilmInfo({
        TaskFileId: "task-file-2",
        FileId: "file-2",
        FileName: "image-2.png",
        Status: "completed",
        ReviewStatus: "PENDING",
      })
    ).toEqual({
      filmPixelValue: "",
      resolution: "",
      specification: "",
      inspectionDate: "",
      filmNumber: "",
      filmDensity: "",
      sensitivity: "",
      normalizedSnr: "",
    });
  });

  it("builds initial weld joints sorted by SortOrder, defaulting to an empty list", () => {
    expect(
      buildInitialWeldJoints({
        TaskFileId: "task-file-1",
        FileId: "file-1",
        FileName: "image-1.png",
        Status: "completed",
        ReviewStatus: "PENDING",
        WeldJoints: [
          { WeldJointId: "weld-2", TaskFileId: "task-file-1", WeldNo: "EE12-07", SortOrder: 1 },
          { WeldJointId: "weld-1", TaskFileId: "task-file-1", WeldNo: "EE12-06", SortOrder: 0 },
        ],
      })
    ).toEqual([
      { id: "weld-1", weldNo: "EE12-06" },
      { id: "weld-2", weldNo: "EE12-07" },
    ]);

    expect(
      buildInitialWeldJoints({
        TaskFileId: "task-file-2",
        FileId: "file-2",
        FileName: "image-2.png",
        Status: "completed",
        ReviewStatus: "PENDING",
      })
    ).toEqual([]);
  });

  it("creates empty history snapshots and idle tool states", () => {
    expect(createEmptyHistorySnapshot()).toEqual({
      rects: [],
      polygons: [],
      circles: [],
      pixelRatio: 0,
    });

    expect(createIdleEllipseToolState()).toEqual({
      mode: "idle",
      shape: null,
      drag: {
        active: false,
        type: null,
        startMouse: { x: 0, y: 0 },
        startShape: { cx: 0, cy: 0, rx: 0, ry: 0, rotation: 0 },
      },
      isVisible: false,
    });

    expect(createIdleVerticalToolState()).toEqual({
      mode: "idle",
      shape: null,
      drag: {
        active: false,
        type: null,
        startMouse: { x: 0, y: 0 },
        startShape: { cx: 0, cy: 0, rx: 0, ry: 0, rotation: 0 },
      },
      isVisible: false,
    });
  });

  it("derives the initial image transform from correction metadata", () => {
    expect(
      buildInitialImageTransform({
        TaskFileId: "task-file-3",
        FileId: "file-3",
        FileName: "image-3.png",
        Status: "completed",
        ReviewStatus: "PENDING",
        CorrectionRotation: 90,
        CorrectionFlip: true,
      })
    ).toEqual({
      orientation: { rotation: 90, flip: true },
      position: { x: 0, y: 0 },
    });
  });

  it("prefers the user orientation over AI correction when present", () => {
    expect(
      buildInitialImageTransform({
        TaskFileId: "task-file-4",
        FileId: "file-4",
        FileName: "image-4.png",
        Status: "completed",
        ReviewStatus: "PENDING",
        CorrectionRotation: 90,
        CorrectionFlip: true,
        UserRotation: 180,
        UserFlip: false,
      })
    ).toEqual({
      orientation: { rotation: 180, flip: false },
      position: { x: 0, y: 0 },
    });
  });
});
