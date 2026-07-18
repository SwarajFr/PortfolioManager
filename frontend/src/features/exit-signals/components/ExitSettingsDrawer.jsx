import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Drawer from "../../../components/ui/Drawer";
import { getExitSettings, resetExitSettings, saveExitSettings } from "../../../services/exitSignalsService";

const KPI_STRUCTURE = {
  loss_severity: [
    { label: "Return < 0% to -5%", index: 0 },
    { label: "Return < -5% to -10%", index: 1 },
    { label: "Return < -10% to -20%", index: 2 },
    { label: "Return < -20%", index: 3 },
  ],
  risk_vs_median: [
    { label: "Ratio 1.0 to 1.2", index: 0 },
    { label: "Ratio 1.2 to 1.5", index: 1 },
    { label: "Ratio > 1.5", index: 2 },
  ],
  risk_adj_inefficiency: [
    { label: "RAR 0 to median", index: 0 },
    { label: "RAR -1 to 0", index: 1 },
    { label: "RAR < -1", index: 2 },
  ],
  trend_weakness: [
    { label: "LTP < 50 DMA", index: 0 },
    { label: "LTP < 50 DMA < 200 DMA", index: 1 },
  ],
  concentration: [
    { label: "Weight 5% to 8%", index: 0 },
    { label: "Weight 8% to 12%", index: 1 },
    { label: "Weight > 12%", index: 2 },
  ],
};

const inputClass =
  "rounded-[var(--radius-sm)] border border-[var(--border-1)] bg-[var(--surface)] px-3 py-2 font-mono text-[var(--text-xs)] text-[var(--text-1)] outline-none transition focus:border-[var(--accent)]";

function titleize(value) {
  return value.replaceAll("_", " ");
}

export default function ExitSettingsDrawer({ onClose, onSaved }) {
  const [config, setConfig] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;

    getExitSettings()
      .then((payload) => {
        if (!cancelled) setConfig(payload.config);
      })
      .catch(() => toast.error("Failed to load exit settings"));

    return () => {
      cancelled = true;
    };
  }, []);

  const updateThreshold = (key, value) => {
    setConfig((current) => ({
      ...current,
      action_thresholds: {
        ...current.action_thresholds,
        [key]: Number(value),
      },
    }));
  };

  const updateFunctionScore = (key, index, value) => {
    setConfig((current) => {
      const scores = [...current.function_scores[key]];
      scores[index] = Number(value);
      return {
        ...current,
        function_scores: {
          ...current.function_scores,
          [key]: scores,
        },
      };
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveExitSettings(config);
      toast.success("Exit settings saved");
      onSaved?.();
      onClose();
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    try {
      const payload = await resetExitSettings();
      setConfig(payload.config);
      toast.success("Reset to defaults");
      onSaved?.();
    } catch {
      toast.error("Reset failed");
    }
  };

  if (!config) {
    return (
      <Drawer onClose={onClose} title="Exit Settings">
        <Card className="p-5 text-sm text-[var(--text-2)]">Loading settings...</Card>
      </Drawer>
    );
  }

  return (
    <Drawer
      onClose={onClose}
      title="Exit Settings"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button onClick={handleReset} variant="ghost">
            Reset Defaults
          </Button>
          <Button disabled={saving} onClick={handleSave} variant="primary">
            {saving ? "Saving..." : "Save Settings"}
          </Button>
        </div>
      }
    >
      <div className="space-y-5">
        <Card className="space-y-4 p-4">
          <h3 className="label">Action score thresholds</h3>
          {["EXIT", "TRIM", "WATCH"].map((action) => (
            <label key={action} className="flex items-center justify-between gap-4 font-mono text-[10px] text-[var(--text-1)]">
              {action} Threshold
              <input
                className={`${inputClass} w-24 text-center font-mono`}
                onChange={(event) => updateThreshold(action, event.target.value)}
                type="number"
                value={config.action_thresholds[action]}
              />
            </label>
          ))}
        </Card>

        <Card className="space-y-4 p-4">
          <h3 className="label">Function KPI scores</h3>

          {Object.entries(KPI_STRUCTURE).map(([kpi, tiers]) => (
              <div key={kpi} className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-1)] p-3">
              <h4 className="font-mono text-[var(--text-xs)] font-semibold tracking-[0.04em] text-[var(--text-3)]">
                {titleize(kpi)}
              </h4>
              <div className="mt-3 space-y-2">
                {tiers.map((tier) => (
                  <label key={tier.index} className="flex items-center justify-between gap-4 font-mono text-[10px] text-[var(--text-2)]">
                    {tier.label}
                    <input
                      className={`${inputClass} w-20 py-1.5 text-center`}
                      onChange={(event) => updateFunctionScore(kpi, tier.index, event.target.value)}
                      type="number"
                      value={config.function_scores[kpi][tier.index]}
                    />
                  </label>
                ))}
              </div>
            </div>
          ))}
        </Card>
      </div>
    </Drawer>
  );
}
