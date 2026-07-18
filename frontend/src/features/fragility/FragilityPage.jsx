import { useFragilityAnalysis } from "./hooks/useFragilityOverview";
import PageShell from "../../components/layout/PageShell";
import Card from "../../components/ui/Card";
import LoadingState from "../../components/ui/LoadingState";
import EmptyState from "../../components/ui/EmptyState";
import FragilitySummaryMetrics from "./components/FragilitySummaryMetrics";
import PrincipalBetsBars from "./components/PrincipalBetsBars";
import FragilityHeatmap from "./components/FragilityHeatmap";

export default function FragilityPage() {
  const { data, loading, error } = useFragilityAnalysis();

  if (loading) return <LoadingState title="Measuring diversification" />;
  if (error) return <EmptyState title="Error" description={error} />;
  if (!data) return null;

  const scalars = data.scalars ?? {};
  const excluded = data.tickers_excluded ?? [];

  if (!scalars.num_positions) {
    return (
      <PageShell eyebrow="Quant Lab" title="Fragility & Diversification">
        <EmptyState
          title="Not enough data"
          description={
            excluded.length
              ? `Need ≥ 2 holdings with sufficient price history. Excluded: ${excluded.join(", ")}`
              : "Connect holdings with enough price history to compute diversification metrics."
          }
        />
      </PageShell>
    );
  }

  return (
    <PageShell eyebrow="Quant Lab" title="Fragility & Diversification">
      <div className="flex flex-col gap-5">
        <FragilitySummaryMetrics
          scalars={scalars}
          maxPair={data.max_correlation_pair}
          maxCorr={scalars.max_correlation ?? 0}
        />

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
          <Card className="p-4">
            <h2 className="label mb-3">Correlation Matrix</h2>
            <FragilityHeatmap correlation={data.correlation} />
          </Card>

          <Card className="p-4">
            <h2 className="label mb-4">Principal Risk Bets</h2>
            <PrincipalBetsBars
              contributions={data.principal_risk_contributions ?? []}
              bets={data.principal_bets ?? []}
            />
          </Card>
        </div>

        {excluded.length > 0 && (
          <p className="font-mono text-[0.625rem] uppercase tracking-[0.1em] text-[var(--color-text-faint)]">
            Excluded · {excluded.join(", ")}
          </p>
        )}
      </div>
    </PageShell>
  );
}
