import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Drawer from "../../../components/ui/Drawer";
import {
  getAdvisorProfile,
  resetAdvisorProfile,
  saveAdvisorProfile,
} from "../../../services/advisorService";

const RISK_LEVELS = [
  { value: "conservative", label: "Conservative", hint: "favours reward:risk over raw conviction" },
  { value: "balanced", label: "Balanced", hint: "weighs both" },
  { value: "aggressive", label: "Aggressive", hint: "chases conviction; allows high-volatility names" },
];

const inputClass =
  "rounded-[var(--radius-sm)] border border-[var(--border-1)] bg-[var(--surface)] px-3 py-2 font-mono text-[var(--text-xs)] text-[var(--text-1)] outline-none transition focus:border-[var(--accent)]";

function parseSymbols(value) {
  return value
    .split(",")
    .map((symbol) => symbol.trim().toUpperCase())
    .filter(Boolean);
}

export default function AdvisorProfileDrawer({ onClose }) {
  const [profile, setProfile] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;

    getAdvisorProfile()
      .then((payload) => {
        if (!cancelled) setProfile(payload.config.profile);
      })
      .catch(() => toast.error("Failed to load your advisor profile"));

    return () => {
      cancelled = true;
    };
  }, []);

  const update = (key, value) => setProfile((current) => ({ ...current, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveAdvisorProfile(profile);
      toast.success("Profile saved");
      onClose();
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    try {
      const payload = await resetAdvisorProfile();
      setProfile(payload.config.profile);
      toast.success("Reset to defaults");
    } catch {
      toast.error("Reset failed");
    }
  };

  if (!profile) {
    return (
      <Drawer onClose={onClose} title="Advisor Profile">
        <Card className="p-5 text-sm text-[var(--text-2)]">Loading profile...</Card>
      </Drawer>
    );
  }

  return (
    <Drawer
      onClose={onClose}
      title="Advisor Profile"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button onClick={handleReset} variant="ghost">
            Reset Defaults
          </Button>
          <Button disabled={saving} onClick={handleSave} variant="primary">
            {saving ? "Saving..." : "Save Profile"}
          </Button>
        </div>
      }
    >
      <div className="space-y-5">
        <p className="font-mono text-[0.6875rem] leading-relaxed text-[var(--color-text-muted)]">
          The assistant reads this before every answer. Anything you name in a question — a
          horizon, a target — overrides these; they only fill in what you leave unsaid.
        </p>

        <Card className="space-y-3 p-4">
          <h3 className="label">Risk tolerance</h3>
          {RISK_LEVELS.map((level) => (
            <label
              key={level.value}
              className="flex cursor-pointer items-start gap-3 font-mono text-[10px] text-[var(--text-1)]"
            >
              <input
                checked={profile.risk_tolerance === level.value}
                name="risk_tolerance"
                onChange={() => update("risk_tolerance", level.value)}
                type="radio"
              />
              <span>
                <span className="block uppercase tracking-[0.08em]">{level.label}</span>
                <span className="text-[var(--color-text-muted)]">{level.hint}</span>
              </span>
            </label>
          ))}
        </Card>

        <Card className="space-y-4 p-4">
          <h3 className="label">Defaults when you don&apos;t say</h3>
          <label className="flex items-center justify-between gap-4 font-mono text-[10px] text-[var(--text-1)]">
            Horizon (months)
            <input
              className={`${inputClass} w-24 text-center`}
              min="0.25"
              onChange={(event) => update("default_horizon_months", Number(event.target.value))}
              step="0.5"
              type="number"
              value={profile.default_horizon_months}
            />
          </label>
          <label className="flex items-center justify-between gap-4 font-mono text-[10px] text-[var(--text-1)]">
            Target gain (%)
            <input
              className={`${inputClass} w-24 text-center`}
              min="0.5"
              onChange={(event) => update("default_target_gain_pct", Number(event.target.value))}
              step="0.5"
              type="number"
              value={profile.default_target_gain_pct}
            />
          </label>
          <label className="flex items-center justify-between gap-4 font-mono text-[10px] text-[var(--text-1)]">
            Capital available (₹)
            <input
              className={`${inputClass} w-32 text-center`}
              min="0"
              onChange={(event) => update("capital_available", Number(event.target.value))}
              type="number"
              value={profile.capital_available}
            />
          </label>
          <p className="font-mono text-[9px] leading-relaxed text-[var(--color-text-muted)]">
            Capital caps the suggested top-up amounts. Leave at 0 to size purely against your
            concentration limit.
          </p>
        </Card>

        <Card className="space-y-3 p-4">
          <h3 className="label">Never suggest</h3>
          <input
            className={`${inputClass} w-full`}
            onChange={(event) => update("avoid_symbols", parseSymbols(event.target.value))}
            placeholder="YESBANK, IDEA"
            type="text"
            value={(profile.avoid_symbols || []).join(", ")}
          />
          <p className="font-mono text-[9px] text-[var(--color-text-muted)]">
            Comma-separated NSE symbols. Dropped from both buy ideas and top-ups.
          </p>
        </Card>

        <Card className="space-y-3 p-4">
          <h3 className="label">Notes for the assistant</h3>
          <textarea
            className={`${inputClass} w-full resize-none`}
            onChange={(event) => update("notes", event.target.value)}
            placeholder="e.g. prefer large caps; avoid anything I'd sell before a year for tax reasons"
            rows={3}
            value={profile.notes || ""}
          />
        </Card>
      </div>
    </Drawer>
  );
}
