/**
 * Editor for the overview config: group membership, target bands, and caps.
 *
 * The whole drawer edits one `config` object and saves it in a single PUT, so
 * nothing is persisted until the user commits. That is what makes destructive
 * edits (removing a group, reassigning every unassigned stock) safe to offer —
 * closing without saving discards them.
 *
 * Two structural choices worth knowing before editing this file:
 *
 * - **Clone-then-mutate.** `updateConfig` hands the updater a `structuredClone`
 *   of the current config and stores whatever comes back. The updaters read as
 *   plain mutation (`delete draft.groups[name]`) while React still sees a new
 *   object every time, so nested changes cannot be missed by identity checks.
 *   Do not mutate `config` directly — only the draft inside `updateConfig`.
 *
 * - **`symbolGroup` is an inverted index**, rebuilt only when config changes.
 *   The alternative — scanning every group's array per symbol — would run on
 *   each keystroke of the filter, since the sort comparator needs a symbol's
 *   group for both sides of every comparison.
 *
 * The filter is a `useDeferredValue` because that sort re-runs the whole list;
 * deferring it keeps typing responsive and lets the stale list paint meanwhile.
 *
 * Saving is blocked while any holding is unassigned. The backend would accept
 * it, but `compute.py` buckets unassigned symbols into a synthetic "Unassigned"
 * group that has no target band — so the overview would show a group the user
 * cannot act on. Better to refuse here than to render something unfixable.
 */
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Drawer from "../../../components/ui/Drawer";
import StatusBadge from "../../../components/ui/StatusBadge";
import {
  getPortfolioSettings,
  resetPortfolioSettings,
  savePortfolioSettings,
} from "../../../services/portfolioService";

const inputClass =
  "w-full rounded-[var(--radius-sm)] border border-[var(--border-1)] bg-[var(--surface)] px-3 py-2 font-mono text-[var(--text-xs)] text-[var(--text-1)] outline-none transition focus:border-[var(--accent)]";

function cloneConfig(config) {
  return structuredClone(config);
}

