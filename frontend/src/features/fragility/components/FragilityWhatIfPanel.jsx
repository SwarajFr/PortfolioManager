import { useState, useEffect } from "react";
import { getFragilityWhatIf } from "../../../services/fragilityService";

function Delta({ label, before, after, format = (v) => v.toFixed(2), isLoss = false }) {
  // isLoss=true means lower is better (stress loss, MRC, effective weight)
  // isLoss=false means higher is better (ENB)
  const improved = isLoss ? after < before : after > before;
  const tone =
    after === before ? "var(--text-3)" : improved ? "var(--profit)" : "var(--loss)";
  return (
    <div className="flex flex-col gap-[var(--space-1)]">
      <span className="text-[var(--text-xs)] text-[var(--text-3)] uppercase tracking-wider">
        {label}
      </span>
      <div className="flex items-baseline gap-[var(--space-2)]">
        <span className="text-[var(--text-2)] text-[var(--text-sm)]">{format(before)}</span>
        <span className="text-[var(--text-3)]">→</span>
        <span style={{ color: tone }} className="text-[var(--text-sm)] font-medium">
          {format(after)}
        </span>
      </div>
    </div>
  );
}

export default function FragilityWhatIfPanel({
  selected,
  baseEnb = 0,
  baseStressLoss = 0,
  onClose,
}) {
  const [weight, setWeight] = useState(
    selected ? Math.round(selected.trim_target_weight) : 10
  );
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Reset slider and results when the user switches to a different holding.
  useEffect(() => {
    setWeight(selected ? Math.round(selected.trim_target_weight) : 10);
    setResult(null);
    setError(null);
  }, [selected]);

  const selectedHolding =
    result?.holdings?.find((h) => h.ticker === selected?.ticker) ?? null;

  async function runSim() {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getFragilityWhatIf(selected.ticker, weight);
      setResult(data);
    } catch (e) {
      setError(e.message || "Simulation failed.");
    } finally {
      setLoading(false);
    }
  }

  if (!selected) {
    return (
      <div className="flex items-center justify-center h-24 text-[var(--text-3)] text-[var(--text-sm)]">
        Click Simulate on any holding
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-[var(--space-4)]">
      {/* Heading */}
      <div className="flex items-center justify-between">
        <h3 className="text-[var(--text-1)] text-[var(--text-base)] font-medium">
          Simulate: <span className="font-mono">{selected.ticker}</span>
        </h3>
        {onClose && (
          <button
            onClick={onClose}
            className="text-[var(--text-3)] hover:text-[var(--text-1)] text-[var(--text-sm)]"
          >
            ✕
          </button>
        )}
      </div>

      {/* Weight slider */}
      <div className="flex flex-col gap-[var(--space-2)]">
        <label className="text-[var(--text-xs)] text-[var(--text-3)]">
          New weight:{" "}
          <span className="text-[var(--text-1)]">{weight}%</span>
        </label>
        <input
          type="range"
          min={1}
          max={50}
          step={1}
          value={weight}
          onChange={(e) => {
            setWeight(Number(e.target.value));
            setResult(null);
          }}
          className="w-full accent-[var(--accent)]"
        />
        <div className="flex justify-between text-[var(--text-xs)] text-[var(--text-3)]">
          <span>1%</span>
          <span>50%</span>
        </div>
      </div>

      {/* Run button */}
      <button
        onClick={runSim}
        disabled={loading}
        className="px-[var(--space-4)] py-[var(--space-2)] bg-[var(--accent)] text-white rounded text-[var(--text-sm)] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {loading ? "Running…" : "Run simulation"}
      </button>

      {error && (
        <p className="text-[var(--loss)] text-[var(--text-xs)]">{error}</p>
      )}

      {/* Before / after results */}
      {result && (
        <div className="grid grid-cols-2 gap-[var(--space-3)] border-t border-[var(--border-subtle)] pt-[var(--space-4)]">
          <Delta
            label="ENB"
            before={baseEnb}
            after={result.enb}
            format={(v) => v.toFixed(1)}
          />
          <Delta
            label="Stress Loss"
            before={baseStressLoss}
            after={result.stress_loss_pct}
            format={(v) => `${v.toFixed(1)}%`}
            isLoss
          />
          {selectedHolding && (
            <>
              <Delta
                label="MRC"
                before={selected.mrc}
                after={selectedHolding.mrc}
                format={(v) => `${v.toFixed(1)}%`}
                isLoss
              />
              <Delta
                label="Eff. Weight"
                before={selected.effective_weight}
                after={selectedHolding.effective_weight}
                format={(v) => `${v.toFixed(1)}%`}
                isLoss
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}
