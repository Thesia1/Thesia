from datetime import datetime, timezone
from decimal import Decimal
import unittest

from forex_bot.market_data import detect_swings, find_missing_candle_ranges
from forex_bot.models import Candle, Timeframe


class MarketDataTest(unittest.TestCase):
    def test_missing_candle_ranges_detects_gap(self):
        candles = [
            _candle("2026-05-25T09:00:00+00:00", "1.1000", "1.1010", "1.0990", "1.1005"),
            _candle("2026-05-25T11:00:00+00:00", "1.1005", "1.1020", "1.1000", "1.1015"),
        ]

        gaps = find_missing_candle_ranges(candles)

        self.assertEqual(len(gaps), 1)

    def test_detect_swings_uses_live_safe_confirmation(self):
        candles = [
            _candle("2026-05-25T09:00:00+00:00", "1.1000", "1.1010", "1.0990", "1.1005"),
            _candle("2026-05-25T10:00:00+00:00", "1.1005", "1.1030", "1.1000", "1.1020"),
            _candle("2026-05-25T11:00:00+00:00", "1.1020", "1.1025", "1.0980", "1.0990"),
            _candle("2026-05-25T12:00:00+00:00", "1.0990", "1.1000", "1.0970", "1.0985"),
        ]

        swings = detect_swings(candles, window=1, live_safe=True)

        self.assertEqual(len(swings), 1)
        self.assertEqual(swings[0].kind, "high")


def _candle(timestamp: str, open_: str, high: str, low: str, close: str) -> Candle:
    return Candle(
        symbol="EUR_USD",
        timeframe=Timeframe.H1,
        timestamp=datetime.fromisoformat(timestamp).astimezone(timezone.utc),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
    )


if __name__ == "__main__":
    unittest.main()
