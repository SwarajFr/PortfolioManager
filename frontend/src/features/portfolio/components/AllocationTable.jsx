import { TableHeader, TableRow, TableShell } from "../../../components/ui/DataTable";
import { formatINR, formatPercent, formatSignedINR } from "../../../utils/formatters";
import { getSignedTone } from "../../../utils/finance";
import AllocationActionBadge from "./AllocationActionBadge";

const GRID = "grid-cols-[1.25fr_1fr_0.8fr_1fr_0.8fr_0.8fr_1fr] gap-4 items-center";

export default function AllocationTable({ rows }) {
  return (
    <TableShell title="Allocation Book">
      <TableHeader className={GRID}>
        <div>Group</div>
        <div className="text-right">Value</div>
        <div className="text-right">Alloc</div>
        <div className="text-right">P&L</div>
        <div className="text-right">P&L %</div>
        <div className="text-right">Target</div>
        <div className="text-right">Action</div>
      </TableHeader>
      {rows.map((row) => {
        const toneClass = getSignedTone(row.pnl) === "positive" ? "text-[var(--profit)]" : "text-[var(--loss)]";

        return (
          <TableRow key={row.group} className={GRID}>
            <div className="font-medium text-[var(--color-text)]">{row.group}</div>
            <div className="text-right font-mono tabular-nums">{formatINR(row.value)}</div>
            <div className="text-right font-mono tabular-nums">{formatPercent(row.allocation_pct)}</div>
            <div className={`text-right font-mono tabular-nums ${toneClass}`}>{formatSignedINR(row.pnl)}</div>
            <div className={`text-right font-mono tabular-nums ${toneClass}`}>
              {formatPercent(row.pnl_pct, 1, { signed: true })}
            </div>
            <div className="text-right font-mono text-[var(--color-text-muted)]">{row.target}</div>
            <div className="text-right">
              <AllocationActionBadge action={row.action} />
            </div>
          </TableRow>
        );
      })}
    </TableShell>
  );
}
