from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class RiskDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class AccountState:
    equity: Decimal
    daily_realized_loss: Decimal
    weekly_realized_loss: Decimal
    open_trade_count: int
    open_risk: Decimal
    margin_available: Decimal


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    pip_size: Decimal
    pip_value_per_unit: Decimal
    min_units: Decimal
    max_units: Decimal
    unit_step: Decimal
    margin_rate: Decimal
    max_spread_pips: Decimal


@dataclass(frozen=True)
class TradeCandidate:
    symbol: str
    direction: Direction
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    spread_pips: Decimal
    setup_name: str
    strategy_decision_id: str


@dataclass(frozen=True)
class RiskLimits:
    risk_percent: Decimal = Decimal("0.0025")
    max_daily_loss_percent: Decimal = Decimal("0.02")
    max_weekly_loss_percent: Decimal = Decimal("0.05")
    max_open_trades: int = 1
    max_open_risk_percent: Decimal = Decimal("0.03")
    min_reward_to_risk: Decimal = Decimal("2")
    max_slippage_pips: Decimal = Decimal("1.5")


@dataclass(frozen=True)
class RiskApproval:
    decision: RiskDecision
    units: Decimal
    risk_amount: Decimal
    reward_to_risk: Decimal
    reasons: tuple[str, ...]

