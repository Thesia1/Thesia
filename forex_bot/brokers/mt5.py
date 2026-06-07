from datetime import datetime, timezone
from decimal import Decimal

from forex_bot.brokers.base import BrokerConfigError, MarketSnapshot
from forex_bot.config import ExecutionConfig
from forex_bot.models import Candle, InstrumentSpec, Timeframe
from forex_bot.symbols import mt5_symbol_candidates


class Mt5MarketDataError(BrokerConfigError):
    pass


class Mt5MarketDataClient:
    provider_name = "mt5"

    def __init__(self, config: ExecutionConfig) -> None:
        self.config = config

    def get_market_snapshot(self, symbol: str, granularity: Timeframe = Timeframe.H1, count: int = 200) -> MarketSnapshot:
        mt5 = self._load_mt5()
        self._initialize_mt5(mt5)
        try:
            resolved_symbol, tick, info = self._resolve_symbol(mt5, symbol)
            instrument = _instrument_spec_from_symbol_info(resolved_symbol, info, tick)
            candles = self._get_complete_candles(mt5, resolved_symbol, granularity, count)
            spread_points = _spread_points(tick, instrument)
            return MarketSnapshot(
                candles=candles,
                instrument=instrument,
                spread_pips=spread_points,
                provider=self.provider_name,
            )
        finally:
            mt5.shutdown()

    def _load_mt5(self):
        try:
            import MetaTrader5 as mt5
        except Exception as error:
            raise Mt5MarketDataError(
                "MetaTrader5 Python package is not available in this Python environment. "
                "Synthetic-index market data must be read from Windows or a VPS with Deriv MT5 installed."
            ) from error
        return mt5

    def _initialize_mt5(self, mt5) -> None:
        missing = []
        if not self.config.mt5_login or self.config.mt5_login.startswith("your_"):
            missing.append("MT5_LOGIN")
        if not self.config.mt5_password or self.config.mt5_password.startswith("your_"):
            missing.append("MT5_PASSWORD")
        if not self.config.mt5_server or self.config.mt5_server.startswith("your_"):
            missing.append("MT5_SERVER")
        if missing:
            raise Mt5MarketDataError(f"Missing required MT5 setting(s): {', '.join(missing)}")
        try:
            login = int(self.config.mt5_login)
        except ValueError as error:
            raise Mt5MarketDataError("MT5_LOGIN must be numeric for the MetaTrader5 Python API.") from error

        initialize_kwargs = {
            "login": login,
            "password": self.config.mt5_password,
            "server": self.config.mt5_server,
            "timeout": self.config.mt5_timeout_ms,
        }
        path = self.config.mt5_path.strip()
        initialized = mt5.initialize(path, **initialize_kwargs) if path else mt5.initialize(**initialize_kwargs)
        if not initialized:
            error = _mt5_last_error(mt5)
            if _is_authorization_failed(error):
                mt5.shutdown()
                initialized = _initialize_attached_terminal(mt5, path, self.config.mt5_timeout_ms)
            if not initialized:
                raise Mt5MarketDataError(f"MT5 initialize/login failed: {error}")
        account_info = mt5.account_info()
        if account_info is None:
            raise Mt5MarketDataError(f"MT5 account_info failed after initialize: {_mt5_last_error(mt5)}")
        if not _account_login_matches_config(account_info, self.config.mt5_login):
            raise Mt5MarketDataError("MT5 terminal is logged into a different account than MT5_LOGIN.")

    def _resolve_symbol(self, mt5, raw_symbol: str):
        for symbol in mt5_symbol_candidates(raw_symbol):
            selected = mt5.symbol_select(symbol, True)
            tick = mt5.symbol_info_tick(symbol) if selected else None
            info = mt5.symbol_info(symbol) if selected else None
            if tick is not None and info is not None:
                return symbol, tick, info
        raise Mt5MarketDataError(f"MT5 could not resolve synthetic/CFD symbol metadata and ticks for {raw_symbol}.")

    def _get_complete_candles(self, mt5, symbol: str, granularity: Timeframe, count: int) -> list[Candle]:
        timeframe = _mt5_timeframe(mt5, granularity)
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + 1)
        if rates is None:
            raise Mt5MarketDataError(f"MT5 did not return candles for {symbol}: {_mt5_last_error(mt5)}")
        candles = [_candle_from_rate(symbol, granularity, rate) for rate in rates]
        candles = sorted(candles, key=lambda candle: candle.timestamp)
        return candles[:-1][-count:] if len(candles) > count else candles


