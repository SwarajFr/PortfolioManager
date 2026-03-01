import numpy as np
from services.price_history import (
    fetch_historical_data,
    compute_moving_averages,
    compute_annualized_volatility,
)
from engines.exit_engine.settings import (
    LOSS_SEVERITY_TIERS, LOSS_SEVERITY_MAX,
    RISK_RATIO_CAP, RISK_RATIO_TIERS, RISK_RATIO_MAX,
    RAR_TIERS, RAR_MAX,
    TREND_BELOW_MA50, TREND_DEATH_CROSS,
    CONCENTRATION_TIERS, CONCENTRATION_MAX,
    ACTION_TIERS, VOL_FLOOR, HISTORY_DAYS,
)


def score_loss_severity(return_pct):
    if return_pct >= 0:
        return 0
    for threshold, score in LOSS_SEVERITY_TIERS:
        if return_pct >= threshold:
            return score
    return LOSS_SEVERITY_MAX


def score_risk_vs_median(stock_vol, median_vol):
    if median_vol == 0:
        return 0
    ratio = min(stock_vol / median_vol, RISK_RATIO_CAP)
    for threshold, score in RISK_RATIO_TIERS:
        if ratio <= threshold:
            return score
    return RISK_RATIO_MAX


def score_rar_inefficiency(rar, median_rar):
    if median_rar == 0:
        return 0
    if rar >= median_rar:
        return 0
    for threshold, score in RAR_TIERS:
        if rar >= threshold:
            return score
    return RAR_MAX


def score_trend_weakness(ltp, ma50, ma200):
    if ma50 is None:
        return 0
    if ma200 is not None and ltp < ma50 and ma50 < ma200:
        return TREND_DEATH_CROSS
    if ltp < ma50:
        return TREND_BELOW_MA50
    return 0


def score_concentration(weight_pct):
    for threshold, score in CONCENTRATION_TIERS:
        if weight_pct <= threshold:
            return score
    return CONCENTRATION_MAX


def map_action(score):
    for threshold, label, badge in ACTION_TIERS:
        if score >= threshold:
            return label, badge
    return "Hold", "badge-hold"


def compute_exit_signals(kite, df):
    total_value = df["value"].sum()
    results = []
    histories = {}
    vols = {}
    rars = {}

    for _, row in df.iterrows():
        symbol = row["tradingsymbol"]
        token = row["instrument_token"]

        hist = fetch_historical_data(kite, token, days=HISTORY_DAYS)
        histories[symbol] = hist

        vol = compute_annualized_volatility(hist)
        vols[symbol] = vol

        ret = row["return_pct"]
        rars[symbol] = (ret / 100) / vol if vol > 0 else 0.0  # percent → decimal

    vol_values = [v for v in vols.values() if v > VOL_FLOOR]
    median_vol = float(np.median(vol_values)) if vol_values else 0.0

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
