CATEGORY_MAP = {
    "INDIAEQUITYETF": {
        "BANKBEES", "JUNIORBEES", "NIFTYBEES",
        "CONSUMBEES", "HDFCMID150", "HDFCNEXT50"
    },
    "USEQUITY": {"MON100", "MONQ50"},
    "METALS": {"GOLDBEES", "GOLDCASE", "SILVERBEES"},
}


def classify_category(symbol):
    for category, symbols in CATEGORY_MAP.items():
        if symbol in symbols:
            return category
    return "INDIAEQUITY"  # default fallback