def _instrument_spec_from_symbol_info(symbol: str, info, tick) -> InstrumentSpec:
    contract_size = Decimal(str(getattr(info, "trade_contract_size", 1) or 1))
    volume_step = Decimal(str(getattr(info, "volume_step", "0.01") or "0.01"))
    volume_min = Decimal(str(getattr(info, "volume_min", "0.01") or "0.01"))
    volume_max = Decimal(str(getattr(info, "volume_max", "100") or "100"))
    tick_size = Decimal(str(getattr(info, "trade_tick_size", 0) or getattr(info, "point", 0) or "0.01"))
    tick_value = Decimal(str(getattr(info, "trade_tick_value", 0) or getattr(info, "trade_tick_value_profit", 0) or "1"))
    margin_rate = _margin_rate(info, tick, contract_size)
    return InstrumentSpec(
        symbol=symbol,
        pip_size=tick_size,
        pip_value_per_unit=tick_value / contract_size,
        min_units=volume_min * contract_size,
        max_units=volume_max * contract_size,
        unit_step=volume_step * contract_size,
        margin_rate=margin_rate,
        max_spread_pips=Decimal("100"),
    )


def _margin_rate(info, tick, contract_size: Decimal) -> Decimal:
    margin_initial = Decimal(str(getattr(info, "margin_initial", 0) or 0))
    ask = Decimal(str(getattr(tick, "ask", 0) or 0))
    notional_per_lot = ask * contract_size
    if margin_initial > 0 and notional_per_lot > 0:
        return margin_initial / notional_per_lot
    return Decimal("1")


def _spread_points(tick, instrument: InstrumentSpec) -> Decimal:
    bid = Decimal(str(getattr(tick, "bid", 0) or 0))
    ask = Decimal(str(getattr(tick, "ask", 0) or 0))
    if bid <= 0 or ask <= 0 or ask < bid:
        raise Mt5MarketDataError("MT5 returned invalid bid/ask values for spread calculation.")
    return (ask - bid) / instrument.pip_size


def _candle_from_rate(symbol: str, granularity: Timeframe, rate) -> Candle:
    return Candle(
        symbol=symbol,
        timeframe=granularity,
        timestamp=datetime.fromtimestamp(_rate_value(rate, "time"), tz=timezone.utc),
        open=Decimal(str(_rate_value(rate, "open"))),
        high=Decimal(str(_rate_value(rate, "high"))),
        low=Decimal(str(_rate_value(rate, "low"))),
        close=Decimal(str(_rate_value(rate, "close"))),
        volume=Decimal(str(_rate_value(rate, "tick_volume", default=0))),
    )


def _rate_value(rate, key: str, default=None):
    try:
        return rate[key]
    except (KeyError, TypeError, IndexError):
        return getattr(rate, key, default)


def _mt5_timeframe(mt5, granularity: Timeframe):
    mapping = {
        Timeframe.M1: mt5.TIMEFRAME_M1,
        Timeframe.M5: mt5.TIMEFRAME_M5,
        Timeframe.M15: mt5.TIMEFRAME_M15,
        Timeframe.M30: mt5.TIMEFRAME_M30,
        Timeframe.H1: mt5.TIMEFRAME_H1,
        Timeframe.H4: mt5.TIMEFRAME_H4,
        Timeframe.D: mt5.TIMEFRAME_D1,
        Timeframe.W: mt5.TIMEFRAME_W1,
        Timeframe.M: mt5.TIMEFRAME_MN1,
    }
    return mapping[granularity]


def _mt5_last_error(mt5) -> str:
    try:
        return str(mt5.last_error())
    except Exception:
        return "unknown"


def _is_authorization_failed(error: str) -> bool:
    normalized = error.lower()
    return "-6" in normalized or "authorization failed" in normalized


def _initialize_attached_terminal(mt5, path: str, timeout_ms: int) -> bool:
    kwargs = {"timeout": timeout_ms}
    return mt5.initialize(path, **kwargs) if path else mt5.initialize(**kwargs)


def _account_login_matches_config(account_info, expected_login: str) -> bool:
    return str(getattr(account_info, "login", "")).strip() == expected_login.strip()
