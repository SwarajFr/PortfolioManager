# -------------------------------------------------
# Target Ranges
# -------------------------------------------------
CATEGORY_TARGETS = {
    "INDIAEQUITYETF": (20, 24),
    "METALS": (15, 18),
    "USEQUITY": (15, 18),
    "INDIAEQUITY": (40, 50),
}


def compute_allocation(df):

    total_value = df["value"].sum()

    grouped = (
        df.groupby("category")
        .agg({
            "value": "sum",
            "pnl": "sum",
            "investment": "sum"
        })
        .reset_index()
    )

    grouped["allocation_pct"] = (
        grouped["value"] / total_value * 100
    )

    grouped["pnl_pct"] = (
        grouped["pnl"] / grouped["investment"] * 100
    )

    rows = []

    for _, row in grouped.iterrows():

        lower, upper = CATEGORY_TARGETS.get(
            row["category"], (0, 100)
        )

        if row["allocation_pct"] > upper:
            drift_amount = (
                (row["allocation_pct"] - upper)
                / 100
                * total_value
            )
            action = f"Trim ₹{drift_amount:,.0f}"
            badge = "danger"

        elif row["allocation_pct"] < lower:
            drift_amount = (
                (lower - row["allocation_pct"])
                / 100
                * total_value
            )
            action = f"Add ₹{drift_amount:,.0f}"
            badge = "warning"

        else:
            action = "On Target"
            badge = "success"

        rows.append({
            "category": row["category"],
            "value": row["value"],
            "allocation_pct": row["allocation_pct"],
            "pnl": row["pnl"],
            "pnl_pct": row["pnl_pct"],
            "target": f"{lower}–{upper}%",
            "action": action,
            "badge": badge,
        })

    return rows