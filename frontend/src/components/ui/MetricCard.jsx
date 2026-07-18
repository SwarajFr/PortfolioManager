import Card from "./Card";
import { TONE_STYLES } from "../../constants/theme";
import { cn } from "../../utils/classNames";

const TONE_EDGE = {
  positive: "var(--color-profit)",
  negative: "var(--color-loss)",
  danger: "var(--color-loss)",
  warning: "var(--color-warning)",
  info: "var(--color-info)",
  neutral: "var(--color-border-strong)",
};

export default function MetricCard({
  label,
  value,
  detail,
  suffix,
  tone = "neutral",
  className = "",
  compact = false,
}) {
  return (
    <Card
      className={cn("relative overflow-hidden", compact ? "p-4" : "p-4 sm:p-5", className)}
    >
      <span
        className="absolute inset-y-0 left-0 w-[2px]"
        style={{ background: TONE_EDGE[tone] || TONE_EDGE.neutral }}
      />
      <div className="label">{label}</div>
      <div className={cn("mt-2.5 font-mono text-[1.55rem] font-semibold leading-none tabular-nums tracking-[-0.02em]", TONE_STYLES[tone])}>
        {value}
        {suffix ? <span className="ml-0.5 text-[0.9rem] font-medium text-[var(--color-text-faint)]">{suffix}</span> : null}
      </div>
      {detail ? (
        <p className="mt-2.5 font-mono text-[0.625rem] leading-4 text-[var(--color-text-faint)]">{detail}</p>
      ) : null}
    </Card>
  );
}
