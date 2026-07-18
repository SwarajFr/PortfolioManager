import MetricCard from "../../../components/ui/MetricCard";

function drTone(dr) {
  if (dr >= 1.6) return "positive";
  if (dr >= 1.25) return "warning";
  return "negative";
}

function enbTone(enb) {
  if (enb >= 6) return "positive";
  if (enb >= 3) return "warning";
  return "negative";
}

function gapTone(gap) {
  if (gap <= 1.5) return "positive";
  if (gap <= 2.5) return "warning";
  return "negative";
}

function volTone(vol) {
  if (vol < 0.2) return "positive";
  if (vol < 0.35) return "warning";
  return "negative";
}

const TONE_COLOR = {
  positive: "var(--color-profit)",
  warning: "var(--color-warning)",
  negative: "var(--color-loss)",
};

function StripStat({ label, value, sub, color }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="label">{label}</span>
      <span className="font-mono text-[1.05rem] font-semibold leading-none tabular-nums" style={color ? { color } : undefined}>
        {value}
        {sub ? <span className="ml-1.5 text-[0.7rem] font-normal text-[var(--color-text-faint)]">{sub}</span> : null}
      </span>
    </div>
  );
}

export default function FragilitySummaryMetrics({ scalars, maxPair, maxCorr }) {
  const {
    num_positions = 0,
    diversification_ratio = 0,
    enb = 0,
    effective_positions = 0,
    concentration_gap = 0,
    portfolio_vol = 0,
    avg_correlation = 0,
  } = scalars;

  // Share of apparent (position-count) diversification that is illusory once
  // correlation is accounted for: 1 - ENB/effective_positions = 1 - 1/gap.
  const illusoryPct =
    concentration_gap > 0 ? Math.max(0, (1 - 1 / concentration_gap) * 100) : 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <MetricCard label="Diversification Ratio" value={diversification_ratio.toFixed(2)} tone={drTone(diversification_ratio)} detail="w·σ ÷ σₚ" />
        <MetricCard label="Effective Bets" value={enb.toFixed(2)} tone={enbTone(enb)} detail={`PCA-ENB · ${num_positions} names`} />
        <MetricCard label="Effective Positions" value={effective_positions.toFixed(2)} tone="neutral" detail="weight entropy" />
        <MetricCard label="Concentration Gap" value={concentration_gap.toFixed(2)} suffix="×" tone={gapTone(concentration_gap)} detail="positions ÷ bets" />
        <MetricCard label="Portfolio Vol" value={(portfolio_vol * 100).toFixed(1)} suffix="%" tone={volTone(portfolio_vol)} detail="annualized" />
      </div>

      <div className="flex flex-wrap items-center gap-x-10 gap-y-4 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-4 py-3.5">
        <StripStat
          label="Diversification Illusory"
          value={`${illusoryPct.toFixed(0)}%`}
          color={TONE_COLOR[gapTone(concentration_gap)]}
        />
        {maxPair && maxPair.length === 2 ? (
          <StripStat label="Most-Correlated Pair" value={`${maxPair[0]} × ${maxPair[1]}`} sub={`ρ ${maxCorr.toFixed(2)}`} />
        ) : null}
        <StripStat label="Average ρ" value={avg_correlation.toFixed(2)} />
      </div>
    </div>
  );
}
