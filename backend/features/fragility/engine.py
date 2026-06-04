# backend/features/fragility/engine.py
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from scipy.linalg import eigvalsh

from core.settings_store import load_settings, save_settings

_ENB_HISTORY_TABLE = "fragility_enb_history"
_ENB_HISTORY_DEFAULTS = {"history": []}

SHORT_REGIME_WINDOW = 20
LONG_REGIME_WINDOW = 90


def _mean_offdiag_corr(cov: np.ndarray) -> float:
    sigma = np.sqrt(np.diag(cov))
    corr = cov / np.outer(sigma, sigma)
    np.fill_diagonal(corr, 0.0)
    n = corr.shape[0]
    return float(corr.sum() / (n * (n - 1))) if n > 1 else 0.0


def _regime_label(delta: float) -> str:
    if delta < 0.10:
        return "LOW"
    if delta <= 0.25:
        return "RISING"
    return "CRISIS"


class FragilityEngine:
    def __init__(self, long_window: int = 90):
        self.long_window = long_window

    def run(self, prices: pd.DataFrame, weights: dict[str, float]) -> dict:
        """
        prices: DataFrame, columns = tickers, index = dates (close prices).
        weights: {ticker: fraction}, fractions should be positive (will be renormalised).
        """
        # ── Stage 1: Return matrix ──────────────────────────────────────────
        R = np.log1p(prices.pct_change()).dropna()

        # Keep only tickers with sufficient history
        surviving = [c for c in R.columns if R[c].notna().sum() >= self.long_window]
        excluded = [c for c in R.columns if c not in surviving]
        R = R[surviving].dropna()

        # Align weights to surviving tickers
        w_raw = {t: weights[t] for t in surviving if t in weights}
        if not w_raw or len(w_raw) < 2:
            return self._empty_result(excluded)
        total = sum(w_raw.values())
        w_dict = {t: v / total for t, v in w_raw.items()}
        tickers = list(w_dict.keys())
        R = R[tickers]
        w = np.array([w_dict[t] for t in tickers])
        N = len(tickers)

        # ── Stage 2: Covariance, ENB, regime delta ──────────────────────────
        cov = LedoitWolf().fit(R.values).covariance_
        sigma = np.sqrt(np.diag(cov))
        corr = cov / np.outer(sigma, sigma)
        np.clip(corr, -1.0, 1.0, out=corr)

        # Regime delta
        recent_short = R.iloc[-SHORT_REGIME_WINDOW:]
        recent_long = R.iloc[-LONG_REGIME_WINDOW:]
        cov_long = LedoitWolf().fit(recent_long.values).covariance_ if len(recent_long) >= SHORT_REGIME_WINDOW else cov
        cov_short = LedoitWolf().fit(recent_short.values).covariance_ if len(recent_short) >= SHORT_REGIME_WINDOW else cov
        mean_corr_long = _mean_offdiag_corr(cov_long)
        mean_corr_short = _mean_offdiag_corr(cov_short)
        regime_delta = float(mean_corr_short - mean_corr_long)
        label = _regime_label(regime_delta)

        # ── Stage 3: Effective weight ────────────────────────────────────────
        ew = w + (corr - np.eye(N)) @ w
        ew = np.clip(ew, 0.0, None)
        with np.errstate(divide="ignore", invalid="ignore"):
            ew_ratio = np.where(w > 0, ew / w, 0.0)

        # ── Stage 4: MRC and trim target ─────────────────────────────────────
        port_var = float(w @ cov @ w)
        mrc = (cov @ w) / port_var  # fractional risk contributions, sums to 1
        mrc_pct = mrc * 100.0

        med_mrc = float(np.median(mrc))
        trim_raw = w * (med_mrc / np.where(mrc > 0, mrc, med_mrc))
        trim_raw = np.clip(trim_raw, 0.01, None)
        trim_target_w = trim_raw / trim_raw.sum()

        # Stress loss (99% VaR, equity correlations → 0.85)
        cov_stressed = cov.copy()
        for i in range(N):
            for j in range(N):
                if i != j:
                    cov_stressed[i, j] = 0.85 * sigma[i] * sigma[j]
        stress_loss_pct = float(-2.33 * np.sqrt(w @ cov_stressed @ w) * 100)

        # What-if: apply trim weights, recompute ENB (MRC-based) + stress loss
        # Risk-contribution ENB = 1/sum(rc_i^2) is weight-dependent and shows
        # improvement when trim weights are more evenly distributed.
        w_trim = trim_target_w
        port_var_trim = float(w_trim @ cov @ w_trim)
        mrc_trim = (cov @ w_trim) / port_var_trim
        enb_new = float(1.0 / np.sum(mrc_trim ** 2))
        # Use same MRC formula for base ENB (consistent with what-if)
        enb = float(1.0 / np.sum(mrc ** 2))
        stress_loss_new_pct = float(-2.33 * np.sqrt(w_trim @ cov_stressed @ w_trim) * 100)

        # ── ENB history ──────────────────────────────────────────────────────
        enb_history = self._update_enb_history(enb)

        # ── Stage 5: Urgency score per holding ───────────────────────────────
        # "falling over last 5 stored values" = current < value 5 steps ago
        enb_falling = len(enb_history) >= 6 and enb_history[-1] < enb_history[-6]
        regime_score = 1 if label == "RISING" else (2 if label == "CRISIS" else 0)
        med_mrc_val = float(np.median(mrc_pct))

        holdings_out = []
        for i, t in enumerate(tickers):
            score = 0
            signals = []
            if enb_falling:
                score += 1
                signals.append("ENB declining")
            score += regime_score
            if regime_score > 0:
                signals.append(f"Regime {label}")
            if mrc_pct[i] > 2 * med_mrc_val:
                score += 1
                signals.append("MRC outlier")
            if ew_ratio[i] > 1.5:
                score += 1
                signals.append("Hidden concentration")

            urgency = "ACT" if score >= 4 else ("WATCH" if score >= 2 else "MONITOR")
            holdings_out.append({
                "ticker": t,
                "weight": round(float(w[i]) * 100, 2),
                "effective_weight": round(float(ew[i]) * 100, 2),
                "ew_ratio": round(float(ew_ratio[i]), 3),
                "mrc": round(float(mrc_pct[i]), 2),
                "trim_target_weight": round(float(trim_target_w[i]) * 100, 2),
                "score": int(score),
                "urgency": urgency,
                "signals": signals,
                "hidden_risk": bool(ew_ratio[i] > 1.5),
            })

        # Sort by score descending
        holdings_out.sort(key=lambda x: x["score"], reverse=True)

        return {
            "enb": round(enb, 2),
            "enb_new": round(enb_new, 2),
            "regime_label": label,
            "regime_delta": round(regime_delta, 4),
            "mean_corr_long": round(mean_corr_long, 4),
            "stress_loss_pct": round(stress_loss_pct, 2),
            "stress_loss_new_pct": round(stress_loss_new_pct, 2),
            "enb_history": enb_history,
            "tickers_included": tickers,
            "tickers_excluded": excluded,
            "corr_matrix": corr.tolist(),
            "tickers_corr": tickers,
            "holdings": holdings_out,
        }

    def _update_enb_history(self, enb: float) -> list[float]:
        stored = load_settings(_ENB_HISTORY_TABLE, _ENB_HISTORY_DEFAULTS)
        history: list[float] = stored.get("history", [])
        history.append(round(enb, 2))
        history = history[-30:]
        save_settings(_ENB_HISTORY_TABLE, {"history": history})
        return history

    def _empty_result(self, excluded: list[str]) -> dict:
        return {
            "enb": 0.0, "enb_new": 0.0,
            "regime_label": "LOW", "regime_delta": 0.0,
            "mean_corr_long": 0.0,
            "stress_loss_pct": 0.0, "stress_loss_new_pct": 0.0,
            "enb_history": [],
            "tickers_included": [], "tickers_excluded": excluded,
            "corr_matrix": [], "tickers_corr": [],
            "holdings": [],
        }
