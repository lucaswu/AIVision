import { describe, expect, it } from "vitest";
import {
  hydrateDefectRecords,
  parseDefectOrigin,
  parseWeldLocationShapes,
} from "./imageEditorDefectHydration";

describe("imageEditorDefectHydration", () => {
  it("parses weld location and defect origin payloads defensively", () => {
    const weldShapes = parseWeldLocationShapes(
      JSON.stringify([
        {
          bbox: [10, 20, 110, 120],
          keypoints: [
            { id: 1, x: 0, y: 50 },
            { id: 2, x: 30, y: 40 },
            { id: 3, x: 80, y: 90 },
          ],
        },
      ])
    );

    expect(weldShapes).toEqual([
      {
        x1: 10,
        y1: 20,
        x2: 110,
        y2: 120,
        keypoints: [
          { x: 30, y: 40 },
          { x: 80, y: 90 },
        ],
      },
    ]);

    expect(parseWeldLocationShapes("bad-json")).toEqual([]);

    expect(
      parseDefectOrigin(
        JSON.stringify({
          origin_x: 123,
          origin_y: 456,
          positioning_type: 2,
          origin_text: "C",
        })
      )
    ).toEqual({
      point: { x: 123, y: 456 },
      meta: { positioningType: 2, originText: "C" },
    });

    expect(parseDefectOrigin('{"origin_x":"x"}')).toEqual({
      point: null,
      meta: null,
    });
  });

  it("hydrates backend defect records into frontend shapes and recalculates auto positions", () => {
    const result = hydrateDefectRecords({
      defectRecords: [
        {
          DefectRecordId: "rect-1",
          TaskFileId: "task-file-1",
          DefectName: "裂纹(A)",
          Position: "",
          Size: "",
          Grade: "II",
          Remark: "rect",
          Geometry: JSON.stringify({
            type: "rect",
            x: 10,
            y: 20,
            w: 30,
            h: 40,
          }),
        },
        {
          DefectRecordId: "circle-1",
          TaskFileId: "task-file-1",
          DefectName: "圆形缺陷(E)",
          Position: "人工位置",
          Size: "",
          Grade: "I",
          Remark: "circle",
          Geometry: JSON.stringify({
            type: "circle",
            x: 60,
            y: 70,
            r: 10,
          }),
        },
        {
          DefectRecordId: "poly-1",
          TaskFileId: "task-file-1",
          DefectName: "未熔合(B)",
          Position: "",
          Size: "",
          Grade: "III",
          Remark: "polygon",
          Geometry: JSON.stringify({
            type: "polygon",
            points: [
              { x: 100, y: 100 },
              { x: 120, y: 100 },
              { x: 120, y: 120 },
              { x: 100, y: 120 },
            ],
          }),
        },
      ],
      weldShapes: [
        {
          x1: 0,
          y1: 0,
          x2: 200,
          y2: 200,
          keypoints: [
            { x: 80, y: 90 },
            { x: 120, y: 90 },
            { x: 120, y: 110 },
            { x: 80, y: 110 },
          ],
        },
      ],
      originPoint: { x: 50, y: 50 },
      pixelRatio: 0.5,
      hasPixelCalibration: true,
      defectTypes: [
        { name: "裂纹(A)", color: "#ff4d4f" },
        { name: "未熔合(B)", color: "#eb2f96" },
      ],
    });

    expect(result.rects).toHaveLength(1);
    expect(result.circles).toHaveLength(1);
    expect(result.polygons).toHaveLength(1);

    expect(result.rects[0]).toMatchObject({
      label: "裂纹(A)",
      color: "#ff4d4f",
      position: "+->-20.00~-5.00mm 10'-11'",
      _positionMode: "auto",
      size: "300.00mm²",
      quality: "II",
      remark: "rect",
      defectRecordId: "rect-1",
      _isCorrectedCoord: true,
      x: 10,
      y: 20,
      w: 30,
      h: 40,
    });

    expect(result.circles[0]).toMatchObject({
      label: "圆形缺陷(E)",
      color: "#f5222d",
      position: "人工位置",
      _positionMode: "manual",
      size: `${(Math.PI * 10 * 10 * 0.25).toFixed(2)}mm²`,
    });

    expect(result.polygons[0]).toMatchObject({
      label: "未熔合(B)",
      color: "#eb2f96",
      position: "+->25.00~35.00mm 5'-6'",
      _positionMode: "auto",
      size: "100.00mm²",
    });
  });
});
