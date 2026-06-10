from dataclasses import dataclass
from decimal import Decimal

from forex_bot.market_data import detect_swings, sort_candles
from forex_bot.models import Candle, Direction, SignalState, StrategyDecision, Timeframe


@dataclass(frozen=True)
class TimeframeBiasReport:
    timeframe: Timeframe
    bias: str
    structure: str
    confidence_score: int
    latest_close: Decimal | None
    previous_close: Decimal | None
    reason: str


@dataclass(frozen=True)
class MarketBiasReport:
    pair_asset: str
    monthly_bias: TimeframeBiasReport
    weekly_bias: TimeframeBiasReport
    daily_bias: TimeframeBiasReport
    h4_bias: TimeframeBiasReport
    lower_timeframe_entry_bias: TimeframeBiasReport
    overall_market_direction: str
    trade_classification: str
    supply_demand_setup_found: bool
    trendline_setup_found: bool
    book_based_insight_applied: bool
    entry_type: str
    entry_area: str
    stop_loss: str
    take_profit: str
    setup_quality: str
    confidence_score: int
    final_decision: str
    candidate_conflict: bool
    reason: str


def build_market_bias_report(
    *,
    symbol: str,
    monthly_candles: list[Candle] | None,
    weekly_candles: list[Candle] | None,
    daily_candles: list[Candle] | None,
    h4_candles: list[Candle] | None,
    entry_candles: list[Candle],
    strategy_decision: StrategyDecision,
    all_strategy_decisions: tuple[StrategyDecision, ...] = (),
) -> MarketBiasReport:
    monthly = analyze_timeframe_bias(monthly_candles or [], Timeframe.M)
    weekly = analyze_timeframe_bias(weekly_candles or [], Timeframe.W)
    daily = analyze_timeframe_bias(daily_candles or [], Timeframe.D)
    h4 = analyze_timeframe_bias(h4_candles or [], Timeframe.H4)
    entry_timeframe = entry_candles[-1].timeframe if entry_candles else Timeframe.H1
    entry = analyze_timeframe_bias(entry_candles, entry_timeframe)
    decisions = all_strategy_decisions or (strategy_decision,)
    supply_demand_setup_found = any(_supply_demand_setup_found(decision) for decision in decisions)
    trendline_setup_found = any(_trendline_setup_found(decision) for decision in decisions)

    classification, direction, confidence, reason = _classify_top_down(monthly, weekly, daily, h4, entry)
    context_is_actionable = _actionable_context_count(monthly, weekly, daily) >= 2
    final_decision = "Wait"
    candidate_conflict = False
    entry_type = "Wait"
    entry_area = "Wait"
    stop_loss = "Wait"
    take_profit = "Wait"
    candidate = strategy_decision.candidate

    if candidate is not None:
        candidate_direction = candidate.direction
        if direction is None:
            if context_is_actionable:
                candidate_conflict = True
                final_decision = "Reject setup"
                reason = f"{reason} Existing setup rejected because top-down context is not tradeable enough."
            else:
                final_decision = "Wait"
                reason = f"{reason} Existing setup remains subject to the strategy and risk gates because higher-timeframe context is incomplete."
        elif candidate_direction != direction:
            candidate_conflict = context_is_actionable and confidence >= 60
            final_decision = "Reject setup" if candidate_conflict else "Wait"
            reason = (
                f"{reason} Existing {candidate_direction.value} setup conflicts with "
                f"{classification.lower()} context."
            )
        else:
            final_decision = direction.value.title()
            entry_type = "Market Entry"
            entry_area = str(candidate.entry_price)
            stop_loss = str(candidate.stop_loss)
            take_profit = str(candidate.take_profit)
            reason = f"{reason} Existing deterministic strategy candidate agrees with the top-down context."
    elif direction is not None:
        final_decision = "Wait"
        reason = f"{reason} Directional bias exists, but no deterministic strategy trade candidate is present."
    else:
        final_decision = "Wait"

    return MarketBiasReport(
        pair_asset=symbol,
        monthly_bias=monthly,
        weekly_bias=weekly,
        daily_bias=daily,
        h4_bias=h4,
        lower_timeframe_entry_bias=entry,
        overall_market_direction=_overall_direction(classification),
        trade_classification=classification,
        supply_demand_setup_found=supply_demand_setup_found,
        trendline_setup_found=trendline_setup_found,
        book_based_insight_applied=_book_context_applied(monthly, weekly, daily, h4, entry),
        entry_type=entry_type,
        entry_area=entry_area,
        stop_loss=stop_loss,
        take_profit=take_profit,
        setup_quality=_setup_quality(confidence, candidate, candidate_conflict),
        confidence_score=confidence,
        final_decision=final_decision,
        candidate_conflict=candidate_conflict,
        reason=reason,
    )


