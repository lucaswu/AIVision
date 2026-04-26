import { describe, expect, it } from "vitest";
import {
  buildInitialFilmInfo,
  buildInitialImageTransform,
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
        WeldId: "W-01",
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
      weldId: "W-01",
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
      weldId: "",
      filmNumber: "",
      filmDensity: "",
      sensitivity: "",
      normalizedSnr: "",
    });
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
      rotation: 90,
      flipH: -1,
      flipV: 1,
      position: { x: 0, y: 0 },
    });
  });
});
