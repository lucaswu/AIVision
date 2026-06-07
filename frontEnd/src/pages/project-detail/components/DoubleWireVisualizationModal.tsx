import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Alert, Button, InputNumber, Modal, Space, Typography } from "antd";
import type { DoubleWirePair, DoubleWireResult } from "../../../utils/api";

const { Text } = Typography;

const PROFILE_COLOR = "#4C78A8";
const WIRE_COLOR = "#13c2c2";
const GAP_COLOR = "#eb2fdb";
const RESOLVED_COLOR = "#2ca02c";
const UNRESOLVED_COLOR = "#faad14";
const SELECTED_COLOR = "#1677ff";

type ManualMarkerKey = "a" | "c" | "b";

interface DoubleWireResolutionInfo {
  resolutionLpMm: number;
  resolvingPowerMm: number;
}

interface ManualMarker {
  index: number;
  gray: number;
}

interface ProfilePanState {
  pointerId: number;
  startClientX: number;
  startRange: { start: number; end: number };
}

interface DoubleWireVisualizationModalProps {
  open: boolean;
  onClose: () => void;
  stripDataUrl: string;
  result: DoubleWireResult;
  fileName: string;
  expand: number;
  bandWidth: number;
  stripWidth: number;
  stripHeight: number;
  automaticLinePair?: number | null;
  resolutionTable: Record<number, DoubleWireResolutionInfo>;
  onApplyManualResolution: (linePair: number) => void;
  getContainer?: () => HTMLElement;
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const formatNumber = (value: number) => {
  if (Math.abs(value) >= 100) return value.toFixed(0);
  if (Math.abs(value) >= 10) return value.toFixed(1).replace(/\.0$/, "");
  return value.toFixed(2).replace(/\.?0+$/, "");
};

const buildXTicks = (maxIndex: number) => {
  const max = Math.max(0, Math.floor(maxIndex));
  const step = max <= 500 ? 50 : max <= 1000 ? 100 : 200;
  const ticks: number[] = [];
  for (let tick = 0; tick <= max; tick += step) {
    ticks.push(tick);
  }
  if (ticks.length === 1 && max > 0) ticks.push(max);
  return ticks;
};

const niceTickStep = (rawStep: number) => {
  if (!Number.isFinite(rawStep) || rawStep <= 0) return 1;
  const power = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const fraction = rawStep / power;
  if (fraction <= 1) return power;
  if (fraction <= 2) return 2 * power;
  if (fraction <= 5) return 5 * power;
  return 10 * power;
};

const buildRangeXTicks = (minIndex: number, maxIndex: number) => {
  const min = Math.max(0, minIndex);
  const max = Math.max(min, maxIndex);
  const range = Math.max(max - min, 1);
  const step = niceTickStep(range / 8);
  const ticks: number[] = [];
  const start = Math.ceil(min / step) * step;
  for (let tick = start; tick <= max + step * 0.5; tick += step) {
    ticks.push(Number(tick.toFixed(6)));
  }
  if (ticks.length === 0) ticks.push(min);
  return ticks.slice(0, 10);
};

const buildYTicks = (min: number, max: number) => {
  const range = Math.max(max - min, 1);
  const step = niceTickStep(range / 5);
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let value = start; value <= max + step * 0.5; value += step) {
    ticks.push(Number(value.toFixed(6)));
  }
  return ticks.slice(0, 7);
};

const getStem = (fileName: string) => fileName.replace(/\.[^.]+$/, "");

const formatFilmType = (filmType: string) => {
  if (filmType === "negative") return "负片";
  if (filmType === "positive") return "正片";
  return filmType || "--";
};

const formatGray = (value: number | null | undefined) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toFixed(2).replace(/\.?0+$/, "");
};

const formatResolutionNumber = (value: number) => value.toFixed(3).replace(/\.?0+$/, "");

