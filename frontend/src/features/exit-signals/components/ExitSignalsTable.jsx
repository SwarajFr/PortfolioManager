import { useMemo, useState } from "react";
import { SortHeader, TableHeader, TableRow, TableShell } from "../../../components/ui/DataTable";
import { formatINR, formatPercent } from "../../../utils/formatters";
import ExitActionBadge from "./ExitActionBadge";
import ExitScoreBar from "./ExitScoreBar";

const KPI_COLUMNS = [
  { key: "loss_severity", label: "Loss", max: 25 },
  { key: "risk_vs_median", label: "Risk", max: 20 },
  { key: "risk_adj_inefficiency", label: "RAR", max: 20 },
  { key: "trend_weakness", label: "Trend", max: 20 },
  { key: "concentration", label: "Conc", max: 15 },
];

const GRID = "grid-cols-[44px_1fr_112px_112px_96px_86px_56px_56px_56px_56px_56px_164px_92px] gap-3 items-center";

function getKpiClass(value, max) {
  const ratio = Number(value || 0) / max;
  if (ratio >= 0.7) return "text-[var(--loss)]";
  if (ratio >= 0.4) return "text-[var(--warning)]";
  if (ratio > 0) return "text-[var(--color-text)]";
  return "text-[var(--color-text-faint)]";
}

export default function ExitSignalsTable({ signals }) {
  const [sortConfig, setSortConfig] = useState({ key: "exit_score", direction: "desc" });

  const sortedSignals = useMemo(() => {
    return [...signals].sort((left, right) => {
      const getValue = (row) => {
        if (KPI_COLUMNS.some((column) => column.key === sortConfig.key)) {
          return row.scores?.[sortConfig.key] || 0;
        }
        return row[sortConfig.key];
      };

      const leftValue = getValue(left);
      const rightValue = getValue(right);
      if (leftValue < rightValue) return sortConfig.direction === "asc" ? -1 : 1;
      if (leftValue > rightValue) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [signals, sortConfig]);

  const requestSort = (key) => {
    setSortConfig((current) => {
      if (current.key === key) {
        return { key, direction: current.direction === "asc" ? "desc" : "asc" };
      }
      return { key, direction: key === "symbol" || key === "action" ? "asc" : "desc" };
    });
  };

  const header = (label, key, align = "left") => (
    <SortHeader
      active={sortConfig.key === key}
      align={align}
      direction={sortConfig.direction}
      onClick={() => requestSort(key)}
    >
      {label}
    </SortHeader>
  );

  return (
    <TableShell title="Exit / Trim Recommendations">
      <TableHeader className={GRID}>
        <div>#</div>
        {header("Stock", "symbol")}
        {header("Invested", "invested", "right")}
        {header("Cur Val", "value", "right")}
        {header("LTP", "ltp", "right")}
        {header("Return", "return_pct", "right")}
        {KPI_COLUMNS.map((column) => (
          <div key={column.key} className="text-center">
            {header(column.label, column.key, "center")}
          </div>
        ))}
        {header("Score", "exit_score")}
        {header("Action", "action", "center")}
      </TableHeader>

      {sortedSignals.map((signal, index) => (
        <TableRow key={signal.symbol} className={GRID}>
          <div className="font-mono text-xs text-[var(--color-text-faint)]">{index + 1}</div>
          <div className="truncate font-mono font-semibold text-[var(--color-text)]">{signal.symbol}</div>
          <div className="text-right font-mono tabular-nums text-[var(--color-text-muted)]">{formatINR(signal.invested)}</div>
          <div className="text-right font-mono tabular-nums">{formatINR(signal.value)}</div>
          <div className="text-right font-mono tabular-nums">{formatINR(signal.ltp)}</div>
          <div className={`text-right font-mono tabular-nums ${signal.return_pct >= 0 ? "text-[var(--profit)]" : "text-[var(--loss)]"}`}>
            {formatPercent(signal.return_pct, 2, { signed: true })}
          </div>
          {KPI_COLUMNS.map((column) => (
            <div key={column.key} className={`text-center font-mono text-xs tabular-nums ${getKpiClass(signal.scores?.[column.key], column.max)}`}>
              {signal.scores?.[column.key] || 0}
            </div>
          ))}
          <ExitScoreBar score={signal.exit_score} />
          <div className="text-center">
            <ExitActionBadge action={signal.action} />
          </div>
        </TableRow>
      ))}
    </TableShell>
  );
}
