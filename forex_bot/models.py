from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class BotMode(str, Enum):
    OFF = "OFF"
    WATCH = "WATCH"
    ASSISTED = "ASSISTED"
    AUTONOMOUS_PAPER = "AUTONOMOUS_PAPER"
    AUTONOMOUS_LIVE = "AUTONOMOUS_LIVE"


class BrokerEnvironment(str, Enum):
    PRACTICE = "practice"
    LIVE = "live"


class BrokerProvider(str, Enum):
    OANDA = "oanda"
    FOREX_COM = "forex_com"
    MT5 = "mt5"


class ExecutionProvider(str, Enum):
    OANDA = "oanda"
    MT5 = "mt5"
    NONE = "none"


class NewsProvider(str, Enum):
    TRADING_ECONOMICS = "trading_economics"
    ALPHA_VANTAGE = "alpha_vantage"
    MARKETAUX = "marketaux"
    NONE = "none"


class AgentProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    NONE = "none"


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class RiskDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SignalState(str, Enum):
    NO_TRADE = "NO_TRADE"
    WATCH = "WATCH"
    TRADE_CANDIDATE = "TRADE_CANDIDATE"


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D = "D"
    W = "W"
    M = "M"


class ZoneType(str, Enum):
    SUPPLY = "SUPPLY"
    DEMAND = "DEMAND"


class ZoneStatus(str, Enum):
    FRESH = "FRESH"
    RETESTED = "RETESTED"
    INVALIDATED = "INVALIDATED"


class OrderIntentState(str, Enum):
    CREATED = "CREATED"
    RISK_APPROVED = "RISK_APPROVED"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    FILLED = "FILLED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    UNKNOWN_BROKER_STATE = "UNKNOWN_BROKER_STATE"


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("candle high must be greater than or equal to open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("candle low must be less than or equal to open, close, and high")


@dataclass(frozen=True)
class PriceSnapshot:
    symbol: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")


@dataclass(frozen=True)
class SpreadSnapshot:
    symbol: str
    timestamp: datetime
    spread_pips: Decimal


@dataclass(frozen=True)
class Zone:
    id: str
    symbol: str
    timeframe: Timeframe
    zone_type: ZoneType
    high: Decimal
    low: Decimal
    created_at: datetime
    source_start: datetime
    source_end: datetime
    status: ZoneStatus = ZoneStatus.FRESH
    removed_opposite_zone_id: str | None = None

    def __post_init__(self) -> None:
        if self.high <= self.low:
            raise ValueError("zone high must be greater than zone low")


@dataclass(frozen=True)
class RuleEvidence:
    rule: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class SetupDetection:
    setup_name: str
    state: SignalState
    evidence: tuple[RuleEvidence, ...]


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

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("trade candidate requires a symbol")
        if not self.strategy_decision_id:
            raise ValueError("trade candidate requires a strategy decision id")
        if self.entry_price <= 0 or self.stop_loss <= 0 or self.take_profit <= 0:
            raise ValueError("trade candidate prices must be positive")


@dataclass(frozen=True)
class StrategyDecision:
    id: str
    symbol: str
    state: SignalState
    setup_name: str
    created_at: datetime
    evidence: tuple[RuleEvidence, ...]
    candidate: TradeCandidate | None = None


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


@dataclass(frozen=True)
class OrderIntent:
    id: str
    strategy_decision_id: str
    risk_approval_id: str
    candidate: TradeCandidate
    units: Decimal
    state: OrderIntentState = OrderIntentState.CREATED

    def __post_init__(self) -> None:
        if not self.risk_approval_id:
            raise ValueError("order intent requires a risk approval id")


@dataclass(frozen=True)
class BrokerOrder:
    id: str
    order_intent_id: str
    broker_order_id: str
    state: OrderIntentState
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class Position:
    symbol: str
    units: Decimal
    average_price: Decimal
    unrealized_pl: Decimal


@dataclass(frozen=True)
class ExecutionAudit:
    id: str
    created_at: datetime
    event_type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ModeChange:
    created_at: datetime
    previous_mode: BotMode
    new_mode: BotMode
    reason: str
