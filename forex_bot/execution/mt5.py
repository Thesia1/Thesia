import platform
from decimal import Decimal, ROUND_DOWN

from forex_bot.config import ExecutionConfig
from forex_bot.execution.base import ExecutionDiagnostics, ExecutionProviderError, OrderSubmissionRequest, OrderSubmissionResult
from forex_bot.execution.ledger import FileOrderLedger
from forex_bot.models import Direction


class Mt5ExecutionClient:
    provider_name = "mt5"

    def __init__(self, config: ExecutionConfig) -> None:
        self.config = config

    def diagnose(self, probe_terminal: bool = False, symbols: tuple[str, ...] = ()) -> ExecutionDiagnostics:
        missing = self._missing_settings()
        configured = not missing
        reason = "MT5 credentials are configured; run the terminal probe to verify Deriv MT5 reconciliation." if configured else f"Missing required MT5 setting(s): {', '.join(missing)}"
        diagnostics = ExecutionDiagnostics(
            provider=self.provider_name,
            environment=self.config.environment.value,
            configured=configured,
            can_place_orders=False,
            reason=reason,
            server=_mask_server(self.config.mt5_server),
            login_present=bool(self.config.mt5_login),
            password_present=bool(self.config.mt5_password),
        )
        if not probe_terminal or not configured:
            return diagnostics
        return self._probe_terminal(diagnostics, symbols)

    def require_ready_for_orders(self) -> None:
        diagnostics = self.diagnose()
        if not diagnostics.configured:
            raise ExecutionProviderError(diagnostics.reason)
        raise ExecutionProviderError(diagnostics.reason)

    def _missing_settings(self) -> list[str]:
        missing = []
        if not self.config.mt5_login or self.config.mt5_login.startswith("your_"):
            missing.append("MT5_LOGIN")
        if not self.config.mt5_password or self.config.mt5_password.startswith("your_"):
            missing.append("MT5_PASSWORD")
        if not self.config.mt5_server or self.config.mt5_server.startswith("your_"):
            missing.append("MT5_SERVER")
        return missing

    def _probe_terminal(self, diagnostics: ExecutionDiagnostics, symbols: tuple[str, ...]) -> ExecutionDiagnostics:
        try:
            import MetaTrader5 as mt5
        except Exception as error:
            return _replace_diagnostics(
                diagnostics,
                probe_error=(
                    "MetaTrader5 Python package is not available in this Python environment. "
                    "The official MetaTrader5 Python bridge is distributed primarily as Windows wheels, "
                    "so macOS/Linux usually need a Windows MT5 terminal, VM, VPS, or remote bridge for live probing."
                ),
                probe_details={
                    "import_error": str(error),
                    "platform": platform.platform(),
                    "python_version": platform.python_version(),
                    "install_hint": "On Windows with MT5 installed, run: python -m pip install MetaTrader5",
                    "recommended_next_step": "Run this probe from a Windows machine or VPS with Deriv MT5 installed and logged in.",
                },
            )

        try:
            login = int(self.config.mt5_login)
        except ValueError:
            return _replace_diagnostics(diagnostics, probe_error="MT5_LOGIN must be numeric for the MetaTrader5 Python API.")

        initialize_kwargs = {
            "login": login,
            "password": self.config.mt5_password,
            "server": self.config.mt5_server,
            "timeout": 15000,
        }
        path = self.config.mt5_path.strip()
        if path:
            initialized = mt5.initialize(path, **initialize_kwargs)
        else:
            initialized = mt5.initialize(**initialize_kwargs)

        if not initialized:
            error = _mt5_last_error(mt5)
            return _replace_diagnostics(
                diagnostics,
                probe_error=f"MT5 initialize/login failed: {error}",
                probe_details={"last_error": error},
            )

        try:
            account_info = mt5.account_info()
            if account_info is None:
                error = _mt5_last_error(mt5)
                return _replace_diagnostics(
                    diagnostics,
                    terminal_connected=True,
                    probe_error=f"MT5 account_info failed: {error}",
                    probe_details={"last_error": error},
                )

            positions = mt5.positions_get()
            orders = mt5.orders_get()
            positions_visible = positions is not None
            orders_visible = orders is not None
            account_equity_visible = getattr(account_info, "equity", None) is not None
            margin_visible = getattr(account_info, "margin_free", None) is not None or getattr(account_info, "margin", None) is not None
            symbol_results = {}
            ticks_visible = False
            symbol_info_visible = False
            checked: list[str] = []
            for raw_symbol in symbols:
                for symbol in _mt5_symbol_candidates(raw_symbol):
                    selected = mt5.symbol_select(symbol, True)
                    tick = mt5.symbol_info_tick(symbol) if selected else None
                    info = mt5.symbol_info(symbol) if selected else None
                    symbol_results[symbol] = {
                        "selected": bool(selected),
                        "tick_visible": tick is not None,
                        "symbol_info_visible": info is not None,
                    }
                    checked.append(symbol)
                    if tick is not None:
                        ticks_visible = True
                    if info is not None:
                        symbol_info_visible = True
                    if tick is not None and info is not None:
                        break
            symbols_ok = not symbols or (ticks_visible and symbol_info_visible)
            reconciliation_ok = positions_visible and orders_visible and account_equity_visible and margin_visible and symbols_ok
            can_place_orders = reconciliation_ok and self.config.order_placement_enabled
            probe_error = "" if reconciliation_ok else "MT5 probe connected but did not verify every reconciliation input."

            return _replace_diagnostics(
                diagnostics,
                reason=(
                    "Deriv MT5 reconciliation verified and order placement is enabled."
                    if can_place_orders
                    else "Deriv MT5 reconciliation verified; order placement remains disabled by EXECUTION_ENABLE_ORDER_PLACEMENT."
                    if reconciliation_ok
                    else diagnostics.reason
                ),
                can_place_orders=can_place_orders,
                terminal_connected=True,
                account_info_visible=True,
                positions_visible=positions_visible,
                ticks_visible=ticks_visible,
                read_only_probe_ok=reconciliation_ok,
                reconciliation_ok=reconciliation_ok,
                account_equity_visible=account_equity_visible,
                margin_visible=margin_visible,
                orders_visible=orders_visible,
                symbol_info_visible=symbol_info_visible,
                duplicate_order_check_ok=orders_visible,
                account_login=_mask_login(str(getattr(account_info, "login", ""))),
                symbols_checked=tuple(checked),
                probe_error=probe_error,
                probe_details={
                    "company": str(getattr(account_info, "company", "")),
                    "server": str(getattr(account_info, "server", "")),
                    "currency": str(getattr(account_info, "currency", "")),
                    "balance_present": getattr(account_info, "balance", None) is not None,
                    "equity_present": account_equity_visible,
                    "margin_present": margin_visible,
                    "positions_count": len(positions) if positions is not None else None,
                    "orders_count": len(orders) if orders is not None else None,
                    "symbols": symbol_results,
                },
            )
        finally:
            mt5.shutdown()

    def submit_order(self, request: OrderSubmissionRequest, ledger: FileOrderLedger | None = None) -> OrderSubmissionResult:
        if not self.config.order_placement_enabled:
            raise ExecutionProviderError("Order placement is disabled. Set EXECUTION_ENABLE_ORDER_PLACEMENT=true only after live readiness is complete.")
        ledger = ledger or FileOrderLedger(self.config.idempotency_ledger_path)
        if ledger.has_submitted(request.idempotency_key):
            return OrderSubmissionResult(
                state="DUPLICATE_BLOCKED",
                idempotency_key=request.idempotency_key,
                message="Duplicate order submission blocked by idempotency ledger.",
            )

        diagnostics = self.diagnose(probe_terminal=True, symbols=(request.symbol,))
        if not diagnostics.can_place_orders:
            raise ExecutionProviderError(diagnostics.probe_error or diagnostics.reason)

        mt5 = self._load_mt5()
        self._initialize_mt5(mt5)
        try:
            symbol, tick, info = self._resolve_symbol_for_order(mt5, request.symbol)
            volume = _units_to_volume(request.units, info)
            order_type = mt5.ORDER_TYPE_BUY if request.direction == Direction.BUY else mt5.ORDER_TYPE_SELL
            price = Decimal(str(tick.ask if request.direction == Direction.BUY else tick.bid))
            mt5_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": order_type,
                "price": float(price),
                "sl": float(request.stop_loss),
                "tp": float(request.take_profit),
                "deviation": self.config.mt5_deviation_points,
                "magic": self.config.mt5_magic,
                "comment": request.idempotency_key[:31],
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": getattr(mt5, "ORDER_FILLING_FOK", 0),
            }
            result = mt5.order_send(mt5_request)
            if result is None:
                raise ExecutionProviderError(f"MT5 order_send returned no result: {_mt5_last_error(mt5)}")

            retcode = getattr(result, "retcode", None)
            accepted = retcode in _successful_retcode_values(mt5)
            submission = OrderSubmissionResult(
                state="ACCEPTED" if accepted else "REJECTED",
                idempotency_key=request.idempotency_key,
                broker_order_id=str(getattr(result, "order", "")),
                broker_deal_id=str(getattr(result, "deal", "")),
                message=str(getattr(result, "comment", "")),
                raw_response={
                    "retcode": retcode,
                    "symbol": symbol,
                    "volume": str(volume),
                    "price": str(price),
                },
            )
            ledger.record_submission(
                idempotency_key=request.idempotency_key,
                strategy_decision_id=request.strategy_decision_id,
                symbol=request.symbol,
                result=submission,
            )
            if not accepted:
                raise ExecutionProviderError(f"MT5 rejected order_send retcode={retcode}: {submission.message}")
            return submission
        finally:
            mt5.shutdown()

    def _load_mt5(self):
        try:
            import MetaTrader5 as mt5
        except Exception as error:
            raise ExecutionProviderError(
                "MetaTrader5 Python package is not available in this Python environment. "
                "Run live execution from a Windows machine or VPS with Deriv MT5 installed."
            ) from error
        return mt5

    def _initialize_mt5(self, mt5) -> None:
        try:
            login = int(self.config.mt5_login)
        except ValueError as error:
            raise ExecutionProviderError("MT5_LOGIN must be numeric for the MetaTrader5 Python API.") from error
        initialize_kwargs = {
            "login": login,
            "password": self.config.mt5_password,
            "server": self.config.mt5_server,
            "timeout": 15000,
        }
        path = self.config.mt5_path.strip()
        initialized = mt5.initialize(path, **initialize_kwargs) if path else mt5.initialize(**initialize_kwargs)
        if not initialized:
            raise ExecutionProviderError(f"MT5 initialize/login failed: {_mt5_last_error(mt5)}")

    def _resolve_symbol_for_order(self, mt5, raw_symbol: str):
        for symbol in _mt5_symbol_candidates(raw_symbol):
            selected = mt5.symbol_select(symbol, True)
            tick = mt5.symbol_info_tick(symbol) if selected else None
            info = mt5.symbol_info(symbol) if selected else None
            if tick is not None and info is not None:
                return symbol, tick, info
        raise ExecutionProviderError(f"MT5 could not resolve symbol/tick metadata for {raw_symbol}.")


