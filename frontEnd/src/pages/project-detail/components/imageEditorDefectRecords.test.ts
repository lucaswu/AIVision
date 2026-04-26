import { describe, expect, it } from "vitest";
import { buildDefectRecordPayloads } from "./imageEditorDefectRecords";

describe("buildDefectRecordPayloads", () => {
  it("builds rect, polygon, and circle payloads with serialized geometry", () => {
    const payloads = buildDefectRecordPayloads(
      "task-file-1",
      [
        {
          label: "裂纹(A)",
          position: "+12~18mm",
          size: "15.40mm²",
          quality: "II",
          remark: "矩形缺陷",
          x: 10,
          y: 20,
          w: 30,
          h: 40,
        },
      ],
      [
        {
          label: "未熔合(B)",
          position: "6'-7'",
          size: "20.10mm²",
          quality: "III",
          remark: "多边形缺陷",
          points: [
            { x: 1, y: 2 },
            { x: 3, y: 4 },
            { x: 5, y: 6 },
          ],
        },
      ],
      [
        {
          label: "圆形缺陷(E)",
          position: "-4~2mm",
          size: "8.88mm²",
          quality: "I",
          remark: "圆形缺陷",
          x: 50,
          y: 60,
          r: 12,
        },
      ]
    );

    expect(payloads).toEqual([
      {
        TaskFileId: "task-file-1",
        DefectName: "裂纹(A)",
        Position: "+12~18mm",
        Geometry: JSON.stringify({ type: "rect", x: 10, y: 20, w: 30, h: 40 }),
        Size: "15.40mm²",
        Grade: "II",
        Remark: "矩形缺陷",
      },
      {
        TaskFileId: "task-file-1",
        DefectName: "未熔合(B)",
        Position: "6'-7'",
        Geometry: JSON.stringify({
          type: "polygon",
          points: [
            { x: 1, y: 2 },
            { x: 3, y: 4 },
            { x: 5, y: 6 },
          ],
        }),
        Size: "20.10mm²",
        Grade: "III",
        Remark: "多边形缺陷",
      },
      {
        TaskFileId: "task-file-1",
        DefectName: "圆形缺陷(E)",
        Position: "-4~2mm",
        Geometry: JSON.stringify({ type: "circle", x: 50, y: 60, r: 12 }),
        Size: "8.88mm²",
        Grade: "I",
        Remark: "圆形缺陷",
      },
    ]);
  });

  it("falls back to empty strings for optional display fields", () => {
    const payloads = buildDefectRecordPayloads(
      "task-file-2",
      [
        {
          label: "其他(H)",
          x: 0,
          y: 0,
          w: 1,
          h: 1,
        },
      ],
      [],
      []
    );

    expect(payloads).toEqual([
      {
        TaskFileId: "task-file-2",
        DefectName: "其他(H)",
        Position: "",
        Geometry: JSON.stringify({ type: "rect", x: 0, y: 0, w: 1, h: 1 }),
        Size: "",
        Grade: "",
        Remark: "",
      },
    ]);
  });
});
