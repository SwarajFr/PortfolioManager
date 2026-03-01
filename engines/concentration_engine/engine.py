from engines.concentration_engine.settings import (
    TOP_N, TOP_N_THRESHOLD, LARGEST_THRESHOLD,
)


def compute_concentration(df):
    total_value = df["value"].sum()
    df_sorted = df.sort_values("value", ascending=False)

    top = df_sorted.head(TOP_N)
    top_value = top["value"].sum()
    top_pct = top_value / total_value * 100
    top_pnl = top["pnl"].sum()
    top_pnl_pct = top_pnl / top["investment"].sum() * 100

    largest = df_sorted.iloc[0]
    largest_pct = largest["value"] / total_value * 100

    return {
        "top5_value": top_value,
        "top5_pct": top_pct,
        "top5_pnl": top_pnl,
        "top5_pnl_pct": top_pnl_pct,
        "top5_action": "Trim" if top_pct > TOP_N_THRESHOLD else "On Target",
        "top5_badge": "danger" if top_pct > TOP_N_THRESHOLD else "success",

        "largest_name": largest["tradingsymbol"],
        "largest_value": largest["value"],
        "largest_pct": largest_pct,
        "largest_pnl": largest["pnl"],
        "largest_pnl_pct": largest["return_pct"],
        "largest_action": "Trim" if largest_pct > LARGEST_THRESHOLD else "On Target",
        "largest_badge": "danger" if largest_pct > LARGEST_THRESHOLD else "success",
    }
