from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal

from forex_bot.indicators import body_to_range_ratio, candle_body, candle_range, is_bearish, is_bullish
from forex_bot.market_data import SwingPoint, detect_swings, sort_candles
from forex_bot.models import (
    Candle,
    Direction,
    RuleEvidence,
    SignalState,
    StrategyDecision,
    Timeframe,
    TradeCandidate,
    Zone,
    ZoneType,
)
from forex_bot.strategy import Strategy, StrategyContext


@dataclass(frozen=True)
class TrendlineZoneSequenceConfig:
    max_base_body_to_range: Decimal = Decimal("0.35")
    min_departure_body_multiple: Decimal = Decimal("2")
    trendline_proximity_pips: Decimal = Decimal("10")
    stop_buffer_pips: Decimal = Decimal("5")
    min_reward_to_risk: Decimal = Decimal("2")


@dataclass(frozen=True)
class SequenceMatch:
    zone: Zone
    direction: Direction
    trendline_value_at_zone: Decimal
    trendline_value_at_latest: Decimal
    swing_a: SwingPoint
    swing_b: SwingPoint


class TrendlineZoneSequence(Strategy):
    name = "trendline_zone_sequence"

    def __init__(self, config: TrendlineZoneSequenceConfig | None = None) -> None:
        self.config = config or TrendlineZoneSequenceConfig()

    def evaluate(self, context: StrategyContext) -> StrategyDecision:
        candles = sort_candles(context.candles)
        evidence: list[RuleEvidence] = []
        if len(candles) < 8:
            return self._decision(context, SignalState.NO_TRADE, evidence + [
                RuleEvidence("enough_candles", False, "At least 8 candles are required for trendline-zone sequence.")
            ])

        match = self._find_sequence_match(context, candles)
        if match is None:
            return self._decision(context, SignalState.NO_TRADE, evidence + [
                RuleEvidence("trendline_zone_sequence", False, "No first-touch zone near a valid sequence trendline was found.")
            ])

        direction = match.direction
        zone = match.zone
        latest = candles[-1]
        evidence.append(RuleEvidence(
            "trendline_sequence",
            True,
            self._trendline_detail(match),
        ))

        mtf_alignment = self._multi_timeframe_confirms(context, direction)
        if mtf_alignment is not None:
            evidence.append(mtf_alignment)
            if not mtf_alignment.passed:
                return self._decision(context, SignalState.NO_TRADE, evidence)

        first_touch = self._is_first_touch(candles, zone)
        evidence.append(RuleEvidence(
            "first_touch_zone",
            first_touch,
            "Zone is untested before the current return." if first_touch else "Zone was already touched before the current return.",
        ))
        if not first_touch:
            return self._decision(context, SignalState.NO_TRADE, evidence)

        returned = self._returned_to_zone(latest, zone, direction)
        evidence.append(RuleEvidence(
            "instant_touch_entry",
            returned,
            self._return_detail(latest, zone, direction),
        ))
        if not returned:
            return self._decision(context, SignalState.WATCH, evidence)

        entry = latest.close
        buffer = self.config.stop_buffer_pips * context.instrument.pip_size
        if direction == Direction.BUY:
            swing_stop = match.swing_b.candle.low
            stop = min(zone.low, swing_stop) - buffer
            risk = entry - stop
            target = entry + (risk * self.config.min_reward_to_risk)
        else:
            swing_stop = match.swing_b.candle.high
            stop = max(zone.high, swing_stop) + buffer
            risk = stop - entry
            target = entry - (risk * self.config.min_reward_to_risk)

        if risk <= 0:
            evidence.append(RuleEvidence("valid_risk_geometry", False, "Entry and stop produce non-positive risk."))
            return self._decision(context, SignalState.NO_TRADE, evidence)

        evidence.append(RuleEvidence(
            "target_selection",
            True,
            f"Using fixed {self.config.min_reward_to_risk}R target={target} for first executable sequence version.",
        ))
        decision_id = self._decision_id(context.symbol, latest)
        candidate = TradeCandidate(
            symbol=context.symbol,
            direction=direction,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            spread_pips=context.spread_pips,
            setup_name=self.name,
            strategy_decision_id=decision_id,
        )
        return self._decision(context, SignalState.TRADE_CANDIDATE, evidence, candidate, decision_id)

    def _find_sequence_match(self, context: StrategyContext, candles: list[Candle]) -> SequenceMatch | None:
        buy_match = self._find_direction_match(context, candles, Direction.BUY)
        sell_match = self._find_direction_match(context, candles, Direction.SELL)
        if buy_match is None:
            return sell_match
        if sell_match is None:
            return buy_match
        return buy_match if buy_match.zone.created_at >= sell_match.zone.created_at else sell_match

    def _find_direction_match(self, context: StrategyContext, candles: list[Candle], direction: Direction) -> SequenceMatch | None:
        swings = detect_swings(candles[:-1], window=1)
        kind = "low" if direction == Direction.BUY else "high"
        sequence = [swing for swing in swings if swing.kind == kind]
        if len(sequence) < 2:
            return None
        swing_a, swing_b = sequence[-2], sequence[-1]
        if direction == Direction.BUY and swing_b.candle.low <= swing_a.candle.low:
            return None
        if direction == Direction.SELL and swing_b.candle.high >= swing_a.candle.high:
            return None

        latest_index = len(candles) - 1
        latest_line = self._line_value(swing_a, swing_b, latest_index, direction)
        tolerance = self.config.trendline_proximity_pips * context.instrument.pip_size
        latest = candles[-1]
        if direction == Direction.BUY and latest.close < latest_line - tolerance:
            return None
        if direction == Direction.SELL and latest.close > latest_line + tolerance:
            return None

        zone_type = ZoneType.DEMAND if direction == Direction.BUY else ZoneType.SUPPLY
        zones = [
            zone
            for zone in self._detect_zones(candles[:-1])
            if zone.zone_type == zone_type and self._returned_to_zone(latest, zone, direction)
        ]
        for zone in sorted(zones, key=lambda item: item.created_at, reverse=True):
            source_index = self._zone_source_index(candles, zone)
            if source_index is None:
                continue
            line_at_zone = self._line_value(swing_a, swing_b, source_index, direction)
            if self._zone_near_trendline(zone, latest_line, tolerance, direction):
                return SequenceMatch(
                    zone=zone,
                    direction=direction,
                    trendline_value_at_zone=line_at_zone,
                    trendline_value_at_latest=latest_line,
                    swing_a=swing_a,
                    swing_b=swing_b,
                )
        return None

    def _line_value(self, swing_a: SwingPoint, swing_b: SwingPoint, index: int, direction: Direction) -> Decimal:
        first = swing_a.candle.low if direction == Direction.BUY else swing_a.candle.high
        second = swing_b.candle.low if direction == Direction.BUY else swing_b.candle.high
        slope = (second - first) / Decimal(swing_b.index - swing_a.index)
        return first + (slope * Decimal(index - swing_a.index))

    def _zone_near_trendline(self, zone: Zone, line_value: Decimal, tolerance: Decimal, direction: Direction) -> bool:
        if direction == Direction.BUY:
            return zone.low - tolerance <= line_value <= zone.high + tolerance
        return zone.low - tolerance <= line_value <= zone.high + tolerance

    def _is_first_touch(self, candles: list[Candle], zone: Zone) -> bool:
        source_index = self._zone_source_index(candles, zone)
        if source_index is None:
            return False
        for candle in candles[source_index + 2:-1]:
            if self._touches_zone(candle, zone):
                return False
            if self._zone_invalidated(candle, zone):
                return False
        return True

    def _returned_to_zone(self, latest: Candle, zone: Zone, direction: Direction) -> bool:
        if direction == Direction.BUY:
            return latest.low <= zone.high and latest.close >= zone.low
        return latest.high >= zone.low and latest.close <= zone.high

    def _detect_zones(self, candles: list[Candle]) -> list[Zone]:
        zones: list[Zone] = []
        for index in range(0, len(candles) - 1):
            base = candles[index]
            departure = candles[index + 1]
            if not self._is_base(base):
                continue
            zone_type = None
            if self._is_bullish_departure(base, departure):
                zone_type = ZoneType.DEMAND
            elif self._is_bearish_departure(base, departure):
                zone_type = ZoneType.SUPPLY
            if zone_type is None:
                continue
            zones.append(
                Zone(
                    id=f"{zone_type.value.lower()}:{base.symbol}:{base.timeframe.value}:{base.timestamp.isoformat()}",
                    symbol=base.symbol,
                    timeframe=base.timeframe,
                    zone_type=zone_type,
                    high=base.high,
                    low=base.low,
                    created_at=departure.timestamp,
                    source_start=base.timestamp,
                    source_end=base.timestamp,
                )
            )
        return zones

    def _is_base(self, candle: Candle) -> bool:
        return candle_range(candle) > 0 and body_to_range_ratio(candle) <= self.config.max_base_body_to_range

    def _is_bullish_departure(self, base: Candle, departure: Candle) -> bool:
        return (
            is_bullish(departure)
            and candle_body(departure) >= candle_body(base) * self.config.min_departure_body_multiple
            and departure.close > base.high
        )

    def _is_bearish_departure(self, base: Candle, departure: Candle) -> bool:
        return (
            is_bearish(departure)
            and candle_body(departure) >= candle_body(base) * self.config.min_departure_body_multiple
            and departure.close < base.low
        )

    def _touches_zone(self, candle: Candle, zone: Zone) -> bool:
        return candle.low <= zone.high and candle.high >= zone.low

    def _zone_invalidated(self, candle: Candle, zone: Zone) -> bool:
        if zone.zone_type == ZoneType.DEMAND:
            return candle.close < zone.low
        return candle.close > zone.high

    def _zone_source_index(self, candles: list[Candle], zone: Zone) -> int | None:
        for index, candle in enumerate(candles):
            if candle.timestamp == zone.source_start and candle.timeframe == zone.timeframe:
                return index
        return None

    def _multi_timeframe_confirms(self, context: StrategyContext, direction: Direction) -> RuleEvidence | None:
        groups = (
            (Timeframe.D, context.daily_candles),
            (Timeframe.H4, context.higher_timeframe_candles),
        )
        if not any(candles for _, candles in groups):
            return None
        details: list[str] = []
        confirmed_all = True
        for timeframe, raw_candles in groups:
            if not raw_candles:
                continue
            candles = sort_candles(raw_candles)
            if len(candles) < 2:
                details.append(f"{timeframe.value}:missing_or_insufficient")
                confirmed_all = False
                continue
            previous = candles[-2]
            latest = candles[-1]
            confirmed = latest.close > previous.close if direction == Direction.BUY else latest.close < previous.close
            details.append(f"{timeframe.value}:{'aligned' if confirmed else 'opposed'} latest={latest.close} previous={previous.close}")
            confirmed_all = confirmed_all and confirmed
        desired = "bullish" if direction == Direction.BUY else "bearish"
        return RuleEvidence(
            "sequence_multi_timeframe_alignment",
            confirmed_all,
            f"Available higher-timeframe sequence context requires {desired} alignment; {'; '.join(details)}.",
        )

    def _trendline_detail(self, match: SequenceMatch) -> str:
        if match.direction == Direction.BUY:
            return (
                "Demand in sequence above ascending trendline; "
                f"swing lows at {match.swing_a.candle.low} then {match.swing_b.candle.low}; "
                f"line_at_zone={match.trendline_value_at_zone}, line_at_latest={match.trendline_value_at_latest}."
            )
        return (
            "Supply in sequence below descending trendline; "
            f"swing highs at {match.swing_a.candle.high} then {match.swing_b.candle.high}; "
            f"line_at_zone={match.trendline_value_at_zone}, line_at_latest={match.trendline_value_at_latest}."
        )

    def _return_detail(self, latest: Candle, zone: Zone, direction: Direction) -> str:
        if direction == Direction.BUY:
            return f"Latest candle touched demand zone={zone.low}-{zone.high}; low={latest.low}, close={latest.close}."
        return f"Latest candle touched supply zone={zone.low}-{zone.high}; high={latest.high}, close={latest.close}."

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
