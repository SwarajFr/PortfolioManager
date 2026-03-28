import { useState, useMemo } from "react";
import { formatINR } from "../../utils/format";
import ExitScoreBar from "./ExitScoreBar";
import ExitActionBadge from "./ExitActionBadge";

const KPI_COLS = [
  { key: "loss_severity",         label: "Loss",  max: 25 },
  { key: "risk_vs_median",        label: "Risk",  max: 20 },
  { key: "risk_adj_inefficiency",  label: "RAR",   max: 20 },
  { key: "trend_weakness",        label: "Trend", max: 20 },
  { key: "concentration",         label: "Conc",  max: 15 },
];

function KpiCell({ value, max }) {
  const ratio = value / max;
  const color =
    ratio >= 0.7 ? "text-red-400"
    : ratio >= 0.4 ? "text-orange-400"
    : ratio > 0 ? "text-yellow-400"
    : "text-neutral-500";

  return <span className={`${color} tabular-nums`}>{value}</span>;
}

export default function ExitTable({ signals }) {
  const [sortConfig, setSortConfig] = useState({ key: "exit_score", direction: "desc" });

  const sortedSignals = useMemo(() => {
    const sortableItems = [...signals];
    if (sortConfig.key) {
      sortableItems.sort((a, b) => {
        let aValue = a[sortConfig.key];
        let bValue = b[sortConfig.key];

        // Handle nested score properties
        if (KPI_COLS.some(c => c.key === sortConfig.key)) {
          aValue = a.scores[sortConfig.key];
          bValue = b.scores[sortConfig.key];
        }

        if (aValue < bValue) {
          return sortConfig.direction === "asc" ? -1 : 1;
        }
        if (aValue > bValue) {
          return sortConfig.direction === "asc" ? 1 : -1;
        }
        return 0;
      });
    }
    return sortableItems;
  }, [signals, sortConfig]);

  const requestSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    } else if (sortConfig.key !== key) {
      // Default to sorting descendant for numerical values initially
      direction = key === "symbol" || key === "action" ? "asc" : "desc";
    }
    setSortConfig({ key, direction });
  };

  const getSortIndicator = (key) => {
    if (sortConfig.key !== key) return "";
    return sortConfig.direction === "asc" ? " ↑" : " ↓";
  };

  const HeaderItem = ({ label, sortKey, align = "left" }) => (
    <div 
      className={`cursor-pointer hover:text-neutral-300 select-none ${align === "right" ? "text-right" : align === "center" ? "text-center" : ""}`}
      onClick={() => requestSort(sortKey)}
    >
      {label}{getSortIndicator(sortKey)}
    </div>
  );

  return (
    <div className="bg-neutral-900/50 border border-neutral-800 rounded-xl p-5 overflow-x-auto">
      <h2 className="text-xs text-neutral-500 uppercase mb-4">
        Exit / Trim Recommendations
      </h2>

      {/* header */}
      <div className="grid grid-cols-[40px_1fr_80px_80px_70px_70px_50px_50px_50px_50px_50px_140px_80px] text-[11px] text-neutral-500 pb-2 gap-x-2 min-w-[1050px]">
        <div>#</div>
        <HeaderItem label="Stock" sortKey="symbol" />
        <HeaderItem label="Invested" sortKey="invested" align="right" />
        <HeaderItem label="Cur Val" sortKey="value" align="right" />
        <HeaderItem label="LTP" sortKey="ltp" align="right" />
        <HeaderItem label="Return" sortKey="return_pct" align="right" />
        {KPI_COLS.map((c) => (
          <HeaderItem key={c.key} label={c.label} sortKey={c.key} align="center" />
        ))}
        <HeaderItem label="Score" sortKey="exit_score" align="left" />
        <HeaderItem label="Action" sortKey="action" align="center" />
      </div>

      {/* rows */}
      {sortedSignals.map((s, i) => (
        <div
          key={s.symbol}
          className="grid grid-cols-[40px_1fr_80px_80px_70px_70px_50px_50px_50px_50px_50px_140px_80px] text-sm py-3 border-t border-neutral-800 hover:bg-neutral-800/30 transition gap-x-2 items-center min-w-[1050px]"
        >
          <div className="text-neutral-500 text-xs">{i + 1}</div>
          <div className="truncate font-medium">{s.symbol}</div>
          <div className="text-right tabular-nums text-neutral-400">{formatINR(s.invested)}</div>
          <div className="text-right tabular-nums">{formatINR(s.value)}</div>
          <div className="text-right tabular-nums">{formatINR(s.ltp)}</div>
          <div className={`text-right tabular-nums ${s.return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
            {s.return_pct > 0 ? "+" : ""}{s.return_pct}%
          </div>
          {KPI_COLS.map((c) => (
            <div key={c.key} className="text-center text-xs">
              <KpiCell value={s.scores[c.key]} max={c.max} />
            </div>
          ))}
          <div>
            <ExitScoreBar score={s.exit_score} />
          </div>
          <div className="text-center">
            <ExitActionBadge action={s.action} />
          </div>
        </div>
      ))}
    </div>
  );
}
