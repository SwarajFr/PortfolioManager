function barColor(pct) {
  if (pct >= 50) return "var(--color-loss)";
  if (pct >= 25) return "var(--color-warning)";
  return "var(--color-accent)";
}

/** The holdings that define one principal bet — the eigenvector's dominant
    loadings. Negative loadings are the opposing leg of a spread. */
function BetMembers({ members }) {
  if (!members?.length) return null;
  return (
    <div className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 font-mono text-[0.625rem]">
      {members.map((m, i) => {
        const short = m.loading < 0;
        return (
          <span key={m.symbol} className="inline-flex items-baseline gap-1">
            {i > 0 ? <span className="text-[var(--color-text-faint)]">·</span> : null}
            <span className={short ? "text-[var(--color-text-muted)]" : "text-[var(--color-text)]"}>
              {short ? "−" : ""}
              {m.symbol}
            </span>
            <span className="tabular-nums text-[var(--color-text-faint)]">{Math.round(m.weight * 100)}</span>
          </span>
        );
      })}
    </div>
  );
}

export default function PrincipalBetsBars({ contributions = [], bets = [] }) {
  if (!contributions.length) {
    return (
      <p className="font-mono text-[0.625rem] uppercase tracking-[0.1em] text-[var(--color-text-faint)] py-4">
        No data
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-[var(--space-3)]">
      {contributions.map((p, i) => {
        const pct = p * 100;
        return (
          <div key={i} className="flex flex-col gap-[var(--space-1)]">
            <div className="flex items-baseline justify-between font-mono text-[var(--text-xs)]">
              <span className="text-[var(--color-text-muted)]">Bet {String(i + 1).padStart(2, "0")}</span>
              <span className="tabular-nums text-[var(--color-text)]">{pct.toFixed(1)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)]">
              <div
                className="h-full rounded-[var(--radius-sm)] transition-all duration-[var(--duration-med)]"
                style={{ width: `${Math.min(100, pct)}%`, background: barColor(pct) }}
              />
            </div>
            <BetMembers members={bets[i]} />
          </div>
        );
      })}
    </div>
  );
}