const formatContrast = (value: number | null) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${(value * 100).toFixed(2).replace(/\.?0+$/, "")}%`;
};

const getProfileValue = (profile: number[], index: number, fallback: number) => {
  if (Number.isFinite(fallback)) return fallback;
  const value = profile[index];
  return Number.isFinite(value) ? value : NaN;
};

const computeContrast = (a: number, b: number, c: number) => {
  if (!Number.isFinite(a) || !Number.isFinite(b) || !Number.isFinite(c)) return null;
  const denominator = a + b;
  if (denominator === 0) return null;
  return (a + b - 2 * c) / denominator;
};

const getPairContrastInfo = (pair: DoubleWirePair, profile: number[]) => {
  const a = getProfileValue(profile, pair.wire_a_idx, pair.wire_a_gray);
  const b = getProfileValue(profile, pair.wire_b_idx, pair.wire_b_gray);
  const c = getProfileValue(profile, pair.gap_idx, pair.gap_gray);
  return { a, b, c, contrast: computeContrast(a, b, c) };
};

const getNextMarkerKey = (key: ManualMarkerKey): ManualMarkerKey => {
  if (key === "a") return "c";
  if (key === "c") return "b";
  return "a";
};

export const DoubleWireVisualizationModal: React.FC<DoubleWireVisualizationModalProps> = ({
  open,
  onClose,
  stripDataUrl,
  result,
  fileName,
  expand,
  bandWidth,
  stripWidth,
  stripHeight,
  automaticLinePair,
  resolutionTable,
  onApplyManualResolution,
  getContainer,
}) => {
  const clipPathIdRef = useRef(`double-wire-clip-${Math.random().toString(36).slice(2)}`);
  const suppressNextProfileClickRef = useRef(false);
  const [manualMode, setManualMode] = useState(false);
  const [selectedPairGroup, setSelectedPairGroup] = useState<number | null>(null);
  const [manualLinePair, setManualLinePair] = useState<number | null>(automaticLinePair ?? null);
  const [activeManualMarker, setActiveManualMarker] = useState<ManualMarkerKey>("a");
  const [manualMarkers, setManualMarkers] = useState<Partial<Record<ManualMarkerKey, ManualMarker>>>({});
  const [profileZoomRange, setProfileZoomRange] = useState<{ start: number; end: number } | null>(null);
  const [profilePanState, setProfilePanState] = useState<ProfilePanState | null>(null);
  const payload = result.result;
  const profile = useMemo(() => payload?.profile ?? [], [payload?.profile]);
  const pairs = useMemo(() => payload?.pairs ?? [], [payload?.pairs]);
  const finiteValues = useMemo(() => profile.filter(Number.isFinite), [profile]);
  const tableLinePairs = useMemo(
    () => Object.keys(resolutionTable).map(Number).filter(Number.isFinite).sort((a, b) => a - b),
    [resolutionTable]
  );
  const minTableLinePair = tableLinePairs[0] ?? 1;
  const maxTableLinePair = tableLinePairs[tableLinePairs.length - 1] ?? 99;
  const selectedPair = useMemo(
    () => pairs.find(pair => pair.group === selectedPairGroup) ?? null,
    [pairs, selectedPairGroup]
  );
  const selectedPairContrast = useMemo(
    () => selectedPair ? getPairContrastInfo(selectedPair, profile) : null,
    [profile, selectedPair]
  );
  const manualContrast = useMemo(() => {
    const a = manualMarkers.a?.gray;
    const b = manualMarkers.b?.gray;
    const c = manualMarkers.c?.gray;
    if (typeof a !== "number" || typeof b !== "number" || typeof c !== "number") return null;
    return computeContrast(a, b, c);
  }, [manualMarkers]);
  const selectedLinePairInfo = manualLinePair !== null ? resolutionTable[manualLinePair] : undefined;

  useEffect(() => {
    if (!open) return;
    const initialPair =
      (typeof automaticLinePair === "number" && pairs.some(pair => pair.group === automaticLinePair))
        ? automaticLinePair
        : (pairs[0]?.group ?? null);
    setSelectedPairGroup(initialPair);
    setManualLinePair(automaticLinePair ?? initialPair ?? null);
    setManualMarkers({});
    setActiveManualMarker("a");
    setManualMode(false);
    setProfileZoomRange(null);
    setProfilePanState(null);
  }, [automaticLinePair, open, pairs]);

  const chart = useMemo(() => {
    const width = 1080;
    const height = 690;
    const plotX = 70;
    const plotW = 1000;
    const topY = 54;
    const topH = 250;
    const bottomY = 360;
    const bottomH = 250;
    const xMax = Math.max(stripWidth - 1, profile.length - 1, 1);
    const zoomStart = clamp(profileZoomRange?.start ?? 0, 0, xMax);
    const zoomEnd = clamp(profileZoomRange?.end ?? xMax, zoomStart + 1, xMax);
    const profileStart = zoomEnd > zoomStart ? zoomStart : 0;
    const profileEnd = zoomEnd > zoomStart ? zoomEnd : xMax;
    const profileRange = Math.max(profileEnd - profileStart, 1);
    const profileMin = finiteValues.length > 0 ? Math.min(...finiteValues) : 0;
    const profileMax = finiteValues.length > 0 ? Math.max(...finiteValues) : 1;
    const yRange = Math.max(profileMax - profileMin, 1);
    const yMin = profileMin - yRange * 0.05;
    const yMax = profileMax + yRange * 0.05;

    return {
      width,
      height,
      plotX,
      plotW,
      topY,
      topH,
      bottomY,
      bottomH,
      xMax,
      profileStart,
      profileEnd,
      yMin,
      yMax,
      xScale: (x: number) => plotX + (clamp(x, 0, xMax) / xMax) * plotW,
      profileXScale: (x: number) => plotX + ((x - profileStart) / profileRange) * plotW,
      profileXInvert: (svgX: number) => profileStart + ((svgX - plotX) / plotW) * profileRange,
      yScale: (y: number) => bottomY + bottomH - ((y - yMin) / Math.max(yMax - yMin, 1)) * bottomH,
      topRowScale: (row: number) => topY + (clamp(row, 0, Math.max(stripHeight - 1, 1)) / Math.max(stripHeight - 1, 1)) * topH,
    };
  }, [finiteValues, profile.length, profileZoomRange, stripHeight, stripWidth]);

  const handleManualMarkerClick = useCallback((e: React.MouseEvent<SVGElement>) => {
    if (!manualMode) return;
    if (suppressNextProfileClickRef.current) {
      suppressNextProfileClickRef.current = false;
      return;
    }
    if (profilePanState) return;
    if (profile.length === 0) return;

    const svg = e.currentTarget.ownerSVGElement;
    if (!svg) return;

    const svgRect = svg.getBoundingClientRect();
    const svgX = ((e.clientX - svgRect.left) / Math.max(svgRect.width, 1)) * chart.width;
    const rawIndex = chart.profileXInvert(svgX);
    const index = Math.round(clamp(rawIndex, 0, profile.length - 1));
    const gray = profile[index];
    if (!Number.isFinite(gray)) return;

    setManualMarkers(prev => ({
      ...prev,
      [activeManualMarker]: { index, gray },
    }));
    setSelectedPairGroup(null);
    setActiveManualMarker(getNextMarkerKey(activeManualMarker));
  }, [activeManualMarker, chart, manualMode, profile, profilePanState]);

  const handleProfileWheel = useCallback((e: React.WheelEvent<SVGElement>) => {
    if (!manualMode) return;

    e.preventDefault();
    e.stopPropagation();

    const svg = e.currentTarget.ownerSVGElement;
    if (!svg) return;

    const svgRect = svg.getBoundingClientRect();
    const svgX = ((e.clientX - svgRect.left) / Math.max(svgRect.width, 1)) * chart.width;
    const anchor = clamp(chart.profileXInvert(svgX), 0, chart.xMax);
    const currentStart = chart.profileStart;
    const currentEnd = chart.profileEnd;
    const currentSpan = Math.max(currentEnd - currentStart, 1);
    const minSpan = Math.max(8, chart.xMax * 0.04);
    const nextSpan = clamp(currentSpan * (e.deltaY < 0 ? 0.82 : 1.22), minSpan, chart.xMax);
    const anchorRatio = (anchor - currentStart) / currentSpan;

    let nextStart = anchor - anchorRatio * nextSpan;
    let nextEnd = nextStart + nextSpan;

    if (nextStart < 0) {
      nextEnd -= nextStart;
      nextStart = 0;
    }
    if (nextEnd > chart.xMax) {
      nextStart -= nextEnd - chart.xMax;
      nextEnd = chart.xMax;
    }
    nextStart = clamp(nextStart, 0, chart.xMax);
    nextEnd = clamp(nextEnd, nextStart + minSpan, chart.xMax);

    if (nextStart <= 0.001 && nextEnd >= chart.xMax - 0.001) {
      setProfileZoomRange(null);
      return;
    }

    setProfileZoomRange({ start: nextStart, end: nextEnd });
  }, [chart, manualMode]);

  const handleProfilePointerDown = useCallback((e: React.PointerEvent<SVGRectElement>) => {
    if (!manualMode) return;
    if (e.button !== 0) return;
    e.preventDefault();

    e.currentTarget.setPointerCapture(e.pointerId);
    setProfilePanState({
      pointerId: e.pointerId,
      startClientX: e.clientX,
      startRange: { start: chart.profileStart, end: chart.profileEnd },
    });
  }, [chart.profileEnd, chart.profileStart, manualMode]);

  const handleProfilePointerMove = useCallback((e: React.PointerEvent<SVGRectElement>) => {
    if (!manualMode || !profilePanState || profilePanState.pointerId !== e.pointerId) return;

    const span = Math.max(profilePanState.startRange.end - profilePanState.startRange.start, 1);
    const dx = e.clientX - profilePanState.startClientX;
    if (Math.abs(dx) > 3) {
      suppressNextProfileClickRef.current = true;
    }
    const delta = -(dx / Math.max(chart.plotW, 1)) * span;
    let nextStart = profilePanState.startRange.start + delta;
    let nextEnd = profilePanState.startRange.end + delta;

    if (nextStart < 0) {
      nextEnd -= nextStart;
      nextStart = 0;
    }
    if (nextEnd > chart.xMax) {
      nextStart -= nextEnd - chart.xMax;
      nextEnd = chart.xMax;
    }

    nextStart = clamp(nextStart, 0, chart.xMax);
    nextEnd = clamp(nextEnd, nextStart + 1, chart.xMax);

    if (nextStart <= 0.001 && nextEnd >= chart.xMax - 0.001) {
      setProfileZoomRange(null);
      return;
    }
    setProfileZoomRange({ start: nextStart, end: nextEnd });
  }, [chart.plotW, chart.xMax, manualMode, profilePanState]);

  const handleProfilePointerEnd = useCallback((e: React.PointerEvent<SVGRectElement>) => {
    if (profilePanState?.pointerId === e.pointerId) {
      setProfilePanState(null);
    }
  }, [profilePanState]);

  const profilePath = useMemo(() => {
    if (profile.length === 0) return "";
    const startIndex = Math.max(0, Math.floor(chart.profileStart) - 1);
    const endIndex = Math.min(profile.length - 1, Math.ceil(chart.profileEnd) + 1);
    return profile
      .slice(startIndex, endIndex + 1)
      .map((value, offset) => {
        const index = startIndex + offset;
        const y = Number.isFinite(value) ? value : chart.yMin;
        return `${offset === 0 ? "M" : "L"} ${chart.profileXScale(index).toFixed(2)} ${chart.yScale(y).toFixed(2)}`;
      })
      .join(" ");
  }, [chart, profile]);

  if (!payload || profile.length === 0) {
    return (
      <Modal
        title="双丝分辨率可视化"
        open={open}
        onCancel={onClose}
        footer={null}
        width="min(1180px, calc(100vw - 32px))"
        centered
        getContainer={getContainer}
      >
        <Text type="secondary">暂无可视化结果</Text>
      </Modal>
    );
  }

  const topCenter = stripHeight / 2;
  const halfBand = (bandWidth - 1) / 2;
  const xTicks = buildXTicks(chart.xMax);
  const profileXTicks = buildRangeXTicks(chart.profileStart, chart.profileEnd);
  const yTicks = buildYTicks(chart.yMin, chart.yMax);
  const titleParts = [
    `${getStem(fileName)} | 线长: ${stripWidth}px`,
    `扩展: ${expand}`,
    `带宽: ${bandWidth}`,
    `底片: ${formatFilmType(payload.film_type)}`,
    `双丝组: ${payload.num_pairs ?? pairs.length}`,
  ];
  if (payload.first_unresolved_group !== null && payload.first_unresolved_group !== undefined) {
    titleParts.push(`首个未分辨: D${payload.first_unresolved_group}`);
  }

  const markerCircle = (index: number, color: string, key: string) => {
    const value = profile[index];
    if (!Number.isFinite(value)) return null;
    return (
      <circle
        key={key}
        cx={chart.profileXScale(index)}
        cy={chart.yScale(value)}
        r={4.2}
        fill="none"
        stroke={color}
        strokeWidth={2}
        pointerEvents="none"
      />
    );
  };

  const activeMeasurement = selectedPair && selectedPairContrast
    ? {
        label: `D${selectedPair.group}`,
        a: selectedPairContrast.a,
        b: selectedPairContrast.b,
        c: selectedPairContrast.c,
        contrast: selectedPairContrast.contrast,
      }
    : {
        label: "A/C/B",
        a: manualMarkers.a?.gray,
        b: manualMarkers.b?.gray,
        c: manualMarkers.c?.gray,
        contrast: manualContrast,
      };

  const hasActiveMeasurement =
    typeof activeMeasurement.a === "number" ||
    typeof activeMeasurement.b === "number" ||
    typeof activeMeasurement.c === "number";

  const manualPanel = (
    <Space direction="vertical" size={8} style={{ width: "100%" }}>
      <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 10, background: "#fff" }}>
        <Text strong>当前灰度计算</Text>
        <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "56px 1fr", rowGap: 5, fontSize: 12 }}>
          <Text type="secondary">来源</Text>
          <Text>{hasActiveMeasurement ? activeMeasurement.label : "未选择"}</Text>
          <Text type="secondary">A</Text>
          <Text>{formatGray(activeMeasurement.a)}</Text>
          <Text type="secondary">B</Text>
          <Text>{formatGray(activeMeasurement.b)}</Text>
          <Text type="secondary">C</Text>
          <Text>{formatGray(activeMeasurement.c)}</Text>
          <Text type="secondary">对比度</Text>
          <Text strong>{formatContrast(activeMeasurement.contrast)}</Text>
        </div>
      </div>

      <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 10, background: "#fff" }}>
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Text strong>手动取点</Text>
          <Space size={6} wrap>
            {(["a", "c", "b"] as ManualMarkerKey[]).map(markerKey => (
              <Button
                key={markerKey}
                size="small"
                type={activeManualMarker === markerKey ? "primary" : "default"}
                onClick={() => setActiveManualMarker(markerKey)}
              >
                {markerKey.toUpperCase()}
              </Button>
            ))}
            <Button
              size="small"
              onClick={() => {
                setManualMarkers({});
                setSelectedPairGroup(null);
                setActiveManualMarker("a");
              }}
            >
              清空
            </Button>
            <Button size="small" onClick={() => setProfileZoomRange(null)}>
              重置缩放
            </Button>
          </Space>
          <div style={{ display: "grid", gap: 6, fontSize: 12 }}>
            {(["a", "c", "b"] as ManualMarkerKey[]).map(markerKey => {
              const marker = manualMarkers[markerKey];
              return (
                <div
                  key={markerKey}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "28px 1fr 1fr",
                    columnGap: 6,
                    alignItems: "center",
                    background: "#fafafa",
                    border: "1px solid #f0f0f0",
                    borderRadius: 4,
                    padding: "5px 7px",
                  }}
                >
                  <Text type="secondary">{markerKey.toUpperCase()}</Text>
                  <Text>{marker ? `x=${marker.index}` : "--"}</Text>
                  <Text>{marker ? formatGray(marker.gray) : "--"}</Text>
                </div>
              );
            })}
          </div>
        </Space>
      </div>

      <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 10, background: "#fff" }}>
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Text strong>查表写回</Text>
          <Space.Compact style={{ width: "100%" }}>
            <div
              style={{
                width: 64,
                border: "1px solid #d9d9d9",
                borderRight: "none",
                borderRadius: "6px 0 0 6px",
                background: "#fafafa",
                lineHeight: "30px",
                textAlign: "center",
              }}
            >
              D(n)
            </div>
            <InputNumber
              min={minTableLinePair}
              max={maxTableLinePair}
              precision={0}
              value={manualLinePair}
              onChange={(value) => {
                setManualLinePair(typeof value === "number" && Number.isFinite(value) ? value : null);
              }}
              style={{ width: "100%" }}
            />
          </Space.Compact>
          <div style={{ minHeight: 44, background: "#fafafa", border: "1px solid #f0f0f0", borderRadius: 4, padding: "6px 8px" }}>
            {selectedLinePairInfo ? (
              <>
                <Text>{formatResolutionNumber(selectedLinePairInfo.resolutionLpMm)} lp/mm</Text>
                <br />
                <Text type="secondary">{formatResolutionNumber(selectedLinePairInfo.resolvingPowerMm)} mm</Text>
              </>
            ) : (
              <Text type="secondary">未配置该 D(n) 的查表值</Text>
            )}
          </div>
          <Button
            type="primary"
            block
            disabled={manualLinePair === null || !selectedLinePairInfo}
            onClick={() => {
              if (manualLinePair !== null && selectedLinePairInfo) {
                onApplyManualResolution(manualLinePair);
              }
            }}
          >
            应用到双丝分辨率
          </Button>
        </Space>
      </div>
    </Space>
  );

  return (
    <Modal
      title="双丝分辨率可视化"
      open={open}
      onCancel={onClose}
      footer={null}
      width={manualMode ? "min(1340px, calc(100vw - 32px))" : "min(1240px, calc(100vw - 32px))"}
      centered
      getContainer={getContainer}
    >
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
          <Button
            type={manualMode ? "primary" : "default"}
            onClick={() => setManualMode(prev => !prev)}
          >
            {manualMode ? "退出手动标注" : "手动标注"}
          </Button>
        </div>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0, overflowX: "auto", paddingTop: 4 }}>
          <svg
            viewBox={`0 0 ${chart.width} ${chart.height}`}
            style={{ width: "100%", minWidth: 760, height: "auto", display: "block" }}
            role="img"
            aria-label="双丝分辨率可视化"
          >
            <defs>
              <clipPath id={clipPathIdRef.current}>
                <rect x={chart.plotX} y={chart.bottomY} width={chart.plotW} height={chart.bottomH} />
              </clipPath>
            </defs>

            <text x={chart.width / 2} y={22} textAnchor="middle" fontSize={14} fontWeight={600} fill="#333">
              {titleParts.join(" | ")}
            </text>

            <image
              href={stripDataUrl}
              x={chart.plotX}
              y={chart.topY}
              width={chart.plotW}
              height={chart.topH}
              preserveAspectRatio="none"
            />
            <rect x={chart.plotX} y={chart.topY} width={chart.plotW} height={chart.topH} fill="none" stroke="#111" />
            <line
              x1={chart.plotX}
              x2={chart.plotX + chart.plotW}
              y1={chart.topRowScale(topCenter)}
              y2={chart.topRowScale(topCenter)}
              stroke="red"
              strokeWidth={1}
            />
            {[topCenter - halfBand, topCenter + halfBand].map((row, index) => (
              <line
                key={`band-${index}`}
                x1={chart.plotX}
                x2={chart.plotX + chart.plotW}
                y1={chart.topRowScale(row)}
                y2={chart.topRowScale(row)}
                stroke="red"
                strokeWidth={0.7}
                strokeDasharray="2 2"
              />
            ))}

            <text
              x={22}
              y={chart.topY + chart.topH / 2}
              transform={`rotate(-90 22 ${chart.topY + chart.topH / 2})`}
              textAnchor="middle"
              fontSize={16}
              fill="#222"
            >
              垂直方向 (px)
            </text>
            {[
              { row: 0, label: `-${expand}` },
              { row: topCenter, label: "0" },
              { row: stripHeight - 1, label: `+${expand}` },
            ].map(tick => (
              <g key={`top-y-${tick.label}`}>
                <line x1={chart.plotX - 5} x2={chart.plotX} y1={chart.topRowScale(tick.row)} y2={chart.topRowScale(tick.row)} stroke="#111" />
                <text x={chart.plotX - 12} y={chart.topRowScale(tick.row) + 5} textAnchor="end" fontSize={16} fill="#222">
                  {tick.label}
                </text>
              </g>
            ))}
            {xTicks.map(tick => (
              <g key={`top-x-${tick}`}>
                <line x1={chart.xScale(tick)} x2={chart.xScale(tick)} y1={chart.topY + chart.topH} y2={chart.topY + chart.topH + 5} stroke="#111" />
                <text x={chart.xScale(tick)} y={chart.topY + chart.topH + 22} textAnchor="middle" fontSize={16} fill="#222">
                  {tick}
                </text>
              </g>
            ))}

            <rect x={chart.plotX} y={chart.bottomY} width={chart.plotW} height={chart.bottomH} fill="#fff" stroke="#111" />
            {yTicks.map(tick => (
              <g key={`bottom-y-${tick}`}>
                <line x1={chart.plotX - 5} x2={chart.plotX} y1={chart.yScale(tick)} y2={chart.yScale(tick)} stroke="#111" />
                <text x={chart.plotX - 12} y={chart.yScale(tick) + 5} textAnchor="end" fontSize={16} fill="#222">
                  {formatNumber(tick)}
                </text>
              </g>
            ))}
            {profileXTicks.map(tick => (
              <g key={`bottom-x-${tick}`}>
                <line x1={chart.profileXScale(tick)} x2={chart.profileXScale(tick)} y1={chart.bottomY + chart.bottomH} y2={chart.bottomY + chart.bottomH + 5} stroke="#111" />
                <text x={chart.profileXScale(tick)} y={chart.bottomY + chart.bottomH + 22} textAnchor="middle" fontSize={16} fill="#222">
                  {formatNumber(tick)}
                </text>
              </g>
            ))}

            <g clipPath={`url(#${clipPathIdRef.current})`}>
              <rect
                x={chart.plotX}
                y={chart.bottomY}
                width={chart.plotW}
                height={chart.bottomH}
                fill="transparent"
                cursor={manualMode ? "crosshair" : "default"}
                onClick={handleManualMarkerClick}
                onWheel={handleProfileWheel}
                onPointerDown={handleProfilePointerDown}
                onPointerMove={handleProfilePointerMove}
                onPointerUp={handleProfilePointerEnd}
                onPointerCancel={handleProfilePointerEnd}
                onLostPointerCapture={handleProfilePointerEnd}
              />
              {pairs.map(pair => {
                const isSelected = selectedPairGroup === pair.group;
                const color = pair.dip_percent >= 20 ? RESOLVED_COLOR : UNRESOLVED_COLOR;
                const x1 = chart.profileXScale(Math.min(pair.wire_a_idx, pair.wire_b_idx));
                const x2 = chart.profileXScale(Math.max(pair.wire_a_idx, pair.wire_b_idx));
                return (
                  <rect
                    key={`span-${pair.group}`}
                    x={x1}
                    y={chart.bottomY}
                    width={Math.max(1, x2 - x1)}
                    height={chart.bottomH}
                    fill={isSelected ? SELECTED_COLOR : color}
                    opacity={isSelected ? 0.22 : 0.12}
                    stroke={isSelected ? SELECTED_COLOR : "none"}
                    strokeWidth={isSelected ? 1.5 : 0}
                    cursor={manualMode ? "pointer" : "default"}
                    onClick={(e) => {
                      if (!manualMode) return;
                      e.stopPropagation();
                      setSelectedPairGroup(pair.group);
                    }}
                  />
                );
              })}
              <path d={profilePath} fill="none" stroke={PROFILE_COLOR} strokeWidth={1.6} pointerEvents="none" />
              {pairs.flatMap(pair => [
                markerCircle(pair.wire_a_idx, WIRE_COLOR, `wire-a-${pair.group}`),
                markerCircle(pair.wire_b_idx, WIRE_COLOR, `wire-b-${pair.group}`),
                markerCircle(pair.gap_idx, GAP_COLOR, `gap-${pair.group}`),
              ])}
              {manualMode && (["a", "c", "b"] as ManualMarkerKey[]).flatMap(markerKey => {
                const marker = manualMarkers[markerKey];
                if (!marker) return [];
                const x = chart.profileXScale(marker.index);
                const y = chart.yScale(marker.gray);
                return [
                  <line
                    key={`manual-line-${markerKey}`}
                    x1={x}
                    x2={x}
                    y1={chart.bottomY}
                    y2={chart.bottomY + chart.bottomH}
                    stroke={SELECTED_COLOR}
                    strokeWidth={1}
                    strokeDasharray="4 3"
                    pointerEvents="none"
                  />,
                  <circle
                    key={`manual-point-${markerKey}`}
                    cx={x}
                    cy={y}
                    r={5}
                    fill="#fff"
                    stroke={SELECTED_COLOR}
                    strokeWidth={2}
                    pointerEvents="none"
                  />,
                  <text
                    key={`manual-label-${markerKey}`}
                    x={x}
                    y={clamp(y - 10, chart.bottomY + 12, chart.bottomY + chart.bottomH - 6)}
                    textAnchor="middle"
                    fontSize={11}
                    fill={SELECTED_COLOR}
                    fontWeight={700}
                    pointerEvents="none"
                  >
                    {markerKey.toUpperCase()}
                  </text>,
                ];
              })}
            </g>

            {pairs.map(pair => {
              const gapValue = profile[pair.gap_idx];
              if (!Number.isFinite(gapValue)) return null;
              const isSelected = selectedPairGroup === pair.group;
              const color = isSelected ? SELECTED_COLOR : pair.dip_percent >= 20 ? RESOLVED_COLOR : UNRESOLVED_COLOR;
              const mid = (pair.wire_a_idx + pair.wire_b_idx) / 2;
              if (mid < chart.profileStart || mid > chart.profileEnd) return null;
              const labelY = clamp(chart.yScale(gapValue) - 18, chart.bottomY + 12, chart.bottomY + chart.bottomH - 8);
              return (
                <text
                  key={`label-${pair.group}`}
                  x={chart.profileXScale(mid)}
                  y={labelY}
                  textAnchor="middle"
                  fontSize={10}
                  fill={color}
                  fontWeight={isSelected ? 700 : 600}
                  cursor={manualMode ? "pointer" : "default"}
                  onClick={(e) => {
                    if (!manualMode) return;
                    e.stopPropagation();
                    setSelectedPairGroup(pair.group);
                  }}
                >
                  D{pair.group}：{pair.dip_percent.toFixed(0)}%
                </text>
              );
            })}

            <text
              x={chart.plotX + chart.plotW / 2}
              y={chart.bottomY + chart.bottomH + 50}
              textAnchor="middle"
              fontSize={16}
              fill="#222"
            >
              剖面位置 (px)
            </text>
            <text
              x={24}
              y={chart.bottomY + chart.bottomH / 2}
              transform={`rotate(-90 24 ${chart.bottomY + chart.bottomH / 2})`}
              textAnchor="middle"
              fontSize={16}
              fill="#222"
            >
              灰度值
            </text>

            <g transform={`translate(${chart.plotX + chart.plotW - 138}, ${chart.bottomY + 12})`}>
              <rect x={0} y={0} width={132} height={64} fill="#fff" stroke="#d9d9d9" opacity={0.96} />
              <line x1={10} y1={16} x2={34} y2={16} stroke={PROFILE_COLOR} strokeWidth={1.6} />
              <text x={42} y={20} fontSize={11} fill="#222">灰度曲线</text>
              <circle cx={22} cy={34} r={4.2} fill="none" stroke={WIRE_COLOR} strokeWidth={2} />
              <text x={42} y={38} fontSize={11} fill="#222">双丝黑区</text>
              <circle cx={22} cy={50} r={4.2} fill="none" stroke={GAP_COLOR} strokeWidth={2} />
              <text x={42} y={54} fontSize={11} fill="#222">中间白区</text>
            </g>
          </svg>
        </div>
        {manualMode && (
          <div style={{ width: 260, flex: "0 0 260px", maxHeight: 690, overflowY: "auto" }}>
            {manualPanel}
          </div>
        )}
      </div>
      {(result.result_code !== 0 || pairs.length === 0 || !automaticLinePair) && (
        <Alert
          type="info"
          showIcon
          style={{ marginTop: 12 }}
          message="自动 D(n) 未能可靠给出时，可点击“手动标注”，再选择曲线中的 D 组或手动点选 A、C、B，并输入 n 查表写回。"
        />
      )}
    </Modal>
  );
};

export default DoubleWireVisualizationModal;
