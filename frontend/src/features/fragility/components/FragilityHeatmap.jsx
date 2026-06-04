import { useState } from "react";

const CELL = 28;
const LABEL_MARGIN = 64;
const FONT = 10;

function corrColor(rho, isDiag) {
  if (isDiag) return "#1c2128";
  const v = Math.max(0, Math.min(1, Math.abs(rho)));
  if (v < 0.5) {
    // white → amber interpolation
    const t = v * 2;
    const r = Math.round(255 + (210 - 255) * t);
    const g = Math.round(255 + (153 - 255) * t);
    const b = Math.round(255 + (34 - 255) * t);
    return `rgb(${r},${g},${b})`;
  }
  // amber → red interpolation
  const t = (v - 0.5) * 2;
  const r = Math.round(210 + (248 - 210) * t);
  const g = Math.round(153 + (81 - 153) * t);
  const b = Math.round(34 + (73 - 34) * t);
  return `rgb(${r},${g},${b})`;
}

export default function FragilityHeatmap({ corr_matrix = [], tickers_corr = [] }) {
  const [tooltip, setTooltip] = useState(null);
  const N = tickers_corr.length;

  if (!N || !corr_matrix.length) {
    return (
      <p className="text-[var(--text-3)] text-[var(--text-sm)] py-4">
        Correlation data unavailable.
      </p>
    );
  }

  const svgW = LABEL_MARGIN + N * CELL + 8;
  const svgH = LABEL_MARGIN + N * CELL + 8;

  return (
    <div className="relative overflow-auto">
      <svg width={svgW} height={svgH} style={{ fontFamily: "IBM Plex Mono, monospace" }}>
        {/* X-axis labels — rotated -45° above the grid */}
        {tickers_corr.map((t, j) => (
          <text
            key={`xl-${j}`}
            x={LABEL_MARGIN + j * CELL + CELL / 2}
            y={LABEL_MARGIN - 4}
            fontSize={FONT}
            fill="var(--text-3)"
            textAnchor="start"
            transform={`rotate(-45,${LABEL_MARGIN + j * CELL + CELL / 2},${LABEL_MARGIN - 4})`}
          >
            {t}
          </text>
        ))}

        {/* Y-axis labels — right-aligned left of grid */}
        {tickers_corr.map((t, i) => (
          <text
            key={`yl-${i}`}
            x={LABEL_MARGIN - 6}
            y={LABEL_MARGIN + i * CELL + CELL / 2 + FONT / 3}
            fontSize={FONT}
            fill="var(--text-3)"
            textAnchor="end"
          >
            {t}
          </text>
        ))}

        {/* N×N cells */}
        {corr_matrix.map((row, i) =>
          row.map((val, j) => {
            const x = LABEL_MARGIN + j * CELL;
            const y = LABEL_MARGIN + i * CELL;
            return (
              <rect
                key={`${i}-${j}`}
                x={x}
                y={y}
                width={CELL - 1}
                height={CELL - 1}
                fill={corrColor(val, i === j)}
                rx={1}
                onMouseEnter={() =>
                  setTooltip({ x: x + CELL, y, a: tickers_corr[i], b: tickers_corr[j], val })
                }
                onMouseLeave={() => setTooltip(null)}
                style={{ cursor: "default" }}
              />
            );
          })
        )}
      </svg>

      {/* Hover tooltip */}
      {tooltip && (
        <div
          style={{
            position: "absolute",
            left: tooltip.x + 4,
            top: tooltip.y,
            pointerEvents: "none",
            background: "var(--surface-2)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            padding: "4px 8px",
            fontSize: "var(--text-xs)",
            color: "var(--text-1)",
            whiteSpace: "nowrap",
            zIndex: 10,
          }}
        >
          {tooltip.a} × {tooltip.b}: ρ = {tooltip.val.toFixed(3)}
        </div>
      )}
    </div>
  );
}