def _mask_server(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}...{value[-3:]}"


def _replace_diagnostics(diagnostics: ExecutionDiagnostics, **updates) -> ExecutionDiagnostics:
    values = diagnostics.__dict__.copy()
    values.update(updates)
    return ExecutionDiagnostics(**values)


def _mt5_last_error(mt5) -> str:
    try:
        return str(mt5.last_error())
    except Exception:
        return "unknown"


def _mt5_symbol_candidates(symbol: str) -> tuple[str, ...]:
    stripped = symbol.replace("_", "").replace("/", "").upper()
    original = symbol.strip()
    if original and original != stripped:
        return stripped, original
    return (stripped,)


def _mask_login(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}...{value[-2:]}"


def _successful_retcode_values(mt5) -> set[int]:
    values = set()
    for name in ("TRADE_RETCODE_DONE", "TRADE_RETCODE_PLACED", "TRADE_RETCODE_DONE_PARTIAL"):
        value = getattr(mt5, name, None)
        if value is not None:
            values.add(value)
    return values or {10009, 10008, 10010}


def _units_to_volume(units: Decimal, symbol_info) -> Decimal:
    contract_size = Decimal(str(getattr(symbol_info, "trade_contract_size", 100000) or 100000))
    volume_step = Decimal(str(getattr(symbol_info, "volume_step", "0.01") or "0.01"))
    volume_min = Decimal(str(getattr(symbol_info, "volume_min", "0.01") or "0.01"))
    volume_max = Decimal(str(getattr(symbol_info, "volume_max", "100") or "100"))
    if units <= 0:
        raise ExecutionProviderError("Order units must be greater than zero.")
    if contract_size <= 0 or volume_step <= 0:
        raise ExecutionProviderError("MT5 symbol contract size and volume step must be greater than zero.")
    volume = (units / contract_size / volume_step).to_integral_value(rounding=ROUND_DOWN) * volume_step
    if volume < volume_min:
        raise ExecutionProviderError(f"Calculated MT5 volume {volume} is below symbol minimum {volume_min}.")
    if volume > volume_max:
        raise ExecutionProviderError(f"Calculated MT5 volume {volume} is above symbol maximum {volume_max}.")
    return volume
