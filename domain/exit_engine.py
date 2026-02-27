import numpy as np
from services.price_history import (
    fetch_historical_data,
    compute_moving_averages,
    compute_annualized_volatility,
)

# =========================
# KPI 1 — Loss Severity (0–25)
# =========================

def score_loss_severity(return_pct):
    if return_pct >= 0:
        return 0
    if return_pct >= -10:
        return 10
    if return_pct >= -20:
        return 18
    return 25


# =========================
# KPI 2 — Risk vs Portfolio Median (0–20)
# =========================

def score_risk_vs_median(stock_vol, median_vol):
    if median_vol == 0:
        return 0

    ratio = min(stock_vol / median_vol, 2.0)  # cap extreme volatility spikes to avoid noise dominating

    if ratio <= 1.0:
        return 0
    if ratio <= 1.2:
        return 8
    if ratio <= 1.5:
        return 14
    return 20


# =========================
# KPI 3 — Risk-Adjusted Inefficiency (0–20)
# =========================

def score_rar_inefficiency(rar, median_rar):
    if median_rar == 0:
        return 0

    if rar >= median_rar:
        return 0
    if rar >= 0:
        return 8
    if rar >= -1:
        return 14
    return 20


# =========================
# KPI 4 — Trend Weakness (0–20)
# =========================

def score_trend_weakness(ltp, ma50, ma200):
    if ma50 is None:
        return 0

    if ma200 is not None and ltp < ma50 and ma50 < ma200:
        return 20
    if ltp < ma50:
        return 10
    return 0


# =========================
# KPI 5 — Concentration Penalty (0–15)
# =========================

def score_concentration(weight_pct):
    if weight_pct <= 5:
        return 0
    if weight_pct <= 8:
        return 5
    if weight_pct <= 12:
        return 10
    return 15


# =========================
# Action Mapping
# =========================

ACTION_TIERS = [
    (70, "Exit",  "badge-exit"),
    (50, "Trim",  "badge-trim"),
    (30, "Watch", "badge-watch"),
    (0,  "Hold",  "badge-hold"),
]

def map_action(score):
    for threshold, label, badge in ACTION_TIERS:
        if score >= threshold:
            return label, badge
    return "Hold", "badge-hold"


# =========================
# Orchestrator
# =========================

def compute_exit_signals(kite, df):
    total_value = df["value"].sum()
    results = []

    histories = {}
    vols = {}
    rars = {}

    # fetch history once per stock (avoids double API calls + MA/vol mismatch)
    for _, row in df.iterrows():
        symbol = row["tradingsymbol"]
        token = row["instrument_token"]

        hist = fetch_historical_data(kite, token, days=365)
        histories[symbol] = hist

        vol = compute_annualized_volatility(hist)
        vols[symbol] = vol

        ret = row["return_pct"]
        rars[symbol] = (ret / 100) / vol if vol > 0 else 0.0  # fix unit mismatch (percent → decimal)

    # exclude ultra-low vol instruments so ETFs don’t distort median risk
    vol_values = [v for v in vols.values() if v > 0.08]
    median_vol = float(np.median(vol_values)) if vol_values else 0.0

    # exclude zero RAR values to avoid collapsing median toward zero
    rar_values = [r for r in rars.values() if r != 0]
    median_rar = float(np.median(rar_values)) if rar_values else 0.0

    for _, row in df.iterrows():
        symbol = row["tradingsymbol"]
        ltp = row["last_price"]
        ret = row["return_pct"]
        weight = (row["value"] / total_value * 100) if total_value else 0

        ma50, ma200 = compute_moving_averages(histories[symbol])

        s1 = score_loss_severity(ret)
        s2 = score_risk_vs_median(vols[symbol], median_vol)
        s3 = score_rar_inefficiency(rars[symbol], median_rar)
        s4 = score_trend_weakness(ltp, ma50, ma200)
        s5 = score_concentration(weight)

        exit_score = s1 + s2 + s3 + s4 + s5
        action, badge = map_action(exit_score)

        results.append({
            "symbol": symbol,
            "ltp": ltp,
            "return_pct": ret,
            "loss_severity": s1,
            "risk_score": s2,
            "rar_score": s3,
            "trend_score": s4,
            "concentration": s5,
            "exit_score": exit_score,
            "action": action,
            "badge": badge,
        })

    results.sort(key=lambda r: r["exit_score"], reverse=True)
    return results