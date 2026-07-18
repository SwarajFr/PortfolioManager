import { useCallback, useState } from "react";
import Card from "../../../components/ui/Card";
import { TableHeader, TableRow, TableShell } from "../../../components/ui/DataTable";
import EmptyState from "../../../components/ui/EmptyState";
import { useAsyncData } from "../../../hooks/useAsyncData";
import { useStrategies } from "../hooks/useScreener";
import { getIndividual } from "../../../services/screenerService";

const GRID = "grid-cols-[0.5fr_2fr_1fr] gap-4 items-center";

export default function StrategiesPanel() {
  const { data: meta, loading: metaLoading } = useStrategies();
  const strategies = meta?.strategies ?? [];
  const [selected, setSelected] = useState("");
  // Derive the active strategy during render (defaults to the first) instead of
  // syncing it via an effect — keeps this component free of set-state-in-effect.
  const active = selected || strategies[0]?.name || "";

  const { data, loading } = useAsyncData(
    useCallback(() => getIndividual(active), [active]),
    { errorMessage: "Failed to load strategy results", enabled: Boolean(active) },
  );
  const results = data?.results ?? [];

  return (
    <Card className="p-4">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="label">Strategy</span>
        <select
          value={active}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-2 py-1 font-mono text-xs text-[var(--color-text)]"
        >
          {strategies.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {metaLoading || loading ? (
        <p className="label">Loading…</p>
      ) : results.length === 0 ? (
        <EmptyState title="No passing stocks" description="No symbols pass this strategy yet." />
      ) : (
        <TableShell title={`Passing · ${active}`}>
          <TableHeader className={GRID}>
            <div>#</div>
            <div>Symbol</div>
            <div className="text-right">Raw score</div>
          </TableHeader>
          {results.map((row, i) => (
            <TableRow key={row.symbol} className={GRID}>
              <div className="font-mono text-[var(--color-text-muted)]">{i + 1}</div>
              <div className="font-medium text-[var(--color-text)]">{row.symbol}</div>
              <div className="text-right font-mono tabular-nums">{row.score}</div>
            </TableRow>
          ))}
        </TableShell>
      )}
    </Card>
  );
}
