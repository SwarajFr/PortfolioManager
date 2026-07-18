import { useEffect, useState } from "react";
import PageShell from "../../components/layout/PageShell";
import EmptyState from "../../components/ui/EmptyState";
import LoadingState from "../../components/ui/LoadingState";
import ExitSettingsDrawer from "./components/ExitSettingsDrawer";
import ExitSignalsTable from "./components/ExitSignalsTable";
import ExitSummaryMetrics from "./components/ExitSummaryMetrics";
import { useExitSignals } from "./hooks/useExitSignals";

export default function ExitSignalsPage() {
  const [showSettings, setShowSettings] = useState(false);
  const { data, loading, refresh } = useExitSignals();

  useEffect(() => {
    const handleRefresh = () => refresh();
    const handleConfigure = () => setShowSettings(true);

    window.addEventListener("dashboard:refresh", handleRefresh);
    window.addEventListener("dashboard:configure", handleConfigure);

    return () => {
      window.removeEventListener("dashboard:refresh", handleRefresh);
      window.removeEventListener("dashboard:configure", handleConfigure);
    };
  }, [refresh]);

  if (loading) {
    return <LoadingState title="Scoring exit pressure" />;
  }

  if (!data) {
    return <EmptyState actionLabel="Retry" onAction={refresh} title="Exit signals unavailable" />;
  }

  return (
    <PageShell eyebrow="Risk Engine" title="Exit Signals">
      <div className="space-y-5">
        <ExitSummaryMetrics summary={data.summary} />
        <ExitSignalsTable signals={data.signals || []} />
      </div>

      {showSettings ? (
        <ExitSettingsDrawer onClose={() => setShowSettings(false)} onSaved={refresh} />
      ) : null}
    </PageShell>
  );
}
