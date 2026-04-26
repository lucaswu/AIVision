import type { HistorySnapshotState } from "./imageEditorFileState";

export type DefectCollectionType = "rect" | "polygon" | "circle";

export interface HistoryState<TSavedRect = unknown, TSavedPolygon = unknown, TSavedCircle = unknown> {
  history: HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle>[];
  index: number;
}

export function cloneHistorySnapshot<TSavedRect, TSavedPolygon, TSavedCircle>(
  snapshot: HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle>
): HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle> {
  return JSON.parse(JSON.stringify(snapshot));
}

export function pushHistorySnapshot<TSavedRect, TSavedPolygon, TSavedCircle>(
  history: HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle>[],
  index: number,
  snapshot: HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle>,
  maxLength: number = 50
): HistoryState<TSavedRect, TSavedPolygon, TSavedCircle> {
  const nextIndex = index + 1;
  const currentHistory = history.slice(0, nextIndex);
  const nextHistory = [...currentHistory, cloneHistorySnapshot(snapshot)];

  if (nextHistory.length > maxLength) {
    nextHistory.shift();
  }

  return {
    history: nextHistory,
    index: nextHistory.length - 1,
  };
}

export function stepHistoryBackward<TSavedRect, TSavedPolygon, TSavedCircle>(
  history: HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle>[],
  index: number
): {
  snapshot: HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle>;
  index: number;
} | null {
  if (index <= 0) return null;

  const nextIndex = index - 1;
  return {
    snapshot: cloneHistorySnapshot(history[nextIndex]),
    index: nextIndex,
  };
}

export function stepHistoryForward<TSavedRect, TSavedPolygon, TSavedCircle>(
  history: HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle>[],
  index: number
): {
  snapshot: HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle>;
  index: number;
} | null {
  if (index >= history.length - 1) return null;

  const nextIndex = index + 1;
  return {
    snapshot: cloneHistorySnapshot(history[nextIndex]),
    index: nextIndex,
  };
}

export function removeDefectAtIndex<TSavedRect, TSavedPolygon, TSavedCircle>(
  type: DefectCollectionType,
  index: number,
  rects: TSavedRect[],
  polygons: TSavedPolygon[],
  circles: TSavedCircle[]
): HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle> {
  if (type === "rect") {
    const nextRects = [...rects];
    nextRects.splice(index, 1);
    return {
      rects: nextRects,
      polygons,
      circles,
      pixelRatio: 0,
    };
  }

  if (type === "polygon") {
    const nextPolygons = [...polygons];
    nextPolygons.splice(index, 1);
    return {
      rects,
      polygons: nextPolygons,
      circles,
      pixelRatio: 0,
    };
  }

  const nextCircles = [...circles];
  nextCircles.splice(index, 1);
  return {
    rects,
    polygons,
    circles: nextCircles,
    pixelRatio: 0,
  };
}

export function isSameHistorySnapshot<TSavedRect, TSavedPolygon, TSavedCircle>(
  left: HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle>,
  right: HistorySnapshotState<TSavedRect, TSavedPolygon, TSavedCircle>
) {
  return JSON.stringify(left) === JSON.stringify(right);
}