def analyze_timeframe_bias(candles: list[Candle], timeframe: Timeframe) -> TimeframeBiasReport:
    ordered = sort_candles(candles)
    if len(ordered) < 3:
        return TimeframeBiasReport(
            timeframe=timeframe,
            bias="INSUFFICIENT",
            structure="insufficient_data",
            confidence_score=0,
            latest_close=ordered[-1].close if ordered else None,
            previous_close=ordered[-2].close if len(ordered) >= 2 else None,
            reason=f"{timeframe.value} needs at least 3 closed candles for a directional read.",
        )

    latest = ordered[-1]
    previous = ordered[-2]
    first = ordered[0]
    close_bias = _close_bias(first.close, previous.close, latest.close)
    swings = detect_swings(ordered, window=1)
    highs = [swing for swing in swings if swing.kind == "high"]
    lows = [swing for swing in swings if swing.kind == "low"]

    if len(highs) >= 2 and len(lows) >= 2:
        previous_high, latest_high = highs[-2], highs[-1]
        previous_low, latest_low = lows[-2], lows[-1]
        higher_high = latest_high.candle.high > previous_high.candle.high
        higher_low = latest_low.candle.low > previous_low.candle.low
        lower_high = latest_high.candle.high < previous_high.candle.high
        lower_low = latest_low.candle.low < previous_low.candle.low
        if higher_high and higher_low and close_bias != "BEARISH":
            return TimeframeBiasReport(
                timeframe=timeframe,
                bias="BULLISH",
                structure="higher_highs_higher_lows",
                confidence_score=84 if close_bias == "BULLISH" else 76,
                latest_close=latest.close,
                previous_close=previous.close,
                reason=(
                    f"{timeframe.value} is forming higher highs and higher lows; "
                    f"last swing high {previous_high.candle.high}->{latest_high.candle.high}, "
                    f"last swing low {previous_low.candle.low}->{latest_low.candle.low}."
                ),
            )
        if lower_high and lower_low and close_bias != "BULLISH":
            return TimeframeBiasReport(
                timeframe=timeframe,
                bias="BEARISH",
                structure="lower_highs_lower_lows",
                confidence_score=84 if close_bias == "BEARISH" else 76,
                latest_close=latest.close,
                previous_close=previous.close,
                reason=(
                    f"{timeframe.value} is forming lower highs and lower lows; "
                    f"last swing high {previous_high.candle.high}->{latest_high.candle.high}, "
                    f"last swing low {previous_low.candle.low}->{latest_low.candle.low}."
                ),
            )
        return TimeframeBiasReport(
            timeframe=timeframe,
            bias="RANGING",
            structure="mixed_swing_structure",
            confidence_score=45,
            latest_close=latest.close,
            previous_close=previous.close,
            reason=f"{timeframe.value} swing structure is mixed; higher-timeframe direction is not clean.",
        )

    if close_bias == "BULLISH":
        return TimeframeBiasReport(
            timeframe=timeframe,
            bias="BULLISH",
            structure="rising_closes",
            confidence_score=62,
            latest_close=latest.close,
            previous_close=previous.close,
            reason=f"{timeframe.value} lacks enough confirmed swings, but closes are rising from {first.close} to {latest.close}.",
        )
    if close_bias == "BEARISH":
        return TimeframeBiasReport(
            timeframe=timeframe,
            bias="BEARISH",
            structure="falling_closes",
            confidence_score=62,
            latest_close=latest.close,
            previous_close=previous.close,
            reason=f"{timeframe.value} lacks enough confirmed swings, but closes are falling from {first.close} to {latest.close}.",
        )
    return TimeframeBiasReport(
        timeframe=timeframe,
        bias="RANGING",
        structure="flat_or_unclear_closes",
        confidence_score=35,
        latest_close=latest.close,
        previous_close=previous.close,
        reason=f"{timeframe.value} closes are flat or unclear; wait for cleaner structure.",
    )


