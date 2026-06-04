const URGENCY_STYLES = {
  ACT: "border border-[rgba(248,81,73,0.4)] bg-[rgba(248,81,73,0.12)] text-[var(--loss)]",
  WATCH: "border border-[rgba(210,153,34,0.4)] bg-[rgba(210,153,34,0.12)] text-[var(--warning)]",
  MONITOR: "border border-[rgba(139,148,158,0.3)] bg-[rgba(139,148,158,0.08)] text-[var(--text-3)]",
};

const GRID = "grid grid-cols-[1fr_80px_90px_80px_100px_1fr_90px_100px]";

export default function FragilityHoldingsTable({ holdings = [], medianMrc = 0, onSimulate }) {
  if (!holdings.length) {
    return (
      <p className="text-[var(--text-3)] text-[var(--text-sm)] py-4">
        No holdings data available.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      {/* Header row */}
      <div className={`${GRID} px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-3)] text-[var(--text-xs)] uppercase tracking-wider border-b border-[var(--border-subtle)]`}>
        <span>Ticker</span>
        <span className="text-right">Weight</span>
        <span className="text-right">Eff. Weight</span>
        <span className="text-right">MRC</span>
        <span className="text-right">Trim Target</span>
        <span>Signals</span>
        <span className="text-center">Urgency</span>
        <span className="text-center">Action</span>
      </div>

      {/* Data rows */}
      {holdings.map((h) => {
        const mrcHigh = h.mrc > 2 * medianMrc;
        const ewHigh = h.hidden_risk;

        return (
          <div
            key={h.ticker}
            className={`${GRID} px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] border-b border-[var(--border-subtle)] hover:bg-[var(--surface-hover)] transition-colors`}
          >
            <span className="font-mono text-[var(--text-1)] font-medium">
              {h.ticker}
            </span>
            <span className="text-right text-[var(--text-2)]">
              {h.weight.toFixed(1)}%
            </span>
            <span
              className="text-right"
              style={{
                color: ewHigh ? "var(--warning)" : "var(--text-2)",
                backgroundColor: ewHigh ? "rgba(210,153,34,0.08)" : "transparent",
                borderRadius: "var(--radius-sm)",
                padding: "0 4px",
              }}
            >
              {h.effective_weight.toFixed(1)}%
            </span>
            <span
              className="text-right"
              style={{ color: mrcHigh ? "var(--loss)" : "var(--text-2)" }}
            >
              {h.mrc.toFixed(1)}%
            </span>
            <span className="text-right text-[var(--text-2)]">
              {h.trim_target_weight.toFixed(1)}%
            </span>
            <span className="flex flex-wrap gap-1 items-center">
              {h.signals.map((s) => (
                <span
                  key={s}
                  className="text-[var(--text-xs)] text-[var(--text-3)] border border-[var(--border-subtle)] rounded px-1"
                >
                  {s}
                </span>
              ))}
            </span>
            <span className="flex justify-center items-center">
              <span
                className={`text-[var(--text-xs)] px-2 py-0.5 rounded-full font-medium ${URGENCY_STYLES[h.urgency]}`}
              >
                {h.urgency}
              </span>
            </span>
            <span className="flex justify-center items-center">
              <button
                onClick={() => onSimulate(h)}
                className="text-[var(--text-xs)] px-2 py-1 rounded border border-[var(--border-subtle)] text-[var(--accent)] hover:bg-[rgba(75,141,255,0.08)] transition-colors"
              >
                Simulate
              </button>
            </span>
          </div>
        );
      })}
    </div>
  );
}
