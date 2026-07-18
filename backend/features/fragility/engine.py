# backend/features/fragility/engine.py
"""Descriptive diversification-metrics engine.

This is the DESCRIPTIVE replacement for the old prescription engine. It reports
what the portfolio's correlation/concentration structure *is* — it does not
prescribe trims, urgency scores, or effective-weight targets.

All metrics are estimated off a single Ledoit-Wolf shrunk covariance Σ.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

TRADING_DAYS = 252


@dataclass
class DiversityResult:
    """JSON-serializable container for the descriptive metrics.

    ``to_dict()`` is the shape the FastAPI route and React component consume.
    """

    symbols: list[str]
    num_positions: int
    portfolio_variance: float
    portfolio_vol_daily: float
    portfolio_vol: float  # annualized — the headline volatility
    diversification_ratio: float
    enb: float  # PCA / principal-portfolio ENB (Meucci)
    weight_entropy: float
    effective_positions: float
    normalized_entropy: float
    concentration_gap: float
    avg_correlation: float
    max_correlation: float
    max_correlation_pair: tuple[str, str] | None
    correlation_matrix: np.ndarray
    principal_risk_contributions: list[float]
    principal_bets: list[list[dict]] = field(default_factory=list)
    tickers_excluded: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scalars": {
                "num_positions": int(self.num_positions),
                "diversification_ratio": round(float(self.diversification_ratio), 4),
                "enb": round(float(self.enb), 4),
                "effective_positions": round(float(self.effective_positions), 4),
                "normalized_entropy": round(float(self.normalized_entropy), 4),
                "weight_entropy": round(float(self.weight_entropy), 4),
                "concentration_gap": round(float(self.concentration_gap), 4),
                "portfolio_vol": round(float(self.portfolio_vol), 6),
                "portfolio_vol_daily": round(float(self.portfolio_vol_daily), 6),
                "portfolio_variance": float(self.portfolio_variance),
                "avg_correlation": round(float(self.avg_correlation), 4),
                "max_correlation": round(float(self.max_correlation), 4),
            },
            "max_correlation_pair": (
                list(self.max_correlation_pair) if self.max_correlation_pair else None
            ),
            "principal_risk_contributions": [
                round(float(p), 6) for p in self.principal_risk_contributions
            ],
            "principal_bets": self.principal_bets,
            "correlation": {
                "symbols": list(self.symbols),
                "matrix": np.round(self.correlation_matrix, 4).tolist(),
            },
            "tickers_excluded": list(self.tickers_excluded),
        }


class DiversityEngine:
    """Compute descriptive diversification metrics from returns + weights.

    Math-only: everything is derived from the returns and weights via a
    Ledoit-Wolf shrunk covariance. No external classification data (sector,
    asset class) is required, since Kite does not provide it.
    """

    def run(self, returns: pd.DataFrame, weights: pd.Series) -> DiversityResult:
        """
        returns: T x N daily returns, columns = symbols.
        weights: Series {symbol: weight}. Reindexed to ``returns.columns`` and
                 renormalized to sum 1. Long-only assumed. Raises ValueError if a
                 weighted symbol has no returns column.
        """
        returns = returns.dropna(how="any")
        cols = list(returns.columns)

        # A weighted symbol with no returns column is a hard error (not a silent drop).
        missing = [
            s for s in weights.index if s not in cols and float(weights[s]) != 0.0
        ]
        if missing:
            raise ValueError(f"Weighted symbols have no returns: {missing}")

        w_series = weights.reindex(cols).fillna(0.0).astype(float)
        held = w_series[w_series > 0].index.tolist()
        if not held:
            raise ValueError("No positive-weight positions to analyse.")

        symbols = held
        R = returns[held]
        w = w_series[held].to_numpy()
        w = w / w.sum()  # renormalize to sum 1
        N = len(symbols)

        # ── Ledoit-Wolf shrunk covariance (the estimator all metrics share) ──
        cov = LedoitWolf().fit(R.to_numpy()).covariance_
        sigma = np.sqrt(np.diag(cov))

        corr = self._correlation(cov, sigma)
        avg_corr, max_corr, max_pair = self._correlation_summary(corr, symbols)

        port_var = float(w @ cov @ w)
        port_vol_daily = math.sqrt(port_var) if port_var > 0 else 0.0

        dr = self._diversification_ratio(w, sigma, port_vol_daily)
        enb, prc, bets = self._pca_enb(cov, w, symbols)
        H, eff_positions, norm_entropy = self._weight_entropy(w, N)
        concentration_gap = eff_positions / enb if enb > 0 else 0.0

        return DiversityResult(
            symbols=symbols,
            num_positions=N,
            portfolio_variance=port_var,
            portfolio_vol_daily=port_vol_daily,
            portfolio_vol=port_vol_daily * math.sqrt(TRADING_DAYS),
            diversification_ratio=dr,
            enb=enb,
            weight_entropy=H,
            effective_positions=eff_positions,
            normalized_entropy=norm_entropy,
            concentration_gap=concentration_gap,
            avg_correlation=avg_corr,
            max_correlation=max_corr,
            max_correlation_pair=max_pair,
            correlation_matrix=corr,
            principal_risk_contributions=prc,
            principal_bets=bets,
        )

    # ── Metric 1: correlation structure ─────────────────────────────────────
    @staticmethod
    def _correlation(cov: np.ndarray, sigma: np.ndarray) -> np.ndarray:
        """Corr = D^-1 Σ D^-1 with D = diag(sqrt(diag Σ))."""
        d_inv = np.diag(1.0 / sigma)
        corr = d_inv @ cov @ d_inv
        np.clip(corr, -1.0, 1.0, out=corr)
        return corr

    @staticmethod
    def _correlation_summary(
        corr: np.ndarray, symbols: list[str]
    ) -> tuple[float, float, tuple[str, str] | None]:
        """Average & max pairwise correlation over the upper triangle (off-diagonal)."""
        n = corr.shape[0]
        iu = np.triu_indices(n, k=1)
        offdiag = corr[iu]
        if offdiag.size == 0:
            return 0.0, 0.0, None
        avg = float(offdiag.mean())
        k = int(np.argmax(offdiag))
        max_corr = float(offdiag[k])
        i, j = int(iu[0][k]), int(iu[1][k])
        return avg, max_corr, (symbols[i], symbols[j])

    # ── Metric 2: diversification ratio (Choueifaty & Coignard) ──────────────
    @staticmethod
    def _diversification_ratio(
        w: np.ndarray, sigma: np.ndarray, port_vol: float
    ) -> float:
        """DR = (w·σ) / sqrt(w'Σw). Always >= 1 for a valid covariance."""
        if port_vol <= 0:
            return 1.0
        return float((w @ sigma) / port_vol)

    # ── Metric 3: PCA / principal-portfolio ENB (Meucci) ─────────────────────
    @staticmethod
    def _pca_enb(
        cov: np.ndarray,
        w: np.ndarray,
        symbols: list[str],
        max_members: int = 5,
        cum_threshold: float = 0.9,
    ) -> tuple[float, list[float], list[list[dict]]]:
        """Effective Number of Bets via principal-component decomposition.

        eigvals, eigvecs = eigh(Σ); clip eigvals >= 1e-15
        y = eigvecs.T @ w ; contrib = eigvals * y**2 ; p = contrib / contrib.sum()
        ENB = exp(-Σ p_i ln p_i)

        Also returns, for each principal bet (ordered by descending variance
        contribution), its composition: the holdings whose eigenvector loadings
        define that uncorrelated direction. ``weight`` is the squared loading
        (share of the bet's direction, sums to 1 across all names); ``loading``
        keeps the sign so spread-style bets (long A vs short B) stay visible.
        The eigenvector sign is arbitrary, so it is fixed to make the dominant
        loading positive.

        WARNING — PCA-ENB is *basis-dependent* and reads LOW under eigenvalue
        degeneracy. For 5 truly independent assets (Σ ≈ σ²·I, all eigenvalues
        equal) the eigenbasis is arbitrary, so this returns ~3.7, NOT 5. Treat
        it as an ordering signal, not a ground-truth count.

        TODO(min-torsion): the intended upgrade is minimum-torsion ENB
        (Meucci, Santangelo & Deguest 2015), which is rotation-invariant and
        avoids this degeneracy artifact. DO NOT implement it from memory — a
        naive polar-iteration torsion matrix `t` silently fails to diagonalize
        the factor covariance. Any implementation MUST be validated by checking
        that  t·Σ·t'  is actually diagonal
        (max off-diagonal magnitude / max diagonal magnitude ≈ 0) BEFORE its
        ENB output is trusted.
        """
        eigvals, eigvecs = np.linalg.eigh(cov)
        eigvals = np.clip(eigvals, 1e-15, None)
        y = eigvecs.T @ w
        contrib = eigvals * y**2
        total = contrib.sum()
        if total <= 0:
            return 1.0, [], []
        p = contrib / total
        p_pos = p[p > 0]
        enb = float(np.exp(-np.sum(p_pos * np.log(p_pos))))

        order = np.argsort(p)[::-1]  # bets, most-important variance direction first
        prc = [float(p[k]) for k in order]
        bets = [
            DiversityEngine._bet_composition(eigvecs[:, k], symbols, max_members, cum_threshold)
            for k in order
        ]
        return enb, prc, bets

    @staticmethod
    def _bet_composition(
        vec: np.ndarray,
        symbols: list[str],
        max_members: int,
        cum_threshold: float,
    ) -> list[dict]:
        """Top holdings defining one principal bet (eigenvector), most-dominant first."""
        v = vec.astype(float)
        # Fix arbitrary eigenvector sign: dominant loading is positive.
        if v[int(np.argmax(np.abs(v)))] < 0:
            v = -v
        share = v**2  # sums to 1 across all names
        idx = np.argsort(share)[::-1]

        members: list[dict] = []
        cum = 0.0
        for rank, i in enumerate(idx):
            members.append(
                {
                    "symbol": symbols[int(i)],
                    "loading": round(float(v[i]), 4),
                    "weight": round(float(share[i]), 4),
                }
            )
            cum += float(share[i])
            if rank + 1 >= 2 and (cum >= cum_threshold or rank + 1 >= max_members):
                break
        return members

    # ── Metric 5: weight entropy -> effective number of positions ────────────
    @staticmethod
    def _weight_entropy(w: np.ndarray, n: int) -> tuple[float, float, float]:
        """H = -Σ w_i ln w_i ; effective_positions = exp(H) ; normalized = H/ln(N)."""
        H = float(-np.sum(w * np.log(w)))  # every held weight is > 0
        eff_positions = float(np.exp(H))
        norm_entropy = float(H / math.log(n)) if n > 1 else 0.0
        return H, eff_positions, norm_entropy
