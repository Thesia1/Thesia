from decimal import Decimal, ROUND_DOWN

from forex_bot.models import (
    AccountState,
    InstrumentSpec,
    RiskApproval,
    RiskDecision,
    RiskLimits,
    TradeCandidate,
)


def evaluate_risk(
    account: AccountState,
    instrument: InstrumentSpec,
    candidate: TradeCandidate,
    limits: RiskLimits,
) -> RiskApproval:
    """Approve or reject a trade candidate and calculate broker units."""

    reasons: list[str] = []

    if candidate.symbol != instrument.symbol:
        reasons.append("candidate_symbol_mismatch")

    if account.equity <= 0:
        reasons.append("invalid_account_equity")

    if candidate.spread_pips > instrument.max_spread_pips:
        reasons.append("spread_too_high")

    if account.open_trade_count >= limits.max_open_trades:
        reasons.append("too_many_open_trades")

    daily_loss_limit = account.equity * limits.max_daily_loss_percent
    if account.daily_realized_loss >= daily_loss_limit:
        reasons.append("daily_loss_limit_reached")

    weekly_loss_limit = account.equity * limits.max_weekly_loss_percent
    if account.weekly_realized_loss >= weekly_loss_limit:
        reasons.append("weekly_loss_limit_reached")

    max_open_risk = account.equity * limits.max_open_risk_percent
    if account.open_risk >= max_open_risk:
        reasons.append("open_risk_limit_reached")

    stop_distance_pips = abs(candidate.entry_price - candidate.stop_loss) / instrument.pip_size
    target_distance_pips = abs(candidate.take_profit - candidate.entry_price) / instrument.pip_size

    if stop_distance_pips <= 0:
        reasons.append("invalid_stop_loss")

    if target_distance_pips <= 0:
        reasons.append("invalid_take_profit")

    reward_to_risk = Decimal("0")
    if stop_distance_pips > 0:
        reward_to_risk = target_distance_pips / stop_distance_pips
        if reward_to_risk < limits.min_reward_to_risk:
            reasons.append("reward_to_risk_too_low")

    risk_amount = account.equity * limits.risk_percent
    raw_units = Decimal("0")
    if stop_distance_pips > 0 and instrument.pip_value_per_unit > 0:
        raw_units = risk_amount / (stop_distance_pips * instrument.pip_value_per_unit)

    units = _floor_to_step(raw_units, instrument.unit_step)

    if units < instrument.min_units:
        reasons.append("position_below_min_units")

    if units > instrument.max_units:
        units = instrument.max_units

    estimated_margin = candidate.entry_price * units * instrument.margin_rate
    if estimated_margin > account.margin_available:
        reasons.append("insufficient_margin")

    if not candidate.strategy_decision_id:
        reasons.append("missing_strategy_decision_id")

    if reasons:
        return RiskApproval(
            decision=RiskDecision.REJECTED,
            units=Decimal("0"),
            risk_amount=risk_amount,
            reward_to_risk=reward_to_risk,
            reasons=tuple(reasons),
        )

    return RiskApproval(
        decision=RiskDecision.APPROVED,
        units=units,
        risk_amount=risk_amount,
        reward_to_risk=reward_to_risk,
        reasons=(),
    )


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("step must be greater than zero")

    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step

