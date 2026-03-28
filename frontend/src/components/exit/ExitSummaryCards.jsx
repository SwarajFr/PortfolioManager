import Card from "../ui/Card";

export default function ExitSummaryCards({ summary }) {
  const { total_holdings, avg_exit_score, action_counts } = summary;

  // colour for average score
  const scoreColor =
    avg_exit_score >= 70 ? "text-red-400"
    : avg_exit_score >= 50 ? "text-orange-400"
    : avg_exit_score >= 30 ? "text-yellow-400"
    : "text-green-400";

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
      <Card className="px-5 py-4">
        <p className="text-[11px] text-neutral-500 uppercase font-semibold tracking-wider">Holdings Analysed</p>
        <div className="mt-2 text-3xl font-bold text-neutral-100">{total_holdings}</div>
      </Card>

      <Card className="px-5 py-4">
        <p className="text-[11px] text-neutral-500 uppercase font-semibold tracking-wider">Avg Exit Score</p>
        <div className={`mt-2 text-3xl font-bold ${scoreColor}`}>
          {avg_exit_score}
        </div>
      </Card>

      <Card className="px-5 py-4">
        <p className="text-[11px] text-neutral-500 uppercase font-semibold tracking-wider">Action Breakdown</p>
        <div className="flex gap-3 mt-3 text-sm font-semibold">
          {action_counts.EXIT > 0 && (
            <span className="text-red-400 bg-red-400/10 px-2 py-0.5 rounded-md">{action_counts.EXIT} Exit</span>
          )}
          {action_counts.TRIM > 0 && (
            <span className="text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded-md">{action_counts.TRIM} Trim</span>
          )}
          {action_counts.WATCH > 0 && (
            <span className="text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded-md">{action_counts.WATCH} Watch</span>
          )}
          {action_counts.HOLD > 0 && (
            <span className="text-green-400 bg-green-400/10 px-2 py-0.5 rounded-md">{action_counts.HOLD} Hold</span>
          )}
          {Object.values(action_counts).every(v => v === 0) && (
            <span className="text-neutral-500">None</span>
          )}
        </div>
      </Card>

      <Card className="px-5 py-4">
        <p className="text-[11px] text-neutral-500 uppercase font-semibold tracking-wider">Median Volatility</p>
        <div className="mt-2 text-3xl font-bold text-neutral-100">
          {(summary.median_volatility * 100).toFixed(1)}<span className="text-xl text-neutral-500">%</span>
        </div>
      </Card>
    </div>
  );
}
