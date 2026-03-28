"""
Exit Signals Engine — Pure computation layer.
Scores each holding 0–100 across 5 KPIs and assigns an action.
"""

import numpy as np
import pandas as pd
from .settings import get_settings


# KPI 1: Loss Severity
def _score_loss_severity(return_pct: float, scores: list) -> int:
    """Capital protection — penalises unrealised losses."""
    if return_pct >= 0:
        return 0
    if return_pct >= -5:
        return scores[0]         
    if return_pct >= -10:
        return scores[1]
    if return_pct >= -20:
        return scores[2]
    return scores[3]


# KPI 2: Risk vs Median
def _score_risk_vs_median(volatility: float, median_vol: float, scores: list) -> int:
    """Flags stocks riskier than the portfolio norm."""
    if median_vol == 0:
        return 0
    ratio = volatility / median_vol
    if ratio <= 1.0:
        return 0
    if ratio <= 1.2:
        return scores[0]
    if ratio <= 1.5:
        return scores[1]
    return scores[2]


# KPI 3: Risk-Adjusted Inefficiency
def _score_risk_adj_inefficiency(rar: float, median_rar: float, scores: list) -> int:
    """Eliminates high-risk, low-reward positions (Sharpe-lite)."""
    if rar >= median_rar:
        return 0
    if rar >= 0:
        return scores[0]
    if rar >= -1:          # moderately negative
        return scores[1]
    return scores[2]              # very negative


# KPI 4: Trend Weakness
def _score_trend_weakness(ltp: float, ma50: float, ma200: float, scores: list) -> int:
    """Timing confirmation via moving averages."""
    if ltp < ma50 and ma50 < ma200:
        return scores[1]
    if ltp < ma50:
        return scores[0]
    return 0


# KPI 5: Concentration Penalty
def _score_concentration(weight_pct: float, scores: list) -> int:
    """Penalises over-sized positions."""
    if weight_pct <= 5:
        return 0
    if weight_pct <= 8:
        return scores[0]
    if weight_pct <= 12:
        return scores[1]
    return scores[2]


#  Action mapping
def _map_action(score: int, thresholds: dict) -> str:
    if score >= thresholds.get("EXIT", 70):
        return "EXIT"
    if score >= thresholds.get("TRIM", 50):
        return "TRIM"
    if score >= thresholds.get("WATCH", 30):
        return "WATCH"
    return "HOLD"


# Compute
def compute_exit_signals(
    holdings_df: pd.DataFrame,
    history: dict[int, pd.DataFrame],
) -> dict:
    """
    Parameters
    ----------
    holdings_df : DataFrame with columns from Kite holdings
        (tradingsymbol, last_price, average_price, quantity, instrument_token, …)
    history : {instrument_token: DataFrame(date, close, …)}

    Returns
    -------
    dict with keys: summary, signals (list sorted by exit_score desc)
    """
    settings = get_settings()
    thresholds = settings.get("action_thresholds", {})
    fn_scores = settings.get("function_scores", {})

    total_value = (holdings_df["last_price"] * holdings_df["quantity"]).sum()

    rows = []
    volatilities = []
    rars = []

    for _, h in holdings_df.iterrows():
        token = h["instrument_token"]
        ltp = h["last_price"]
        avg_price = h["average_price"]
        qty = h["quantity"]
        symbol = h["tradingsymbol"]

        # Return %
        return_pct = ((ltp - avg_price) / avg_price * 100) if avg_price else 0

        # Current value & weight
        value = ltp * qty
        invested = avg_price * qty
        weight_pct = (value / total_value * 100) if total_value else 0

        # Historical analysis
        hist = history.get(token)
        if hist is not None and len(hist) >= 10:
            closes = hist["close"].values.astype(float)
            daily_returns = np.diff(closes) / closes[:-1]
            std_dev = float(np.std(daily_returns, ddof=1)) if len(daily_returns) > 1 else 0
            volatility = std_dev * np.sqrt(252)

            # Moving averages
            ma50 = float(np.mean(closes[-50:])) if len(closes) >= 50 else float(np.mean(closes))
            ma200 = float(np.mean(closes[-200:])) if len(closes) >= 200 else float(np.mean(closes))
        else:
            volatility = 0
            ma50 = ltp
            ma200 = ltp

        # Risk-adjusted return (Sharpe-lite: return / volatility)
        rar = (return_pct / volatility) if volatility > 0 else 0

        volatilities.append(volatility)
        rars.append(rar)

        rows.append({
            "symbol": symbol,
            "ltp": float(ltp),
            "avg_price": float(avg_price),
            "quantity": int(qty),
            "value": float(value),
            "invested": float(invested),
            "return_pct": round(return_pct, 2),
            "weight_pct": round(weight_pct, 2),
            "volatility": round(volatility, 4),
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2),
            "rar": round(rar, 4),
        })

    # Portfolio-level medians
    median_vol = float(np.median(volatilities)) if volatilities else 0
    median_rar = float(np.median(rars)) if rars else 0

    # Score each stock
    signals = []
    for r in rows:
        s1 = _score_loss_severity(r["return_pct"], fn_scores.get("loss_severity", [5, 10, 18, 25]))
        s2 = _score_risk_vs_median(r["volatility"], median_vol, fn_scores.get("risk_vs_median", [8, 14, 20]))
        s3 = _score_risk_adj_inefficiency(r["rar"], median_rar, fn_scores.get("risk_adj_inefficiency", [8, 14, 20]))
        s4 = _score_trend_weakness(r["ltp"], r["ma50"], r["ma200"], fn_scores.get("trend_weakness", [10, 20]))
        s5 = _score_concentration(r["weight_pct"], fn_scores.get("concentration", [5, 10, 15]))

        exit_score = s1 + s2 + s3 + s4 + s5
        action = _map_action(exit_score, thresholds)

        signals.append({
            "symbol": r["symbol"],
            "ltp": r["ltp"],
            "avg_price": r["avg_price"],
            "quantity": r["quantity"],
            "value": r["value"],
            "invested": r["invested"],
            "return_pct": r["return_pct"],
            "weight_pct": r["weight_pct"],
            "scores": {
                "loss_severity": s1,
                "risk_vs_median": s2,
                "risk_adj_inefficiency": s3,
                "trend_weakness": s4,
                "concentration": s5,
            },
            "exit_score": exit_score,
            "action": action,
        })

    # Sort descending by exit_score
    signals.sort(key=lambda x: x["exit_score"], reverse=True)

    # Summary
    action_counts = {"EXIT": 0, "TRIM": 0, "WATCH": 0, "HOLD": 0}
    total_score = 0
    for s in signals:
        action_counts[s["action"]] += 1
        total_score += s["exit_score"]

    n = len(signals)
    summary = {
        "total_holdings": n,
        "avg_exit_score": round(total_score / n, 1) if n else 0,
        "action_counts": action_counts,
        "median_volatility": round(median_vol, 4),
        "median_rar": round(median_rar, 4),
    }

    return {"summary": summary, "signals": signals}
