from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal

from forex_bot.indicators import body_to_range_ratio, candle_body, candle_range, is_bullish
from forex_bot.market_data import sort_candles
from forex_bot.models import (
    Candle,
    Direction,
    RuleEvidence,
    SignalState,
    StrategyDecision,
    TradeCandidate,
    Zone,
    ZoneType,
)
from forex_bot.strategy import Strategy, StrategyContext


@dataclass(frozen=True)
class FreshStrongZoneConfig:
    max_base_body_to_range: Decimal = Decimal("0.35")
    min_departure_body_multiple: Decimal = Decimal("2")
    stop_buffer_pips: Decimal = Decimal("5")
    min_reward_to_risk: Decimal = Decimal("2")


class FreshStrongZoneContinuation(Strategy):
    name = "fresh_strong_zone_continuation"

    def __init__(self, config: FreshStrongZoneConfig | None = None) -> None:
        self.config = config or FreshStrongZoneConfig()

    def evaluate(self, context: StrategyContext) -> StrategyDecision:
        candles = sort_candles(context.candles)
        evidence: list[RuleEvidence] = []

        if len(candles) < 6:
            return self._decision(context, SignalState.NO_TRADE, evidence + [
                RuleEvidence("enough_candles", False, "At least 6 candles are required.")
            ])

        setup = self._find_latest_bullish_setup(candles)
        if setup is None:
            return self._decision(context, SignalState.NO_TRADE, evidence + [
                RuleEvidence("fresh_strong_demand_zone", False, "No valid base plus bullish departure was found.")
            ])

        base_index, departure_index, zone = setup
        latest = candles[-1]
        departure = candles[departure_index]

        evidence.append(RuleEvidence("base_candle", True, f"Base candle found at {candles[base_index].timestamp.isoformat()}."))
        evidence.append(RuleEvidence("departure_candle", True, f"Bullish departure closed at {departure.close}."))

        removed_opposite = self._removed_prior_high(candles, base_index, departure_index)
        evidence.append(RuleEvidence(
            "opposite_zone_removed",
            removed_opposite,
            "Departure closed above prior structure high." if removed_opposite else "Departure did not close above prior structure high.",
        ))
        if not removed_opposite:
            return self._decision(context, SignalState.NO_TRADE, evidence)

        returned_to_zone = latest.low <= zone.high and latest.close >= zone.low
        evidence.append(RuleEvidence(
            "return_to_zone",
            returned_to_zone,
            f"Latest candle low={latest.low}, zone={zone.low}-{zone.high}.",
        ))
        if not returned_to_zone:
            return self._decision(context, SignalState.WATCH, evidence)

        confirmed = is_bullish(latest) and latest.close > zone.high
        evidence.append(RuleEvidence(
            "candle_close_confirmation",
            confirmed,
            "Latest candle closed bullish above the demand zone." if confirmed else "Latest candle has not confirmed above the zone.",
        ))
        if not confirmed:
            return self._decision(context, SignalState.WATCH, evidence)

        entry = latest.close
        stop = zone.low - (self.config.stop_buffer_pips * context.instrument.pip_size)
        risk = entry - stop
        target = entry + (risk * self.config.min_reward_to_risk)
        decision_id = self._decision_id(context.symbol, latest)

        candidate = TradeCandidate(
            symbol=context.symbol,
            direction=Direction.BUY,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            spread_pips=context.spread_pips,
            setup_name=self.name,
            strategy_decision_id=decision_id,
        )
        return self._decision(context, SignalState.TRADE_CANDIDATE, evidence, candidate, decision_id)

    def _find_latest_bullish_setup(self, candles: list[Candle]) -> tuple[int, int, Zone] | None:
        for index in range(len(candles) - 3, 1, -1):
            base = candles[index]
            departure = candles[index + 1]
            if not self._is_base(base):
                continue
            if not self._is_bullish_departure(base, departure):
                continue

            zone = Zone(
                id=f"demand:{base.symbol}:{base.timeframe.value}:{base.timestamp.isoformat()}",
                symbol=base.symbol,
                timeframe=base.timeframe,
                zone_type=ZoneType.DEMAND,
                high=base.high,
                low=base.low,
                created_at=departure.timestamp,
                source_start=base.timestamp,
                source_end=base.timestamp,
            )
            return index, index + 1, zone
        return None

    def _is_base(self, candle: Candle) -> bool:
        return candle_range(candle) > 0 and body_to_range_ratio(candle) <= self.config.max_base_body_to_range

    def _is_bullish_departure(self, base: Candle, departure: Candle) -> bool:
        return (
            is_bullish(departure)
            and candle_body(departure) >= candle_body(base) * self.config.min_departure_body_multiple
            and departure.close > base.high
        )

    def _removed_prior_high(self, candles: list[Candle], base_index: int, departure_index: int) -> bool:
        prior_high = max(candle.high for candle in candles[:base_index])
        return candles[departure_index].close > prior_high

    def _decision(
        self,
        context: StrategyContext,
        state: SignalState,
        evidence: list[RuleEvidence],
        candidate: TradeCandidate | None = None,
        decision_id: str | None = None,
    ) -> StrategyDecision:
        latest_timestamp = sort_candles(context.candles)[-1].timestamp if context.candles else None
        created_at = latest_timestamp or __import__("datetime").datetime.now(timezone.utc)
        return StrategyDecision(
            id=decision_id or f"{self.name}:{context.symbol}:{created_at.isoformat()}",
            symbol=context.symbol,
            state=state,
            setup_name=self.name,
            created_at=created_at,
            evidence=tuple(evidence),
            candidate=candidate,
        )

    def _decision_id(self, symbol: str, candle: Candle) -> str:
        return f"{self.name}:{symbol}:{candle.timestamp.isoformat()}"

