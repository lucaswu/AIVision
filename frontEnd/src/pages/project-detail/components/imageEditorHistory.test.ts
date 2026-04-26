import { describe, expect, it } from "vitest";
import {
  cloneHistorySnapshot,
  isSameHistorySnapshot,
  pushHistorySnapshot,
  removeDefectAtIndex,
  stepHistoryBackward,
  stepHistoryForward,
} from "./imageEditorHistory";

describe("imageEditorHistory", () => {
  const buildSnapshot = (ids: number[], pixelRatio: number = 1) => ({
    rects: ids.map((id) => ({ id })),
    polygons: [],
    circles: [],
    pixelRatio,
  });

  it("pushes a new snapshot and truncates future history", () => {
    const history = [
      buildSnapshot([1], 1),
      buildSnapshot([2], 2),
      buildSnapshot([3], 3),
    ];

    const result = pushHistorySnapshot(
      history,
      0,
      buildSnapshot([9], 9)
    );

    expect(result.history).toHaveLength(2);
    expect(result.history[0].rects).toEqual([{ id: 1 }]);
    expect(result.history[1].rects).toEqual([{ id: 9 }]);
    expect(result.index).toBe(1);
  });

  it("steps backward and forward through history snapshots", () => {
    const history = [
      buildSnapshot([1], 1),
      buildSnapshot([2], 2),
      buildSnapshot([3], 3),
    ];

    const previous = stepHistoryBackward(history, 2);
    const next = stepHistoryForward(history, 1);

    expect(previous?.index).toBe(1);
    expect(previous?.snapshot.rects).toEqual([{ id: 2 }]);
    expect(next?.index).toBe(2);
    expect(next?.snapshot.pixelRatio).toBe(3);
  });

  it("removes a defect from the requested collection only", () => {
    const result = removeDefectAtIndex(
      "polygon",
      1,
      [{ id: "r1" }],
      [{ id: "p1" }, { id: "p2" }],
      [{ id: "c1" }]
    );

    expect(result.rects).toEqual([{ id: "r1" }]);
    expect(result.polygons).toEqual([{ id: "p1" }]);
    expect(result.circles).toEqual([{ id: "c1" }]);
  });

  it("clones snapshots before returning them", () => {
    const original = buildSnapshot([1], 1);

    const cloned = cloneHistorySnapshot(original);
    cloned.rects[0].id = 99;

    expect(original.rects[0].id).toBe(1);
  });

  it("detects whether two snapshots are equivalent", () => {
    const left = buildSnapshot([1], 2);
    const right = buildSnapshot([1], 2);
    const different = buildSnapshot([2], 2);

    expect(isSameHistorySnapshot(left, right)).toBe(true);
    expect(isSameHistorySnapshot(left, different)).toBe(false);
  });

  it("restores a deleted defect after undo and reapplies it on redo", () => {
    const original = buildSnapshot([1, 2], 1);
    const deleted = removeDefectAtIndex(
      "rect",
      1,
      original.rects,
      original.polygons,
      original.circles
    );
    deleted.pixelRatio = original.pixelRatio;

    const historyState = pushHistorySnapshot([original], 0, deleted);

    expect(historyState.history[1].rects).toEqual([{ id: 1 }]);

    const undoState = stepHistoryBackward(historyState.history, historyState.index);
    expect(undoState?.snapshot.rects).toEqual([{ id: 1 }, { id: 2 }]);

    const redoState = stepHistoryForward(historyState.history, undoState!.index);
    expect(redoState?.snapshot.rects).toEqual([{ id: 1 }]);
  });

  it("restores the edited state after reset undo and reapplies reset on redo", () => {
    const original = buildSnapshot([1], 1);
    const edited = buildSnapshot([1, 2], 3);
    const reset = cloneHistorySnapshot(original);

    const withEdited = pushHistorySnapshot([original], 0, edited);
    const withReset = pushHistorySnapshot(
      withEdited.history,
      withEdited.index,
      reset
    );

    expect(withReset.history[2].rects).toEqual([{ id: 1 }]);
    expect(withReset.history[2].pixelRatio).toBe(1);

    const undoState = stepHistoryBackward(withReset.history, withReset.index);
    expect(undoState?.snapshot.rects).toEqual([{ id: 1 }, { id: 2 }]);
    expect(undoState?.snapshot.pixelRatio).toBe(3);

    const redoState = stepHistoryForward(withReset.history, undoState!.index);
    expect(redoState?.snapshot.rects).toEqual([{ id: 1 }]);
    expect(redoState?.snapshot.pixelRatio).toBe(1);
  });
});
