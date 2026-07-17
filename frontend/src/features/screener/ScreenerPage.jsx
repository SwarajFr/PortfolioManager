import { useState } from "react";
import PageShell from "../../components/layout/PageShell";
import { cn } from "../../utils/classNames";
import { useScreenerStatus } from "./hooks/useScreener";
import LastUpdated from "./components/LastUpdated";
import StrategiesPanel from "./components/StrategiesPanel";
import ScreenerPanel from "./components/ScreenerPanel";

const TABS = [
  { id: "strategies", label: "Strategies" },
  { id: "screener", label: "Screener" },
];

export default function ScreenerPage() {
  const [tab, setTab] = useState("strategies");
  const { data: status } = useScreenerStatus();

  return (
    <PageShell eyebrow="Signals" title="Stock Screener">
      <div className="flex flex-col gap-5">
        <div className="flex items-center justify-between">
          <div className="flex gap-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={cn(
                  "rounded-[var(--radius-sm)] border px-3 py-1.5 font-mono text-[0.625rem] uppercase tracking-[0.12em] transition",
                  tab === t.id
                    ? "border-[var(--color-accent)] bg-[var(--color-surface-soft)] text-[var(--color-text)]"
                    : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
          <LastUpdated status={status} />
        </div>

        {tab === "strategies" ? <StrategiesPanel /> : <ScreenerPanel />}
      </div>
    </PageShell>
  );
}
