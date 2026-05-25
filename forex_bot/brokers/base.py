from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from forex_bot.models import Candle, InstrumentSpec, Timeframe


class BrokerConfigError(ValueError):
    pass


@dataclass(frozen=True)
class MarketSnapshot:
    candles: list[Candle]
    instrument: InstrumentSpec
    spread_pips: Decimal
    provider: str


class BrokerClient(Protocol):
    def get_market_snapshot(self, symbol: str, granularity: Timeframe = Timeframe.H1, count: int = 200) -> MarketSnapshot:
        raise NotImplementedError

