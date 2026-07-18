import MetricCard from "../../../components/ui/MetricCard";
import { formatINR, formatPercent, formatSignedINR } from "../../../utils/formatters";
import { getSignedTone } from "../../../utils/finance";

export default function PortfolioMetrics({ health }) {
  const metrics = [
    {
      label: "Total Value",
      value: formatINR(health.total_value),
      tone: "neutral",
    },
    {
      label: "Net P&L",
      value: formatSignedINR(health.total_pnl),
      tone: getSignedTone(health.total_pnl),
    },
    {
      label: "Return",
      value: formatPercent(health.return_pct, 1, { signed: true }),
      tone: getSignedTone(health.return_pct),
    },
    {
      label: "Capital At Risk",
      value: formatINR(health.capital_at_risk),
      tone: "negative",
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <MetricCard key={metric.label} compact {...metric} />
      ))}
    </div>
  );
}
