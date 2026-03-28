import { useEffect, useState } from "react";
import api from "../../api/client";
import toast from "react-hot-toast";

const KPI_STRUCTURE = {
  loss_severity: [
    { label: "Return < 0% to -5%", idx: 0 },
    { label: "Return < -5% to -10%", idx: 1 },
    { label: "Return < -10% to -20%", idx: 2 },
    { label: "Return < -20%", idx: 3 },
  ],
  risk_vs_median: [
    { label: "Ratio 1.0 to 1.2", idx: 0 },
    { label: "Ratio 1.2 to 1.5", idx: 1 },
    { label: "Ratio > 1.5", idx: 2 },
  ],
  risk_adj_inefficiency: [
    { label: "RAR 0 to Median", idx: 0 },
    { label: "RAR -1 to 0 (Moderate)", idx: 1 },
    { label: "RAR < -1 (Severe)", idx: 2 },
  ],
  trend_weakness: [
    { label: "LTP < 50 DMA", idx: 0 },
    { label: "LTP < 50 DMA < 200 DMA", idx: 1 },
  ],
  concentration: [
    { label: "Weight 5% to 8%", idx: 0 },
    { label: "Weight 8% to 12%", idx: 1 },
    { label: "Weight > 12%", idx: 2 },
  ]
};

export default function ExitSettingsPanel({ onClose, onSaved }) {
  const [config, setConfig] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/exit/settings")
      .then(res => setConfig(res.data.config))
      .catch(() => toast.error("Failed to load settings"));
  }, []);

  if (!config) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put("/exit/settings", config);
      toast.success("Settings saved");
      onSaved?.();
      onClose();
    } catch {
      toast.error("Save failed");
    }
    setSaving(false);
  };

  const handleReset = async () => {
    try {
      const res = await api.post("/exit/settings/reset");
      setConfig(res.data.config);
      toast.success("Reset to defaults");
      onSaved?.();
    } catch {
      toast.error("Reset failed");
    }
  };

  const updateThreshold = (key, val) => {
    setConfig({
      ...config,
      action_thresholds: {
        ...config.action_thresholds,
        [key]: Number(val),
      }
    });
  };

  const updateFunctionScoreIdx = (key, idx, val) => {
    const arr = [...config.function_scores[key]];
    arr[idx] = Number(val);
    setConfig({
      ...config,
      function_scores: {
        ...config.function_scores,
        [key]: arr,
      }
    });
  };

  const input =
    "bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-sm text-neutral-200 " +
    "focus:outline-none focus:border-neutral-500 transition w-full";

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* panel */}
      <div className="relative w-full max-w-xl bg-[#111113] border-l border-neutral-800 overflow-y-auto flex flex-col h-full">
        {/* header */}
        <div className="sticky top-0 z-10 bg-[#111113]/90 backdrop-blur border-b border-neutral-800 px-6 py-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-neutral-200 tracking-wide uppercase">
            Exit Settings
          </h2>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300 transition cursor-pointer">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-6 flex-1">
          {/* Action Thresholds */}
          <section className="bg-neutral-900/50 border border-neutral-800 rounded-xl p-5 space-y-3">
            <h3 className="text-xs text-neutral-500 uppercase tracking-wide">Action Score Thresholds</h3>
            
            <div className="space-y-3">
              {["EXIT", "TRIM", "WATCH"].map(action => (
                <div key={action} className="flex items-center justify-between">
                  <label className="text-sm text-neutral-300">{action} Threshold</label>
                  <input
                    type="number"
                    value={config.action_thresholds[action]}
                    onChange={e => updateThreshold(action, e.target.value)}
                    className={`${input} !w-24 text-center`}
                  />
                </div>
              ))}
            </div>
          </section>

          {/* Function Scores */}
          <section className="bg-neutral-900/50 border border-neutral-800 rounded-xl p-5 space-y-3">
            <h3 className="text-xs text-neutral-500 uppercase tracking-wide">Function KPI Scores</h3>
            <p className="text-xs text-neutral-500 mb-2">Configure the penalty scores given for each conditional logic bracket.</p>
            
            <div className="space-y-4">
              {Object.entries(KPI_STRUCTURE).map(([kpi, tiers]) => (
                <div key={kpi} className="border border-neutral-800 rounded-lg p-3 space-y-2 bg-neutral-900/40">
                  <h4 className="text-xs font-semibold text-neutral-300 uppercase tracking-wide mb-3">
                    {kpi.split('_').join(' ')}
                  </h4>
                  <div className="space-y-2">
                    {tiers.map((tier) => (
                      <div key={tier.idx} className="flex items-center justify-between">
                        <span className="text-xs text-neutral-400">{tier.label}</span>
                        <input
                          type="number"
                          value={config.function_scores[kpi][tier.idx]}
                          onChange={e => updateFunctionScoreIdx(kpi, tier.idx, e.target.value)}
                          className={`${input} !w-20 !py-1 !text-center`}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* footer */}
        <div className="sticky bottom-0 bg-[#111113]/90 backdrop-blur border-t border-neutral-800 px-6 py-4 flex items-center justify-between">
          <button
            onClick={handleReset}
            className="text-xs text-neutral-400 hover:text-neutral-200 transition cursor-pointer underline underline-offset-2"
          >
            Reset to Defaults
          </button>

          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-white text-black text-sm font-medium px-5 py-2 rounded-xl hover:bg-neutral-200 transition disabled:opacity-40 cursor-pointer"
          >
            {saving ? "Saving…" : "Save Settings"}
          </button>
        </div>
      </div>
    </div>
  );
}

