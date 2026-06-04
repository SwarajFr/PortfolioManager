import { useState } from "react";
import { useFragilityAnalysis } from "./hooks/useFragilityOverview";
import PageShell from "../../components/layout/PageShell";
import Card from "../../components/ui/Card";
import LoadingState from "../../components/ui/LoadingState";
import EmptyState from "../../components/ui/EmptyState";
import FragilitySummaryMetrics from "./components/FragilitySummaryMetrics";
import FragilityHoldingsTable from "./components/FragilityHoldingsTable";
import FragilityHeatmap from "./components/FragilityHeatmap";
import FragilityWhatIfPanel from "./components/FragilityWhatIfPanel";

function medianMrc(holdings) {
  if (!holdings.length) return 0;
  const sorted = [...holdings].map((h) => h.mrc).sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export default function FragilityPage() {
  const { data, loading, error } = useFragilityAnalysis();
  const [selectedHolding, setSelectedHolding] = useState(null);

  if (loading) return <LoadingState title="Analysing portfolio fragility…" />;
  if (error) return <EmptyState title="Error" description={error} />;
  if (!data) return null;

  const med = medianMrc(data.holdings ?? []);

  return (
    <PageShell
      title="Fragility & Diversification"
      description="Concentration risk, regime detection, and trim simulation"
    >
      <div className="flex flex-col gap-[var(--space-5)]">
        {/* Header: 4 metric cards + sparkline + trim summary */}
        <Card className="p-[var(--space-4)]">
          <FragilitySummaryMetrics data={data} />
        </Card>

        {/* Holdings table + Correlation heatmap side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-[var(--space-4)]">
          <Card className="p-[var(--space-4)]">
            <h2 className="text-[var(--text-1)] text-[var(--text-sm)] font-medium mb-[var(--space-3)]">
              Holdings
            </h2>
            <FragilityHoldingsTable
              holdings={data.holdings ?? []}
              medianMrc={med}
              onSimulate={(h) => setSelectedHolding(h)}
            />
          </Card>
          <Card className="p-[var(--space-4)]">
            <h2 className="text-[var(--text-1)] text-[var(--text-sm)] font-medium mb-[var(--space-3)]">
              Correlation Matrix
            </h2>
            <FragilityHeatmap
              corr_matrix={data.corr_matrix ?? []}
              tickers_corr={data.tickers_corr ?? []}
            />
          </Card>
        </div>

        {/* What-if simulator */}
        <Card className="p-[var(--space-4)]">
          <FragilityWhatIfPanel
            selected={selectedHolding}
            baseEnb={data.enb ?? 0}
            baseStressLoss={data.stress_loss_pct ?? 0}
            onClose={() => setSelectedHolding(null)}
          />
        </Card>
      </div>
    </PageShell>
  );
}
