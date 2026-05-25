from dataclasses import dataclass
from decimal import Decimal

from forex_bot.models import Candle, InstrumentSpec, StrategyDecision


@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    candles: list[Candle]
    instrument: InstrumentSpec
    spread_pips: Decimal


class Strategy:
    name: str

    def evaluate(self, context: StrategyContext) -> StrategyDecision:
        raise NotImplementedError

