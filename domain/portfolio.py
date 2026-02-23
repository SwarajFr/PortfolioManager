import pandas as pd


# -------------------------------------------------
# CATEGORY MAP (Your controlled asset taxonomy)
# -------------------------------------------------
CATEGORY_MAP = {
    "INDIAEQUITYETF": {
        "BANKBEES", "JUNIORBEES", "NIFTYBEES",
        "CONSUMBEES", "HDFCMID150", "HDFCNEXT50"
    },
    "USEQUITY": {"MON100", "MONQ50"},
    "METALS": {"GOLDBEES", "GOLDCASE", "SILVERBEES"},
}


# -------------------------------------------------
# Classification Engine
# -------------------------------------------------
def classify_category(symbol):

    for category, symbols in CATEGORY_MAP.items():
        if symbol in symbols:
            return category

    return "INDIAEQUITY"  # default fallback


# -------------------------------------------------
# Build Base DataFrame
# -------------------------------------------------
def build_portfolio_dataframe(holdings):

    df = pd.DataFrame(holdings)

    df["investment"] = df["quantity"] * df["average_price"]
    df["value"] = df["quantity"] * df["last_price"]
    df["pnl"] = df["value"] - df["investment"]

    df["return_pct"] = df["pnl"] / df["investment"] * 100

    # 🔥 Add category column
    df["category"] = df["tradingsymbol"].apply(classify_category)

    return df


# -------------------------------------------------
# Portfolio Health
# -------------------------------------------------
def compute_portfolio_health(df):

    total_value = df["value"].sum()
    total_investment = df["investment"].sum()
    total_pnl = df["pnl"].sum()

    portfolio_return = (
        total_pnl / total_investment * 100
        if total_investment else 0
    )

    capital_at_risk = df[df["pnl"] < 0]["value"].sum()

    return {
        "total_value": total_value,
        "total_pnl": total_pnl,
        "portfolio_return": portfolio_return,
        "capital_at_risk": capital_at_risk,
    }