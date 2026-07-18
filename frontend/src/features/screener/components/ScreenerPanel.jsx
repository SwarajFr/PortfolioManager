import { useState } from "react";
import Card from "../../../components/ui/Card";
import { TableHeader, TableRow, TableShell } from "../../../components/ui/DataTable";
import EmptyState from "../../../components/ui/EmptyState";
import { useStrategies } from "../hooks/useScreener";
import { postScan } from "../../../services/screenerService";

const RESULT_GRID = "grid-cols-[0.5fr_2fr_1fr_1fr] gap-4 items-center";

export default function ScreenerPanel() {
  const { data: meta } = useStrategies();
  const strategies = meta?.strategies ?? [];

  // Derive selected/weights during render (default: all selected, equal weight).
  // User edits are stored as overrides, so no set-state-in-effect is needed.
  const [selectedOverride, setSelectedOverride] = useState(null);
  const [weightsOverride, setWeightsOverride] = useState(null);
  const selected =
    selectedOverride ?? Object.fromEntries(strategies.map((s) => [s.name, true]));
  const weights =
    weightsOverride ?? Object.fromEntries(strategies.map((s) => [s.name, 1]));

  const [k, setK] = useState("all");
  const [fallbackN, setFallbackN] = useState(10);
  const [scan, setScan] = useState(null);
  const [loading, setLoading] = useState(false);

  const chosen = strategies.filter((s) => selected[s.name]).map((s) => s.name);

  async function runScan() {
    setLoading(true);
    try {
      const body = {
        strategies: chosen,
        weights: Object.fromEntries(chosen.map((n) => [n, Number(weights[n]) || 1])),
        k: k === "all" ? "all" : Number(k),
        fallback_n: Number(fallbackN) || 10,
      };
      setScan(await postScan(body));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <h2 className="label mb-3">Configure screen</h2>
        <div className="flex flex-col gap-2">
          {strategies.map((s) => (
            <div key={s.name} className="flex items-center gap-3">
              <label className="flex w-48 items-center gap-2 font-mono text-xs text-[var(--color-text)]">
                <input
                  type="checkbox"
                  checked={!!selected[s.name]}
                  onChange={(e) =>
                    setSelectedOverride({ ...selected, [s.name]: e.target.checked })
                  }
                />
                {s.name}
              </label>
              <input
                type="number"
                step="0.1"
                value={weights[s.name] ?? 1}
                onChange={(e) =>
                  setWeightsOverride({ ...weights, [s.name]: e.target.value })
                }
                disabled={!selected[s.name]}
                className="w-20 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-2 py-1 font-mono text-xs disabled:opacity-40"
              />
            </div>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1">
            <span className="label">K (matches required)</span>
            <select
              value={k}
              onChange={(e) => setK(e.target.value)}
              className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-2 py-1 font-mono text-xs"
            >
              <option value="all">all (AND)</option>
              {chosen.map((_, i) => (
                <option key={i + 1} value={i + 1}>
                  {i + 1}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="label">Fallback N</span>
            <input
              type="number"
              value={fallbackN}
              onChange={(e) => setFallbackN(e.target.value)}
              className="w-20 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-2 py-1 font-mono text-xs"
            />
          </label>
          <button
            type="button"
            onClick={runScan}
            disabled={loading || chosen.length === 0}
            className="rounded-[var(--radius-sm)] border border-[var(--color-accent)] bg-[var(--color-surface-soft)] px-4 py-1.5 font-mono text-xs uppercase tracking-[0.1em] text-[var(--color-text)] disabled:opacity-40"
          >
            {loading ? "Scanning…" : "Run screen"}
          </button>
        </div>
      </Card>

      {scan && (
        <Card className="p-4">
          <div className="mb-3 flex items-center gap-3">
            <h2 className="label">Results</h2>
            {scan.is_fallback && (
              <span
                className="rounded-[var(--radius-sm)] px-2 py-0.5 font-mono text-[0.625rem] uppercase tracking-[0.1em] text-[var(--color-warning)]"
                style={{
                  backgroundColor:
                    "color-mix(in srgb, var(--color-warning) 15%, transparent)",
                }}
              >
                Fallback · no true matches — showing top {scan.results.length} by aggregate
              </span>
            )}
          </div>
          {scan.results.length === 0 ? (
            <EmptyState title="No results" description="Refresh data or loosen K." />
          ) : (
            <TableShell>
              <TableHeader className={RESULT_GRID}>
                <div>#</div>
                <div>Symbol</div>
                <div className="text-right">Aggregate</div>
                <div className="text-right">Passes</div>
              </TableHeader>
              {scan.results.map((row, i) => (
                <TableRow key={row.symbol} className={RESULT_GRID}>
                  <div className="font-mono text-[var(--color-text-muted)]">{i + 1}</div>
                  <div className="font-medium text-[var(--color-text)]">{row.symbol}</div>
                  <div className="text-right font-mono tabular-nums">{row.aggregate}</div>
                  <div className="text-right font-mono tabular-nums">{row.passes}</div>
                </TableRow>
              ))}
            </TableShell>
          )}
        </Card>
      )}
    </div>
  );
}
