import { clamp } from "../../utils/finance";

export default function ProgressBar({ value, color = "var(--color-accent)", className = "" }) {
  const pct = clamp(value, 0, 100);

  return (
    <div className={`h-2 overflow-hidden rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] ${className}`.trim()}>
      <div
        className="h-full rounded-[var(--radius-sm)] transition-all duration-[var(--duration-med)]"
        style={{
          width: `${pct}%`,
          background: color,
        }}
      />
    </div>
  );
}
