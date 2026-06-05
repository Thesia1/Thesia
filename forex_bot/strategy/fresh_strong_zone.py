from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal

from forex_bot.indicators import body_to_range_ratio, candle_body, candle_range, is_bearish, is_bullish
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
    Timeframe,
)
from forex_bot.strategy import Strategy, StrategyContext


@dataclass(frozen=True)
class FreshStrongZoneConfig:
    max_base_body_to_range: Decimal = Decimal("0.35")
    min_departure_body_multiple: Decimal = Decimal("2")
    stop_buffer_pips: Decimal = Decimal("5")
    min_reward_to_risk: Decimal = Decimal("2")
    max_prior_retests: int = 0
    curve_tradeable_percent: Decimal = Decimal("0.25")


@dataclass(frozen=True)
class ZoneLifecycle:
    prior_retest_count: int
    invalidated: bool
    invalidated_at: str = ""


@dataclass(frozen=True)
class CurveLocation:
    location: str
    position: Decimal
    high: Decimal
    low: Decimal


@dataclass(frozen=True)
class SetupMatch:
    base_index: int
    departure_index: int
    zone: Zone


@dataclass(frozen=True)
class MultiTimeframeAlignment:
    confirmed: bool
    detail: str


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

        setup = self._find_latest_setup(candles)
        if setup is None:
            return self._decision(context, SignalState.NO_TRADE, evidence + [
                RuleEvidence("fresh_strong_zone", False, "No valid base plus strong departure was found.")
            ])

        base_index = setup.base_index
        departure_index = setup.departure_index
        zone = setup.zone
        latest = candles[-1]
        departure = candles[departure_index]
        direction = Direction.BUY if zone.zone_type == ZoneType.DEMAND else Direction.SELL

        evidence.append(RuleEvidence("base_candle", True, f"Base candle found at {candles[base_index].timestamp.isoformat()}."))
        departure_label = "Bullish" if direction == Direction.BUY else "Bearish"
        evidence.append(RuleEvidence("departure_candle", True, f"{departure_label} departure closed at {departure.close}."))

        removed_opposite, opposite_zone = self._removed_opposite_zone(candles, base_index, departure_index, direction)
        evidence.append(RuleEvidence(
            "opposite_zone_removed",
            removed_opposite,
            self._opposite_removal_detail(departure.close, opposite_zone, direction, removed_opposite),
        ))
        if not removed_opposite:
            return self._decision(context, SignalState.NO_TRADE, evidence)

        lifecycle = self._zone_lifecycle(candles, departure_index, zone)
        lifecycle_ok = not lifecycle.invalidated and lifecycle.prior_retest_count <= self.config.max_prior_retests
        evidence.append(RuleEvidence(
            "zone_freshness",
            lifecycle_ok,
            self._zone_lifecycle_detail(lifecycle),
        ))
        if not lifecycle_ok:
            return self._decision(context, SignalState.NO_TRADE, evidence)

        htf_confirmed = self._higher_timeframe_confirms(context, direction)
        if htf_confirmed is not None:
            evidence.append(RuleEvidence(
                "higher_timeframe_confirmation",
                htf_confirmed,
                "Higher-timeframe direction confirms the setup." if htf_confirmed else "Higher-timeframe direction does not confirm the setup.",
            ))
            if not htf_confirmed:
                return self._decision(context, SignalState.NO_TRADE, evidence)

        mtf_alignment = self._multi_timeframe_confirms(context, direction)
        if mtf_alignment is not None:
            evidence.append(RuleEvidence(
                "monthly_weekly_daily_alignment",
                mtf_alignment.confirmed,
                mtf_alignment.detail,
            ))
            if not mtf_alignment.confirmed:
                return self._decision(context, SignalState.NO_TRADE, evidence)

        curve = self._curve_location(context, candles)
        if curve is not None:
            curve_ok = self._curve_confirms(curve, direction)
            evidence.append(RuleEvidence(
                "curve_location",
                curve_ok,
                self._curve_detail(curve, direction),
            ))
            if not curve_ok:
                return self._decision(context, SignalState.NO_TRADE, evidence)

        returned_to_zone = self._returned_to_zone(latest, zone, direction)
        evidence.append(RuleEvidence(
            "return_to_zone",
            returned_to_zone,
            self._return_to_zone_detail(latest, zone, direction),
        ))
        if not returned_to_zone:
            return self._decision(context, SignalState.WATCH, evidence)

        confirmed = self._confirmed_close(latest, zone, direction)
        evidence.append(RuleEvidence(
            "candle_close_confirmation",
            confirmed,
            self._confirmation_detail(direction, confirmed),
        ))
        if not confirmed:
            return self._decision(context, SignalState.WATCH, evidence)

        entry = latest.close
        buffer = self.config.stop_buffer_pips * context.instrument.pip_size
        opposing_target = self._nearest_opposing_zone_target(context, candles, entry, direction)
        if direction == Direction.BUY:
            stop = zone.low - buffer
            risk = entry - stop
            fixed_target = entry + (risk * self.config.min_reward_to_risk)
            target = opposing_target if opposing_target is not None and opposing_target > fixed_target else fixed_target
        else:
            stop = zone.high + buffer
            risk = stop - entry
            fixed_target = entry - (risk * self.config.min_reward_to_risk)
            target = opposing_target if opposing_target is not None and opposing_target < fixed_target else fixed_target
        evidence.append(RuleEvidence(
            "target_selection",
            True,
            self._target_detail(target, fixed_target, opposing_target, direction),
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

    def _find_latest_setup(self, candles: list[Candle]) -> SetupMatch | None:
        bullish = self._find_latest_bullish_setup(candles)
        bearish = self._find_latest_bearish_setup(candles)
        if bullish is None:
            return bearish
        if bearish is None:
            return bullish
        return bullish if candles[bullish.departure_index].timestamp >= candles[bearish.departure_index].timestamp else bearish

    def _find_latest_bullish_setup(self, candles: list[Candle]) -> SetupMatch | None:
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
            return SetupMatch(index, index + 1, zone)
        return None

    def _find_latest_bearish_setup(self, candles: list[Candle]) -> SetupMatch | None:
        for index in range(len(candles) - 3, 1, -1):
            base = candles[index]
            departure = candles[index + 1]
            if not self._is_base(base):
                continue
            if not self._is_bearish_departure(base, departure):
                continue

            zone = Zone(
                id=f"supply:{base.symbol}:{base.timeframe.value}:{base.timestamp.isoformat()}",
                symbol=base.symbol,
                timeframe=base.timeframe,
                zone_type=ZoneType.SUPPLY,
                high=base.high,
                low=base.low,
                created_at=departure.timestamp,
                source_start=base.timestamp,
                source_end=base.timestamp,
            )
            return SetupMatch(index, index + 1, zone)
        return None

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

    def _removed_opposite_zone(
        self,
        candles: list[Candle],
        base_index: int,
        departure_index: int,
        direction: Direction,
    ) -> tuple[bool, Zone | None]:
        opposite_type = ZoneType.SUPPLY if direction == Direction.BUY else ZoneType.DEMAND
        zones = [
            zone
            for zone in self._detect_zones(candles[:base_index])
            if zone.zone_type == opposite_type and self._zone_is_active_until(candles, zone, departure_index)
        ]
        if not zones:
            return False, None

        latest_zone = max(zones, key=lambda zone: zone.created_at)
        departure = candles[departure_index]
        if direction == Direction.BUY:
            return departure.close > latest_zone.high, latest_zone
        return departure.close < latest_zone.low, latest_zone

    def _higher_timeframe_confirms(self, context: StrategyContext, direction: Direction) -> bool | None:
        if not context.higher_timeframe_candles:
            return None
        candles = sort_candles(context.higher_timeframe_candles)
        if len(candles) < 2:
            return False
        previous = candles[-2]
        latest = candles[-1]
        if direction == Direction.BUY:
            return latest.close > previous.close
        return latest.close < previous.close

    def _multi_timeframe_confirms(self, context: StrategyContext, direction: Direction) -> MultiTimeframeAlignment | None:
        groups = (
            (Timeframe.M, context.monthly_candles),
            (Timeframe.W, context.weekly_candles),
            (Timeframe.D, context.daily_candles),
        )
        if not any(candles for _, candles in groups):
            return None

        details: list[str] = []
        all_confirmed = True
        for timeframe, raw_candles in groups:
            candles = sort_candles(raw_candles or [])
            if len(candles) < 2:
                details.append(f"{timeframe.value}:missing_or_insufficient")
                all_confirmed = False
                continue
            previous = candles[-2]
            latest = candles[-1]
            confirmed = latest.close > previous.close if direction == Direction.BUY else latest.close < previous.close
            status = "aligned" if confirmed else "opposed"
            details.append(f"{timeframe.value}:{status} latest={latest.close} previous={previous.close}")
            all_confirmed = all_confirmed and confirmed

        desired = "rising closes" if direction == Direction.BUY else "falling closes"
        return MultiTimeframeAlignment(
            confirmed=all_confirmed,
            detail=f"Monthly/weekly/daily context requires {desired}; {'; '.join(details)}.",
        )

    def _zone_lifecycle(self, candles: list[Candle], departure_index: int, zone: Zone) -> ZoneLifecycle:
        retests = 0
        for candle in candles[departure_index + 1:-1]:
            if self._zone_invalidated(candle, zone):
                return ZoneLifecycle(
                    prior_retest_count=retests,
                    invalidated=True,
                    invalidated_at=candle.timestamp.isoformat(),
                )
            if self._touches_zone(candle, zone):
                retests += 1
        return ZoneLifecycle(prior_retest_count=retests, invalidated=False)

    def _zone_invalidated(self, candle: Candle, zone: Zone) -> bool:
        if zone.zone_type == ZoneType.DEMAND:
            return candle.close < zone.low
        return candle.close > zone.high

    def _zone_is_active_until(self, candles: list[Candle], zone: Zone, exclusive_end_index: int) -> bool:
        source_index = self._zone_source_index(candles, zone)
        if source_index is None:
            return False
        for candle in candles[source_index + 2:exclusive_end_index]:
            if self._zone_invalidated(candle, zone):
                return False
        return True

    def _zone_source_index(self, candles: list[Candle], zone: Zone) -> int | None:
        for index, candle in enumerate(candles):
            if candle.timestamp == zone.source_start and candle.timeframe == zone.timeframe:
                return index
        return None

    def _touches_zone(self, candle: Candle, zone: Zone) -> bool:
        return candle.low <= zone.high and candle.high >= zone.low

    def _curve_location(self, context: StrategyContext, candles: list[Candle]) -> CurveLocation | None:
        if not context.higher_timeframe_candles:
            return None
        curve_candles = sort_candles(context.higher_timeframe_candles)
        if len(curve_candles) < 3:
            return None
        high = max(candle.high for candle in curve_candles)
        low = min(candle.low for candle in curve_candles)
        if high <= low:
            return None
        latest_close = curve_candles[-1].close
        position = (latest_close - low) / (high - low)
        if position <= self.config.curve_tradeable_percent:
            location = "LOW_CURVE"
        elif position >= Decimal("1") - self.config.curve_tradeable_percent:
            location = "HIGH_CURVE"
        else:
            location = "MIDDLE_CURVE"
        return CurveLocation(location=location, position=position, high=high, low=low)

    def _curve_confirms(self, curve: CurveLocation, direction: Direction) -> bool:
        if direction == Direction.BUY:
            return curve.location == "LOW_CURVE"
        return curve.location == "HIGH_CURVE"

    def _returned_to_zone(self, latest: Candle, zone: Zone, direction: Direction) -> bool:
        if direction == Direction.BUY:
            return latest.low <= zone.high and latest.close >= zone.low
        return latest.high >= zone.low and latest.close <= zone.high

    def _confirmed_close(self, latest: Candle, zone: Zone, direction: Direction) -> bool:
        if direction == Direction.BUY:
            return is_bullish(latest) and latest.close > zone.high
        return is_bearish(latest) and latest.close < zone.low

    def _nearest_opposing_zone_target(
        self,
        context: StrategyContext,
        candles: list[Candle],
        entry: Decimal,
        direction: Direction,
    ) -> Decimal | None:
        target_candles = sort_candles(context.higher_timeframe_candles or candles)
        zones = self._detect_zones(target_candles[:-1])
        if direction == Direction.BUY:
            prices = [zone.low for zone in zones if zone.zone_type == ZoneType.SUPPLY and zone.low > entry]
            return min(prices) if prices else None
        prices = [zone.high for zone in zones if zone.zone_type == ZoneType.DEMAND and zone.high < entry]
        return max(prices) if prices else None

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

    def _opposite_removal_detail(
        self,
        departure_close: Decimal,
        opposite_zone: Zone | None,
        direction: Direction,
        removed: bool,
    ) -> str:
        if opposite_zone is None:
            label = "supply" if direction == Direction.BUY else "demand"
            return f"No active prior opposing {label} zone object was found."
        if direction == Direction.BUY:
            result = "above" if removed else "not above"
            return f"Departure close={departure_close} is {result} active opposing supply zone high={opposite_zone.high} ({opposite_zone.id})."
        result = "below" if removed else "not below"
        return f"Departure close={departure_close} is {result} active opposing demand zone low={opposite_zone.low} ({opposite_zone.id})."

    def _return_to_zone_detail(self, latest: Candle, zone: Zone, direction: Direction) -> str:
        if direction == Direction.BUY:
            return f"Latest candle low={latest.low}, close={latest.close}, demand zone={zone.low}-{zone.high}."
        return f"Latest candle high={latest.high}, close={latest.close}, supply zone={zone.low}-{zone.high}."

    def _zone_lifecycle_detail(self, lifecycle: ZoneLifecycle) -> str:
        if lifecycle.invalidated:
            return f"Zone invalidated before confirmation at {lifecycle.invalidated_at}; prior retests={lifecycle.prior_retest_count}."
        return f"Zone fresh before current return; prior retests={lifecycle.prior_retest_count}."

    def _curve_detail(self, curve: CurveLocation, direction: Direction) -> str:
        desired = "LOW_CURVE" if direction == Direction.BUY else "HIGH_CURVE"
        return (
            f"Curve location={curve.location}, desired={desired}, "
            f"position={curve.position:.4f}, range={curve.low}-{curve.high}."
        )

    def _confirmation_detail(self, direction: Direction, confirmed: bool) -> str:
        if direction == Direction.BUY:
            return "Latest candle closed bullish above the demand zone." if confirmed else "Latest candle has not confirmed above the demand zone."
        return "Latest candle closed bearish below the supply zone." if confirmed else "Latest candle has not confirmed below the supply zone."

    def _target_detail(
        self,
        target: Decimal,
        fixed_target: Decimal,
        opposing_target: Decimal | None,
        direction: Direction,
    ) -> str:
        if opposing_target is None:
            return f"No opposing zone target found; using fixed {self.config.min_reward_to_risk}R target={fixed_target}."
        if target == opposing_target:
            label = "supply" if direction == Direction.BUY else "demand"
            return f"Using nearest opposing {label} zone target={opposing_target}; fixed target was {fixed_target}."
        return f"Opposing zone target={opposing_target} was inside minimum reward; using fixed target={fixed_target}."

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
