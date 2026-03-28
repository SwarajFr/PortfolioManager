/**
 * ExitScoreBar — horizontal bar visualising 0-100 score with gradient.
 */
export default function ExitScoreBar({ score }) {
  const pct = Math.min(100, Math.max(0, score));

  // green → yellow → orange → red
  const getColor = (s) => {
    if (s < 30) return "#22c55e";   // green-500
    if (s < 50) return "#eab308";   // yellow-500
    if (s < 70) return "#f97316";   // orange-500
    return "#ef4444";               // red-500
  };

  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-2 rounded-full bg-neutral-800 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${pct}%`, backgroundColor: getColor(pct) }}
        />
      </div>
      <span className="text-xs font-semibold tabular-nums" style={{ color: getColor(pct) }}>
        {score}
      </span>
    </div>
  );
}
