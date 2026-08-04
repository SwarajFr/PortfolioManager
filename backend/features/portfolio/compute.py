"""Pure portfolio arithmetic: holdings frame + config in, overview payload out.

No I/O and no settings lookup — `service.py` supplies both — which is what lets
the allocation and concentration rules be tested against a hand-built frame.

The two rule families answer different questions and deliberately do not share
code:

* **Allocation** is about *intent*: each group has a target band, and the action
  is the rupee amount that would bring it back inside that band. A group with no
  configured target is reported, never actioned.
* **Concentration** is about *risk*: top-5 and largest-holding caps are absolute
  ceilings, so they only ever produce TRIM.

Amounts are the distance to the *nearest edge* of the limit, not to its midpoint
— the smallest trade that resolves the breach, since every trade costs.
"""


def _empty_overview():
    """Zeroed payload so an empty portfolio renders an empty state, not a 500."""
    return {
        "health": {
            "total_value": 0,
            "total_pnl": 0,
            "return_pct": 0,
            "capital_at_risk": 0,
        },
        "allocation": [],
        "concentration": [],
    }


def compute_overview(df, config):
    if df is None or df.empty:
        return _empty_overview()

    df = df.copy()
    df["value"] = df["last_price"] * df["quantity"]
    df["invested"] = df["average_price"] * df["quantity"]
    df["pnl"] = df["value"] - df["invested"]

    total_value = df["value"].sum()
    total_invested = df["invested"].sum()
    total_pnl = df["pnl"].sum()
    capital_at_risk = df[df["pnl"] < 0]["value"].sum()

    def classify(symbol):
        for group, symbols in config["groups"].items():
            if symbol in symbols:
                return group
        return "Unassigned"

    df["group"] = df["tradingsymbol"].apply(classify)
    grouped = df.groupby("group").agg({"value": "sum", "invested": "sum", "pnl": "sum"}).reset_index()

    allocation = []
    for _, row in grouped.iterrows():
        group = row["group"]
        value = row["value"]
        invested = row["invested"]
        pnl = row["pnl"]
        allocation_pct = (value / total_value) * 100 if total_value else 0
        pnl_pct = (pnl / invested) * 100 if invested else 0

        target = config["targets"].get(group)
        if target:
            target_min, target_max = target
            if allocation_pct > target_max:
                amount = value - (target_max / 100) * total_value
                action = {"type": "TRIM", "amount": int(amount)}
            elif allocation_pct < target_min:
                amount = (target_min / 100) * total_value - value
                action = {"type": "ADD", "amount": int(amount)}
            else:
                action = {"type": "HOLD", "amount": 0}
            target_label = f"{target_min}-{target_max}%"
        else:
            action = {"type": "HOLD", "amount": 0}
            target_label = "-"

        allocation.append(
            {
                "group": group,
                "value": float(value),
                "allocation_pct": round(allocation_pct, 1),
                "pnl": float(pnl),
                "pnl_pct": round(pnl_pct, 1),
                "target": target_label,
                "action": action,
            }
        )

    df_sorted = df.sort_values("value", ascending=False)
    concentration = []

    if not df_sorted.empty:
        top5 = df_sorted.head(5)
        top5_value = top5["value"].sum()
        top5_pct = (top5_value / total_value) * 100 if total_value else 0
        top5_limit = config["concentration"]["top5"]
        top5_action = (
            {"type": "TRIM", "amount": int(top5_value - (top5_limit / 100) * total_value)}
            if top5_pct > top5_limit
            else {"type": "HOLD", "amount": 0}
        )

        largest = df_sorted.iloc[0]
        largest_pct = (largest["value"] / total_value) * 100 if total_value else 0
        single_limit = config["concentration"]["single"]
        largest_action = (
            {"type": "TRIM", "amount": int(largest["value"] - (single_limit / 100) * total_value)}
            if largest_pct > single_limit
            else {"type": "HOLD", "amount": 0}
        )

        concentration = [
            {
                "metric": "Top 5 Holdings",
                "value": float(top5_value),
                "value_pct": round(top5_pct, 1),
                "pnl": float(top5["pnl"].sum()),
                "limit": f"< {top5_limit}%",
                "action": top5_action,
            },
            {
                "metric": f"Largest Holding - {largest['tradingsymbol']}",
                "value": float(largest["value"]),
                "value_pct": round(largest_pct, 1),
                "pnl": float(largest["pnl"]),
                "limit": f"<= {single_limit}%",
                "action": largest_action,
            },
        ]

    return {
        "health": {
            "total_value": float(total_value),
            "total_pnl": float(total_pnl),
            "return_pct": float((total_pnl / total_invested) * 100) if total_invested else 0,
            "capital_at_risk": float(capital_at_risk),
        },
        "allocation": allocation,
        "concentration": concentration,
    }
