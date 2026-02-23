def compute_concentration(df):

    total_value = df["value"].sum()

    df_sorted = df.sort_values("value", ascending=False)

    top5 = df_sorted.head(5)
    top5_value = top5["value"].sum()
    top5_pct = top5_value / total_value * 100
    top5_pnl = top5["pnl"].sum()
    top5_pnl_pct = top5_pnl / top5["investment"].sum() * 100

    largest = df_sorted.iloc[0]
    largest_pct = largest["value"] / total_value * 100

    return {
        "top5_value": top5_value,
        "top5_pct": top5_pct,
        "top5_pnl": top5_pnl,
        "top5_pnl_pct": top5_pnl_pct,
        "top5_action": "Trim" if top5_pct > 35 else "On Target",
        "top5_badge": "danger" if top5_pct > 35 else "success",

        "largest_name": largest["tradingsymbol"],
        "largest_value": largest["value"],
        "largest_pct": largest_pct,
        "largest_pnl": largest["pnl"],
        "largest_pnl_pct": largest["return_pct"],
        "largest_action": "Trim" if largest_pct > 5 else "On Target",
        "largest_badge": "danger" if largest_pct > 5 else "success",
    }