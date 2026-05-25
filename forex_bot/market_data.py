from dataclasses import dataclass
from datetime import timedelta

from forex_bot.models import Candle, Timeframe


TIMEFRAME_DELTAS: dict[Timeframe, timedelta] = {
    Timeframe.M1: timedelta(minutes=1),
    Timeframe.M5: timedelta(minutes=5),
    Timeframe.M15: timedelta(minutes=15),
    Timeframe.M30: timedelta(minutes=30),
    Timeframe.H1: timedelta(hours=1),
    Timeframe.H4: timedelta(hours=4),
    Timeframe.D: timedelta(days=1),
    Timeframe.W: timedelta(weeks=1),
}


@dataclass(frozen=True)
class SwingPoint:
    index: int
    candle: Candle
    kind: str


def sort_candles(candles: list[Candle]) -> list[Candle]:
    return sorted(candles, key=lambda candle: candle.timestamp)


def assert_same_series(candles: list[Candle]) -> None:
    if not candles:
        return
    symbol = candles[0].symbol
    timeframe = candles[0].timeframe
    for candle in candles:
        if candle.symbol != symbol:
            raise ValueError("candles must all have the same symbol")
        if candle.timeframe != timeframe:
            raise ValueError("candles must all have the same timeframe")


def find_missing_candle_ranges(candles: list[Candle]) -> list[tuple[Candle, Candle]]:
    ordered = sort_candles(candles)
    assert_same_series(ordered)
    if len(ordered) < 2:
        return []

    expected_delta = TIMEFRAME_DELTAS.get(ordered[0].timeframe)
    if expected_delta is None:
        return []

    gaps: list[tuple[Candle, Candle]] = []
    for previous, current in zip(ordered, ordered[1:]):
        if current.timestamp - previous.timestamp > expected_delta:
            gaps.append((previous, current))
    return gaps


def detect_swings(candles: list[Candle], window: int = 2, live_safe: bool = True) -> list[SwingPoint]:
    if window < 1:
        raise ValueError("window must be at least 1")

    ordered = sort_candles(candles)
    swings: list[SwingPoint] = []
    last_index = len(ordered) - window if live_safe else len(ordered)

    for index in range(window, last_index):
        candle = ordered[index]
        left = ordered[index - window:index]
        right = ordered[index + 1:index + window + 1]
        if len(right) < window:
            continue

        if all(candle.high > other.high for other in left + right):
            swings.append(SwingPoint(index=index, candle=candle, kind="high"))
        if all(candle.low < other.low for other in left + right):
            swings.append(SwingPoint(index=index, candle=candle, kind="low"))
    return swings