export default function PortfolioSettingsDrawer({ onClose, onSaved }) {
  const [config, setConfig] = useState(null);
  const [holdings, setHoldings] = useState([]);
  const [saving, setSaving] = useState(false);
  const [newGroup, setNewGroup] = useState("");
  const [filter, setFilter] = useState("");
  const deferredFilter = useDeferredValue(filter);

  useEffect(() => {
    let cancelled = false;

    getPortfolioSettings()
      .then((payload) => {
        if (!cancelled) {
          setConfig(cloneConfig(payload.config));
          setHoldings(payload.holdings || []);
        }
      })
      .catch(() => toast.error("Failed to load portfolio settings"));

    return () => {
      cancelled = true;
    };
  }, []);

  const symbolGroup = useMemo(() => {
    const lookup = {};
    for (const [group, symbols] of Object.entries(config?.groups || {})) {
      for (const symbol of symbols) lookup[symbol] = group;
    }
    return lookup;
  }, [config]);

  const groupNames = useMemo(() => Object.keys(config?.groups || {}), [config]);
  const unassignedCount = holdings.filter((symbol) => !symbolGroup[symbol]).length;

  const filteredHoldings = useMemo(() => {
    const search = deferredFilter.toLowerCase();
    return holdings
      .filter((symbol) => symbol.toLowerCase().includes(search))
      .sort((left, right) => {
        const leftGroup = symbolGroup[left] || "";
        const rightGroup = symbolGroup[right] || "";
        if (!leftGroup && rightGroup) return -1;
        if (leftGroup && !rightGroup) return 1;
        if (leftGroup !== rightGroup) return leftGroup.localeCompare(rightGroup);
        return left.localeCompare(right);
      });
  }, [deferredFilter, holdings, symbolGroup]);

  if (!config) {
    return (
      <Drawer onClose={onClose} title="Overview Settings">
        <div className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] p-5 text-sm text-[var(--text-2)]">
          Loading settings...
        </div>
      </Drawer>
    );
  }

  const updateConfig = (updater) => setConfig((current) => updater(cloneConfig(current)));

  const assignStock = (symbol, nextGroup) => {
    updateConfig((draft) => {
      for (const group of Object.keys(draft.groups)) {
        draft.groups[group] = draft.groups[group].filter((item) => item !== symbol);
      }
      if (nextGroup && draft.groups[nextGroup]) draft.groups[nextGroup].push(symbol);
      return draft;
    });
  };

  const assignAllUnassigned = (group) => {
    updateConfig((draft) => {
      for (const symbol of holdings) {
        const alreadyAssigned = Object.values(draft.groups).some((symbols) => symbols.includes(symbol));
        if (!alreadyAssigned && draft.groups[group]) draft.groups[group].push(symbol);
      }
      return draft;
    });
  };

  const addGroup = () => {
    const name = newGroup.trim();
    if (!name || config.groups[name]) return;
    updateConfig((draft) => {
      draft.groups[name] = [];
      draft.targets[name] = [0, 0];
      return draft;
    });
    setNewGroup("");
  };

  const removeGroup = (name) => {
    updateConfig((draft) => {
      delete draft.groups[name];
      delete draft.targets[name];
      return draft;
    });
  };

  // Fires per keystroke, so a rename happens one character at a time. It looks
  // wrong but is correct: each pass carries the membership array and target
  // band across to the new key, so no data is lost mid-word. Debouncing would
  // need the input to hold its own draft state, which is not worth it here.
  const renameGroup = (oldName, newName) => {
    if (!newName || newName === oldName) return;
    updateConfig((draft) => {
      draft.groups[newName] = draft.groups[oldName] || [];
      delete draft.groups[oldName];
      if (draft.targets[oldName]) {
        draft.targets[newName] = draft.targets[oldName];
        delete draft.targets[oldName];
      }
      return draft;
    });
  };

  const setTarget = (group, index, value) => {
    updateConfig((draft) => {
      draft.targets[group] ||= [0, 0];
      draft.targets[group][index] = Number(value) || 0;
      return draft;
    });
  };

  const setConcentration = (key, value) => {
    updateConfig((draft) => {
      draft.concentration[key] = Number(value) || 0;
      return draft;
    });
  };

  const handleSave = async () => {
    if (unassignedCount > 0) {
      toast.error(`${unassignedCount} stock(s) still unassigned`);
      return;
    }

    setSaving(true);
    try {
      await savePortfolioSettings(config);
      toast.success("Portfolio settings saved");
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
      const payload = await resetPortfolioSettings();
      setConfig(cloneConfig(payload.config));
      toast.success("Reset to defaults");
      onSaved?.();
    } catch {
      toast.error("Reset failed");
    }
  };

  return (
      <Drawer
      onClose={onClose}
      title="Overview Settings"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button onClick={handleReset} variant="ghost">
            Reset Defaults
          </Button>
          <div className="flex items-center gap-3">
            {unassignedCount > 0 ? <StatusBadge tone="warning">{unassignedCount} unassigned</StatusBadge> : null}
            <Button disabled={saving || unassignedCount > 0} onClick={handleSave} variant="primary">
              {saving ? "Saving..." : "Save Settings"}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-5">
        <Card className="p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-mono text-[var(--text-xs)] font-semibold tracking-[0.04em] text-[var(--text-2)]">Assign stocks to groups</h3>
            {unassignedCount > 0 ? <StatusBadge tone="warning">{unassignedCount} open</StatusBadge> : null}
          </div>

          {unassignedCount > 0 ? (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-[var(--text-2)]">
              <span>Quick assign all unassigned to</span>
              <select
                className="rounded-[var(--radius-sm)] border border-[var(--border-1)] bg-[var(--surface)] px-2 py-1 font-mono text-[var(--text-xs)] text-[var(--text-1)]"
                defaultValue=""
                onChange={(event) => {
                  if (event.target.value) assignAllUnassigned(event.target.value);
                  event.target.value = "";
                }}
              >
                <option value="" disabled>
                  Select group
                </option>
                {groupNames.map((group) => (
                  <option key={group} value={group}>
                    {group}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <input
            className={`${inputClass} mt-4`}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Search holdings..."
            value={filter}
          />

          <div className="mt-4 grid grid-cols-2 border-b border-[var(--border)] pb-2 font-mono text-[var(--text-xs)] font-semibold tracking-[0.04em] text-[var(--text-3)]">
            <div>Symbol</div>
            <div>Group</div>
          </div>
          <div className="mt-2 max-h-80 space-y-1 overflow-y-auto pr-1">
            {filteredHoldings.map((symbol) => {
              const group = symbolGroup[symbol] || "";
              const isUnassigned = !group;

              return (
                <div
                  key={symbol}
                  className={`grid grid-cols-2 items-center gap-3 rounded-[var(--radius-sm)] px-2 py-2 ${
                    isUnassigned ? "bg-[rgba(242,184,75,0.12)]" : "hover:bg-[var(--surface-1)]"
                  }`}
                >
                  <span className={`font-mono text-sm ${isUnassigned ? "text-[var(--warning)]" : "text-[var(--text-1)]"}`}>
                    {symbol}
                  </span>
                  <select
                    className={`rounded-[var(--radius-sm)] border px-2 py-1.5 font-mono text-[var(--text-xs)] ${
                      isUnassigned
                        ? "border-[rgba(242,184,75,0.4)] text-[var(--warning)] bg-[var(--surface)]"
                        : "border-[var(--border-1)] text-[var(--text-1)] bg-[var(--surface)]"
                    }`}
                    onChange={(event) => assignStock(symbol, event.target.value)}
                    value={group}
                  >
                    <option value="">Unassigned</option>
                    {groupNames.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>
        </Card>

        <Card className="space-y-3 p-4">
          <h3 className="font-mono text-[var(--text-xs)] font-semibold tracking-[0.04em] text-[var(--text-2)]">Manage groups</h3>
          {groupNames.map((group) => (
            <div key={group} className="flex items-center gap-2">
              <input className={inputClass} onChange={(event) => renameGroup(group, event.target.value)} value={group} />
              <span className="w-8 text-center font-mono text-[10px] text-[var(--text-3)]">{config.groups[group].length}</span>
              <Button className="px-3" onClick={() => removeGroup(group)} variant="danger">
                Remove
              </Button>
            </div>
          ))}
          <div className="flex gap-2 border-t border-[var(--border)] pt-3">
            <input
              className={inputClass}
              onChange={(event) => setNewGroup(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && addGroup()}
              placeholder="New group name..."
              value={newGroup}
            />
            <Button onClick={addGroup} variant="secondary">
              Add
            </Button>
          </div>
        </Card>

        <Card className="space-y-3 p-4">
          <h3 className="font-mono text-[var(--text-xs)] font-semibold tracking-[0.04em] text-[var(--text-2)]">Allocation targets</h3>
          <div className="grid grid-cols-3 gap-3 font-mono text-[var(--text-xs)] font-semibold tracking-[0.04em] text-[var(--text-3)]">
            <div>Group</div>
            <div className="text-center">Min %</div>
            <div className="text-center">Max %</div>
          </div>
          {Object.entries(config.targets).map(([group, [min, max]]) => (
            <div key={group} className="grid grid-cols-3 items-center gap-3">
              <span className="font-mono text-[10px] text-[var(--text-1)]">{group}</span>
              <input className={`${inputClass} text-center`} onChange={(event) => setTarget(group, 0, event.target.value)} type="number" value={min} />
              <input className={`${inputClass} text-center`} onChange={(event) => setTarget(group, 1, event.target.value)} type="number" value={max} />
            </div>
          ))}
        </Card>

        <Card className="space-y-4 p-4">
          <h3 className="font-mono text-[var(--text-xs)] font-semibold tracking-[0.04em] text-[var(--text-2)]">Concentration limits</h3>
          {[
            ["top5", "Top 5 Holdings Limit"],
            ["single", "Single Stock Limit"],
          ].map(([key, label]) => (
            <label key={key} className="flex items-center justify-between gap-4 font-mono text-[10px] text-[var(--text-1)]">
              {label}
              <div className="flex items-center gap-2">
                <input
                  className={`${inputClass} w-24 text-center`}
                  onChange={(event) => setConcentration(key, event.target.value)}
                  type="number"
                  value={config.concentration[key]}
                />
                <span className="font-mono text-[10px] text-[var(--text-3)]">%</span>
              </div>
            </label>
          ))}
        </Card>
      </div>
    </Drawer>
  );
}
