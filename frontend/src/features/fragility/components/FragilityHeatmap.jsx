import { useLayoutEffect, useRef, useState } from "react";

const LABEL_MARGIN = 64;
const MIN_CELL = 16;
const MAX_CELL = 46;

function lerp(a, b, t) {
  return Math.round(a + (b - a) * t);
}

function corrColor(rho, isDiag) {
  if (isDiag) return "#1c2128";
  const v = Math.max(0, Math.min(1, Math.abs(rho)));
  if (v < 0.5) {
    // dark slate → amber (low correlation stays quiet on black)
    const t = v * 2;
    return `rgb(${lerp(20, 224, t)},${lerp(24, 165, t)},${lerp(30, 46, t)})`;
  }
  // amber → red (hot, correlated pairs)
  const t = (v - 0.5) * 2;
  return `rgb(${lerp(224, 250, t)},${lerp(165, 82, t)},${lerp(46, 82, t)})`;
}

export default function FragilityHeatmap({ correlation }) {
  const [tooltip, setTooltip] = useState(null);
  const containerRef = useRef(null);
  const [width, setWidth] = useState(0);

  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;
    const update = () => setWidth(el.clientWidth);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const symbols = correlation?.symbols ?? [];
  const matrix = correlation?.matrix ?? [];
  const N = symbols.length;

  if (!N || !matrix.length) {
    return (
      <p className="font-mono text-[0.625rem] uppercase tracking-[0.1em] text-[var(--color-text-faint)] py-4">
        Correlation data unavailable
      </p>
    );
  }

  // Grow cells to fill the panel; clamp so tiny portfolios don't balloon and
  // large ones stay legible (and scroll via the container instead).
  const avail = width ? width - LABEL_MARGIN - 8 : N * 28;
  const cell = Math.max(MIN_CELL, Math.min(MAX_CELL, Math.floor(avail / N)));
  const font = Math.max(9, Math.min(12, Math.round(cell * 0.4)));
  const svgW = LABEL_MARGIN + N * cell + 8;
  const svgH = LABEL_MARGIN + N * cell + 8;

  return (
    <div ref={containerRef} className="relative overflow-auto">
      <svg width={svgW} height={svgH} style={{ fontFamily: "JetBrains Mono, monospace" }}>
        {/* X-axis labels — rotated -45° above the grid */}
        {symbols.map((t, j) => (
          <text
            key={`xl-${j}`}
            x={LABEL_MARGIN + j * cell + cell / 2}
            y={LABEL_MARGIN - 4}
            fontSize={font}
            fill="var(--color-text-faint)"
            textAnchor="start"
            transform={`rotate(-45,${LABEL_MARGIN + j * cell + cell / 2},${LABEL_MARGIN - 4})`}
          >
            {t}
          </text>
        ))}

        {/* Y-axis labels — right-aligned left of grid */}
        {symbols.map((t, i) => (
          <text
            key={`yl-${i}`}
            x={LABEL_MARGIN - 6}
            y={LABEL_MARGIN + i * cell + cell / 2 + font / 3}
            fontSize={font}
            fill="var(--color-text-faint)"
            textAnchor="end"
          >
            {t}
          </text>
        ))}

        {/* N×N cells */}
        {matrix.map((row, i) =>
          row.map((val, j) => {
            const x = LABEL_MARGIN + j * cell;
            const y = LABEL_MARGIN + i * cell;
            return (
              <rect
                key={`${i}-${j}`}
                x={x}
                y={y}
                width={cell - 1}
                height={cell - 1}
                fill={corrColor(val, i === j)}
                rx={1}
                onMouseEnter={() =>
                  // Flip tooltip to left side for right-half columns to avoid clipping
                  setTooltip({ x: j > N / 2 ? x - cell * 5 : x + cell, y, a: symbols[i], b: symbols[j], val })
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
            background: "var(--color-surface-strong)",
            border: "1px solid var(--color-border-strong)",
            borderRadius: "var(--radius-sm)",
            padding: "4px 8px",
            fontSize: "var(--text-xs)",
            fontFamily: "var(--font-mono)",
            color: "var(--color-text)",
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
