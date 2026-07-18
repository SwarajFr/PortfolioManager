import { clamp } from "../../../utils/finance";

function getScoreColor(score) {
  if (score >= 70) return "var(--color-loss)";
  if (score >= 50) return "var(--color-warning)";
  if (score >= 30) return "var(--color-warning)";
  return "var(--color-profit)";
}

export default function ExitScoreBar({ score }) {
  const pct = clamp(score, 0, 100);
  const color = getScoreColor(pct);
  const filled = Math.round(pct / 10);

  return (
    <div className="flex min-w-36 items-center gap-2">
      <div className="grid h-2 flex-1 grid-cols-10 gap-px">
        {Array.from({ length: 10 }).map((_, index) => (
          <div
            key={index}
            style={{
              backgroundColor: index < filled ? color : "rgba(255,255,255,0.06)",
            }}
          />
        ))}
      </div>
      <span className="w-9 text-right font-mono text-[var(--text-xs)] font-semibold tabular-nums text-[var(--color-text)]">
        {score}
      </span>
    </div>
  );
}
