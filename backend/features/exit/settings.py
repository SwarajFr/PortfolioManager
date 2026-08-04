"""Exit-signal tuning: what each KPI is worth, and where the actions cut over.

Two independent dials, both user-owned:

* `function_scores` — the points a KPI contributes in each of its severity
  bands, worst band last. The *boundaries* are not here: they are hardcoded in
  `compute.py` (loss at -5/-10/-20 %, risk at 1.2x/1.5x the median, and so on).
  So a list of *n* entries means that KPI has *n* bands, and editing it
  re-weights the KPI without moving where the bands begin. The lists differ in
  length because the KPIs genuinely differ in how many distinctions are useful.
* `action_thresholds` — where the summed 0-100 score becomes EXIT / TRIM /
  WATCH. Anything below the lowest is HOLD.

Because the entries are weights rather than cut points, a list is only required
to be as long as its KPI has bands; nothing checks that it ascends. A user who
enters them out of order gets an odd but defensible scoring curve rather than a
rejected save — this is a personal tuning knob, not an API contract.
"""
from core.settings_store import (
    load_settings,
    reset_settings as reset_stored_settings,
    save_settings as save_stored_settings,
)

DEFAULT = {
    "action_thresholds": {
        "EXIT": 70,
        "TRIM": 50,
        "WATCH": 30,
    },
    "function_scores": {
        "loss_severity": [5, 10, 18, 25],
        "risk_vs_median": [8, 14, 20],
        "risk_adj_inefficiency": [8, 14, 20],
        "trend_weakness": [10, 20],
        "concentration": [5, 10, 15],
    },
}


def get_settings():
    return load_settings("exit_settings", DEFAULT)


def save_settings(config: dict):
    save_stored_settings("exit_settings", config)


def reset_settings():
    return reset_stored_settings("exit_settings", DEFAULT)
