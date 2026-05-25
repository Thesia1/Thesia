from decimal import Decimal

from forex_bot.models import Candle


def candle_range(candle: Candle) -> Decimal:
    return candle.high - candle.low


def candle_body(candle: Candle) -> Decimal:
    return abs(candle.close - candle.open)


def upper_wick(candle: Candle) -> Decimal:
    return candle.high - max(candle.open, candle.close)


def lower_wick(candle: Candle) -> Decimal:
    return min(candle.open, candle.close) - candle.low


def body_to_range_ratio(candle: Candle) -> Decimal:
    range_value = candle_range(candle)
    if range_value == 0:
        return Decimal("0")
    return candle_body(candle) / range_value


def is_bullish(candle: Candle) -> bool:
    return candle.close > candle.open


def is_bearish(candle: Candle) -> bool:
    return candle.close < candle.open


def true_range(current: Candle, previous: Candle | None = None) -> Decimal:
    if previous is None:
        return candle_range(current)

    return max(
        current.high - current.low,
        abs(current.high - previous.close),
        abs(current.low - previous.close),
    )


def atr(candles: list[Candle], period: int = 14) -> list[Decimal]:
    if period < 1:
        raise ValueError("period must be at least 1")
    if not candles:
        return []

    values: list[Decimal] = []
    ranges: list[Decimal] = []
    previous: Candle | None = None

    for candle in candles:
        ranges.append(true_range(candle, previous))
        previous = candle
        if len(ranges) < period:
            values.append(Decimal("0"))
        else:
            window = ranges[-period:]
            values.append(sum(window) / Decimal(period))
    return values
