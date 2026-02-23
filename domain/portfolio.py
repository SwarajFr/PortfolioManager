import pandas as pd

def portfolio_summary(holdings):
    df = pd.DataFrame(holdings)

    df["investment"] = (df["quantity"] * df["average_price"]).round(2)
    df["value"] = (df["quantity"] * df["last_price"]).round(2)
    df["pnl"] = (df["value"] - df["investment"]).round(2)

    total_investment = round(df["investment"].sum(), 2)
    total_value = round(df["value"].sum(), 2)
    total_pnl = round(df["pnl"].sum(), 2)

    return {
        "investment": total_investment,
        "value": total_value,
        "pnl": total_pnl,
        "return_pct": round((total_pnl / total_investment) * 100, 2)
        if total_investment != 0 else 0.0,
        "df": df
    }