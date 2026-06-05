from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from typing import Protocol

from forex_bot.models import Direction


class ExecutionProviderError(ValueError):
    pass


@dataclass(frozen=True)
class ExecutionDiagnostics:
    provider: str
    environment: str
    configured: bool
    can_place_orders: bool
    reason: str
    server: str = ""
    login_present: bool = False
    password_present: bool = False
    terminal_connected: bool = False
    account_info_visible: bool = False
    positions_visible: bool = False
    ticks_visible: bool = False
    read_only_probe_ok: bool = False
    reconciliation_ok: bool = False
    account_equity_visible: bool = False
    margin_visible: bool = False
    orders_visible: bool = False
    symbol_info_visible: bool = False
    duplicate_order_check_ok: bool = False
    account_login: str = ""
    symbols_checked: tuple[str, ...] = ()
    probe_error: str = ""
    probe_details: dict[str, Any] | None = None


@dataclass(frozen=True)
class OrderSubmissionRequest:
    symbol: str
    direction: Direction
    units: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    strategy_decision_id: str
    idempotency_key: str


@dataclass(frozen=True)
class OrderSubmissionResult:
    state: str
    idempotency_key: str
    broker_order_id: str = ""
    broker_deal_id: str = ""
    message: str = ""
    raw_response: dict[str, Any] | None = None


class ExecutionClient(Protocol):
    provider_name: str

    def diagnose(self) -> ExecutionDiagnostics:
        raise NotImplementedError

    def submit_order(self, request: OrderSubmissionRequest, ledger=None) -> OrderSubmissionResult:
        raise NotImplementedError
