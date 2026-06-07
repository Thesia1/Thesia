from collections.abc import Iterable


KNOWN_MARKET_CODES = {
    "AUD",
    "CAD",
    "CHF",
    "EUR",
    "GBP",
    "JPY",
    "NZD",
    "USD",
    "XAG",
    "XAU",
}


DERIV_SYNTHETIC_ALIASES: dict[str, tuple[str, ...]] = {
    "V50_1S": ("Volatility 50 (1s) Index",),
    "VOLATILITY_50_1S": ("Volatility 50 (1s) Index",),
    "VOLATILITY_50_1S_INDEX": ("Volatility 50 (1s) Index",),
    "STEP": ("Step Index",),
    "STEP_INDEX": ("Step Index",),
    "V75": ("Volatility 75 Index",),
    "VOLATILITY_75": ("Volatility 75 Index",),
    "VOLATILITY_75_INDEX": ("Volatility 75 Index",),
    "V75_1S": ("Volatility 75 (1s) Index",),
    "VOLATILITY_75_1S": ("Volatility 75 (1s) Index",),
    "VOLATILITY_75_1S_INDEX": ("Volatility 75 (1s) Index",),
}


def normalize_market_symbol(symbol: str) -> str:
    raw = symbol.strip().replace("/", "_").replace(" ", "_").upper()
    if "_" in raw:
        return raw
    if len(raw) == 6 and raw[:3] in KNOWN_MARKET_CODES and raw[3:] in KNOWN_MARKET_CODES:
        return f"{raw[:3]}_{raw[3:]}"
    return raw


def mt5_symbol_candidates(symbol: str) -> tuple[str, ...]:
    raw = symbol.strip()
    normalized_market = normalize_market_symbol(raw)
    compact = normalized_market.replace("/", "").replace("_", "").upper()
    underscored = raw.replace("/", "_").replace(" ", "_").upper()
    normalized_words = (
        raw.upper()
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
        .replace(" ", "_")
    )
    candidates: list[str] = []
    candidates.extend(DERIV_SYNTHETIC_ALIASES.get(underscored, ()))
    candidates.extend(DERIV_SYNTHETIC_ALIASES.get(normalized_words, ()))
    candidates.extend((compact, normalized_market, raw))
    return _dedupe(candidate for candidate in candidates if candidate)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen = set()
    ordered = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)
