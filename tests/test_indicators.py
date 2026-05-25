from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from forex_bot.indicators import atr, body_to_range_ratio, true_range
from forex_bot.models import Candle, Timeframe


class IndicatorsTest(unittest.TestCase):
    def test_true_range_uses_previous_close_gap(self):
        previous = _candle(0, "1.1000", "1.1010", "1.0990", "1.1000")
        current = _candle(1, "1.1040", "1.1050", "1.1030", "1.1045")

        self.assertEqual(true_range(current, previous), Decimal("0.0050"))

    def test_atr_returns_rolling_average(self):
        candles = [
            _candle(0, "1.1000", "1.1010", "1.0990", "1.1000"),
            _candle(1, "1.1000", "1.1020", "1.0990", "1.1010"),
            _candle(2, "1.1010", "1.1030", "1.1000", "1.1020"),
        ]

        self.assertEqual(atr(candles, period=2)[-1], Decimal("0.0030"))

    def test_body_to_range_ratio(self):
        candle = _candle(0, "1.1000", "1.1020", "1.0980", "1.1010")

        self.assertEqual(body_to_range_ratio(candle), Decimal("0.25"))


def _candle(offset: int, open_: str, high: str, low: str, close: str) -> Candle:
    return Candle(
        symbol="EUR_USD",
        timeframe=Timeframe.H1,
        timestamp=datetime(2026, 5, 25, tzinfo=timezone.utc) + timedelta(hours=offset),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
    )


if __name__ == "__main__":
    unittest.main()

