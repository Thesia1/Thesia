from collections.abc import Iterable


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


def mt5_symbol_candidates(symbol: str) -> tuple[str, ...]:
    raw = symbol.strip()
    compact = raw.replace("/", "").replace("_", "").upper()
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
    candidates.extend((compact, raw))
    return _dedupe(candidate for candidate in candidates if candidate)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen = set()
    ordered = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)
