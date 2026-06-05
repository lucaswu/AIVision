import React, { useMemo, useRef } from "react";
import { Modal, Typography } from "antd";
import type { DoubleWireResult } from "../../../utils/api";

const { Text } = Typography;

const PROFILE_COLOR = "#4C78A8";
const WIRE_COLOR = "#13c2c2";
const GAP_COLOR = "#eb2fdb";
const RESOLVED_COLOR = "#2ca02c";
const UNRESOLVED_COLOR = "#faad14";

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
  getContainer,
}) => {
  const clipPathIdRef = useRef(`double-wire-clip-${Math.random().toString(36).slice(2)}`);
  const payload = result.result;
  const profile = payload?.profile ?? [];
  const pairs = payload?.pairs ?? [];
  const finiteValues = useMemo(() => profile.filter(Number.isFinite), [profile]);

  const chart = useMemo(() => {
    const width = 1080;
    const height = 650;
    const plotX = 70;
    const plotW = 1000;
    const topY = 54;
    const topH = 250;
    const bottomY = 360;
    const bottomH = 250;
    const xMax = Math.max(stripWidth - 1, profile.length - 1, 1);
    const profileMin = finiteValues.length > 0 ? Math.min(...finiteValues) : 0;
    const profileMax = finiteValues.length > 0 ? Math.max(...finiteValues) : 1;
    const profileRange = Math.max(profileMax - profileMin, 1);
    const yMin = profileMin - profileRange * 0.05;
    const yMax = profileMax + profileRange * 0.05;

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
      yMin,
      yMax,
      xScale: (x: number) => plotX + (clamp(x, 0, xMax) / xMax) * plotW,
      yScale: (y: number) => bottomY + bottomH - ((y - yMin) / Math.max(yMax - yMin, 1)) * bottomH,
      topRowScale: (row: number) => topY + (clamp(row, 0, Math.max(stripHeight - 1, 1)) / Math.max(stripHeight - 1, 1)) * topH,
    };
  }, [finiteValues, profile.length, stripHeight, stripWidth]);

  const profilePath = useMemo(() => {
    if (profile.length === 0) return "";
    return profile
      .map((value, index) => {
        const y = Number.isFinite(value) ? value : chart.yMin;
        return `${index === 0 ? "M" : "L"} ${chart.xScale(index).toFixed(2)} ${chart.yScale(y).toFixed(2)}`;
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
  const yTicks = buildYTicks(chart.yMin, chart.yMax);
  const titleParts = [
    `${getStem(fileName)} | line: ${stripWidth}px`,
    `expand: ${expand}`,
    `band: ${bandWidth}`,
    `film: ${payload.film_type}`,
    `pairs: ${payload.num_pairs ?? pairs.length}`,
  ];
  if (payload.first_unresolved_group !== null && payload.first_unresolved_group !== undefined) {
    titleParts.push(`1st unres.: D${payload.first_unresolved_group}`);
  }

  const markerCircle = (index: number, color: string, key: string) => {
    const value = profile[index];
    if (!Number.isFinite(value)) return null;
    return (
      <circle
        key={key}
        cx={chart.xScale(index)}
        cy={chart.yScale(value)}
        r={4.2}
        fill="none"
        stroke={color}
        strokeWidth={2}
      />
    );
  };

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
      <div style={{ overflowX: "auto", paddingTop: 4 }}>
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
            Perpendicular (px)
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
          {xTicks.map(tick => (
            <g key={`bottom-x-${tick}`}>
              <line x1={chart.xScale(tick)} x2={chart.xScale(tick)} y1={chart.bottomY + chart.bottomH} y2={chart.bottomY + chart.bottomH + 5} stroke="#111" />
              <text x={chart.xScale(tick)} y={chart.bottomY + chart.bottomH + 22} textAnchor="middle" fontSize={16} fill="#222">
                {tick}
              </text>
            </g>
          ))}

          <g clipPath={`url(#${clipPathIdRef.current})`}>
            {pairs.map(pair => {
              const color = pair.dip_percent >= 20 ? RESOLVED_COLOR : UNRESOLVED_COLOR;
              const x1 = chart.xScale(Math.min(pair.wire_a_idx, pair.wire_b_idx));
              const x2 = chart.xScale(Math.max(pair.wire_a_idx, pair.wire_b_idx));
              return (
                <rect
                  key={`span-${pair.group}`}
                  x={x1}
                  y={chart.bottomY}
                  width={Math.max(1, x2 - x1)}
                  height={chart.bottomH}
                  fill={color}
                  opacity={0.12}
                />
              );
            })}
            <path d={profilePath} fill="none" stroke={PROFILE_COLOR} strokeWidth={1.6} />
            {pairs.flatMap(pair => [
              markerCircle(pair.wire_a_idx, WIRE_COLOR, `wire-a-${pair.group}`),
              markerCircle(pair.wire_b_idx, WIRE_COLOR, `wire-b-${pair.group}`),
              markerCircle(pair.gap_idx, GAP_COLOR, `gap-${pair.group}`),
            ])}
          </g>

          {pairs.map(pair => {
            const gapValue = profile[pair.gap_idx];
            if (!Number.isFinite(gapValue)) return null;
            const color = pair.dip_percent >= 20 ? RESOLVED_COLOR : UNRESOLVED_COLOR;
            const mid = (pair.wire_a_idx + pair.wire_b_idx) / 2;
            const labelY = clamp(chart.yScale(gapValue) - 18, chart.bottomY + 12, chart.bottomY + chart.bottomH - 8);
            return (
              <text
                key={`label-${pair.group}`}
                x={chart.xScale(mid)}
                y={labelY}
                textAnchor="middle"
                fontSize={10}
                fill={color}
                fontWeight={600}
              >
                D{pair.group}:{pair.dip_percent.toFixed(0)}%
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
            Profile position (px)
          </text>
          <text
            x={24}
            y={chart.bottomY + chart.bottomH / 2}
            transform={`rotate(-90 24 ${chart.bottomY + chart.bottomH / 2})`}
            textAnchor="middle"
            fontSize={16}
            fill="#222"
          >
            Gray value
          </text>

          <g transform={`translate(${chart.plotX + chart.plotW - 128}, ${chart.bottomY + 12})`}>
            <rect x={0} y={0} width={122} height={64} fill="#fff" stroke="#d9d9d9" opacity={0.96} />
            <line x1={10} y1={16} x2={34} y2={16} stroke={PROFILE_COLOR} strokeWidth={1.6} />
            <text x={42} y={20} fontSize={11} fill="#222">Profile</text>
            <circle cx={22} cy={34} r={4.2} fill="none" stroke={WIRE_COLOR} strokeWidth={2} />
            <text x={42} y={38} fontSize={11} fill="#222">BAM wires</text>
            <circle cx={22} cy={50} r={4.2} fill="none" stroke={GAP_COLOR} strokeWidth={2} />
            <text x={42} y={54} fontSize={11} fill="#222">BAM gaps</text>
          </g>
        </svg>
      </div>
    </Modal>
  );
};

export default DoubleWireVisualizationModal;