def _classify_top_down(
    monthly: TimeframeBiasReport,
    weekly: TimeframeBiasReport,
    daily: TimeframeBiasReport,
    h4: TimeframeBiasReport,
    entry: TimeframeBiasReport,
) -> tuple[str, Direction | None, int, str]:
    htf = (monthly, weekly, daily)
    bull_htf = sum(1 for item in htf if item.bias == "BULLISH")
    bear_htf = sum(1 for item in htf if item.bias == "BEARISH")
    actionable_htf = _actionable_context_count(*htf)

    if actionable_htf < 2:
        return (
            "No Trade / Wait",
            None,
            30,
            "Monthly/weekly/daily context is incomplete; lower timeframes cannot carry the trade alone.",
        )

    if bull_htf == 3:
        if h4.bias == "BEARISH":
            return (
                "No Trade / Wait",
                None,
                58,
                "Monthly/weekly/daily are bullish, but H4 is bearish; wait for H4 to realign before buying.",
            )
        confidence = _direction_confidence(Direction.BUY, monthly, weekly, daily, h4, entry)
        return ("Long-Term Buy", Direction.BUY, confidence, "Monthly, weekly, and daily are aligned bullish.")

    if bear_htf == 3:
        if h4.bias == "BULLISH":
            return (
                "No Trade / Wait",
                None,
                58,
                "Monthly/weekly/daily are bearish, but H4 is bullish; wait for H4 to realign before selling.",
            )
        confidence = _direction_confidence(Direction.SELL, monthly, weekly, daily, h4, entry)
        return ("Long-Term Sell", Direction.SELL, confidence, "Monthly, weekly, and daily are aligned bearish.")

    if bull_htf >= 2 and bear_htf == 0:
        if h4.bias == "BEARISH" or entry.bias == "BEARISH":
            return (
                "No Trade / Wait",
                None,
                54,
                "Higher timeframe leans bullish, but H4 or entry timing is bearish; wait instead of forcing a buy.",
            )
        confidence = _direction_confidence(Direction.BUY, monthly, weekly, daily, h4, entry)
        return ("Short-Term Buy", Direction.BUY, min(confidence, 86), "Higher timeframe leans bullish with no bearish monthly/weekly/daily opposition.")

    if bear_htf >= 2 and bull_htf == 0:
        if h4.bias == "BULLISH" or entry.bias == "BULLISH":
            return (
                "No Trade / Wait",
                None,
                54,
                "Higher timeframe leans bearish, but H4 or entry timing is bullish; wait instead of forcing a sell.",
            )
        confidence = _direction_confidence(Direction.SELL, monthly, weekly, daily, h4, entry)
        return ("Short-Term Sell", Direction.SELL, min(confidence, 86), "Higher timeframe leans bearish with no bullish monthly/weekly/daily opposition.")

    if bull_htf and bear_htf:
        return (
            "No Trade / Wait",
            None,
            46,
            "Monthly, weekly, and daily are fighting each other; top-down rules require waiting.",
        )

    if h4.bias == "BULLISH" and entry.bias == "BULLISH" and bear_htf == 0:
        confidence = _direction_confidence(Direction.BUY, monthly, weekly, daily, h4, entry)
        return ("Short-Term Buy", Direction.BUY, min(confidence, 74), "H4 and entry are bullish, but higher timeframe support is incomplete.")

    if h4.bias == "BEARISH" and entry.bias == "BEARISH" and bull_htf == 0:
        confidence = _direction_confidence(Direction.SELL, monthly, weekly, daily, h4, entry)
        return ("Short-Term Sell", Direction.SELL, min(confidence, 74), "H4 and entry are bearish, but higher timeframe support is incomplete.")

    return ("No Trade / Wait", None, 40, "Market structure is unclear or ranging; wait for a cleaner top-down read.")


def _direction_confidence(
    direction: Direction,
    monthly: TimeframeBiasReport,
    weekly: TimeframeBiasReport,
    daily: TimeframeBiasReport,
    h4: TimeframeBiasReport,
    entry: TimeframeBiasReport,
) -> int:
    desired = "BULLISH" if direction == Direction.BUY else "BEARISH"
    opposite = "BEARISH" if direction == Direction.BUY else "BULLISH"
    score = 35
    for report, weight in ((monthly, 16), (weekly, 18), (daily, 20), (h4, 14), (entry, 7)):
        if report.bias == desired:
            score += weight
            if report.structure in ("higher_highs_higher_lows", "lower_highs_lower_lows"):
                score += 3
        elif report.bias == opposite:
            score -= weight
        elif report.bias == "RANGING":
            score -= 4
        else:
            score -= 2
    if monthly.bias == weekly.bias == daily.bias == desired:
        score += 8
    return max(0, min(100, score))


def _close_bias(first_close: Decimal, previous_close: Decimal, latest_close: Decimal) -> str:
    if latest_close > previous_close and latest_close > first_close:
        return "BULLISH"
    if latest_close < previous_close and latest_close < first_close:
        return "BEARISH"
    return "RANGING"


def _actionable_context_count(*reports: TimeframeBiasReport) -> int:
    return sum(1 for report in reports if report.bias in {"BULLISH", "BEARISH", "RANGING"})


def _supply_demand_setup_found(decision: StrategyDecision) -> bool:
    if decision.state in {SignalState.WATCH, SignalState.TRADE_CANDIDATE}:
        return True
    return any(
        item.passed and ("zone" in item.rule or "demand" in item.detail.lower() or "supply" in item.detail.lower())
        for item in decision.evidence
    )


def _trendline_setup_found(decision: StrategyDecision) -> bool:
    return decision.setup_name == "trendline_zone_sequence" and (
        decision.state in {SignalState.WATCH, SignalState.TRADE_CANDIDATE}
        or any(item.passed and "trendline" in item.rule for item in decision.evidence)
    )


def _book_context_applied(*reports: TimeframeBiasReport) -> bool:
    return any(report.bias != "INSUFFICIENT" for report in reports)


def _setup_quality(confidence: int, candidate, candidate_conflict: bool) -> str:
    if candidate_conflict:
        return "Invalid"
    if candidate is not None and confidence < 40:
        return "Weak"
    if confidence < 40:
        return "Invalid"
    if candidate is None and confidence < 75:
        return "Weak"
    if confidence >= 90:
        return "Strong"
    if confidence >= 75:
        return "Medium"
    return "Weak"


def _overall_direction(classification: str) -> str:
    if "Buy" in classification:
        return "Bullish"
    if "Sell" in classification:
        return "Bearish"
    return "Wait"
