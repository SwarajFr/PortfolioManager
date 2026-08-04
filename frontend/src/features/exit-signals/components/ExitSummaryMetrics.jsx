import MetricCard from "../../../components/ui/MetricCard";

function getAverageScoreTone(score) {
  if (score >= 70) return "danger";
  if (score >= 50) return "warning";
  if (score >= 30) return "warning";
  return "positive";
}

export default function ExitSummaryMetrics({ summary }) {
  const counts = summary.action_counts || {};
  const activeActions = ["EXIT", "TRIM", "WATCH", "HOLD"]
    .filter((action) => Number(counts[action] || 0) > 0)
    .map((action) => `${counts[action]} ${action.toLowerCase()}`)
    .join(" | ");

  const metrics = [
    {
      label: "Holdings Analysed",
      value: summary.total_holdings,
      tone: "neutral",
    },
    {
      label: "Avg Exit Score",
      value: summary.avg_exit_score,
      tone: getAverageScoreTone(summary.avg_exit_score),
    },
    {
      label: "Action Breakdown",
      value: activeActions || "None",
      tone: "info",
    },
    {
      label: "Median Volatility",
      value: `${(Number(summary.median_volatility || 0) * 100).toFixed(1)}%`,
      tone: "neutral",
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
