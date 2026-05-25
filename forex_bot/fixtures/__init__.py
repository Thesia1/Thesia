"""Local fixture data used by tests and the development CLI."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from importlib.resources import files

from forex_bot.models import Candle, Timeframe


def load_fixture_candles(name: str) -> list[Candle]:
    path = files("forex_bot.fixtures").joinpath(name)
    rows = json.loads(path.read_text())
    candles: list[Candle] = []
    for row in rows:
        timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).astimezone(timezone.utc)
        candles.append(
            Candle(
                symbol=row["symbol"],
                timeframe=Timeframe(row["timeframe"]),
                timestamp=timestamp,
                open=Decimal(row["open"]),
                high=Decimal(row["high"]),
                low=Decimal(row["low"]),
                close=Decimal(row["close"]),
                volume=Decimal(row.get("volume", "0")),
            )
        )
    return candles
