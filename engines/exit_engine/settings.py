# score thresholds for loss severity (KPI 1, max 25)
LOSS_SEVERITY_TIERS = [
    (0, 0),       # no loss → 0
    (-10, 10),    # up to -10% → 10
    (-20, 18),    # up to -20% → 18
]
LOSS_SEVERITY_MAX = 25  # worse than -20%

# risk vs median ratio thresholds (KPI 2, max 20)
RISK_RATIO_CAP = 2.0
RISK_RATIO_TIERS = [
    (1.0, 0),
    (1.2, 8),
    (1.5, 14),
]
RISK_RATIO_MAX = 20

# risk-adjusted return inefficiency (KPI 3, max 20)
RAR_TIERS = [
    (0, 8),       # positive but below median → 8
    (-1, 14),     # slightly negative → 14
]
RAR_MAX = 20

# trend weakness scores (KPI 4, max 20)
TREND_BELOW_MA50 = 10
TREND_DEATH_CROSS = 20  # below MA50 and MA50 < MA200

# concentration penalty (KPI 5, max 15)
CONCENTRATION_TIERS = [
    (5, 0),
    (8, 5),
    (12, 10),
]
CONCENTRATION_MAX = 15

# action mapping based on total exit score
ACTION_TIERS = [
    (70, "Exit",  "badge-exit"),
    (50, "Trim",  "badge-trim"),
    (30, "Watch", "badge-watch"),
    (0,  "Hold",  "badge-hold"),
]

# minimum vol to include in median calculation (filters out ETFs)
VOL_FLOOR = 0.08

# lookback period for historical data
HISTORY_DAYS = 365
