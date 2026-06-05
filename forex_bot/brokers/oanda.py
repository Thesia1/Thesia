import json
import ssl
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
from os import environ
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from forex_bot.config import BrokerConfig
from forex_bot.brokers.base import BrokerConfigError, MarketSnapshot
from forex_bot.models import Candle, InstrumentSpec, Timeframe


class OandaConfigError(BrokerConfigError):
    pass


class OandaConnectionError(BrokerConfigError):
    pass


@dataclass(frozen=True)
class OandaDiagnostics:
    environment: str
    base_url: str
    configured_account_id: str
    token_present: bool
    token_length: int
    token_has_bearer_prefix: bool
    token_has_whitespace: bool
    auth_ok: bool
    account_visible: bool
    candles_ok: bool
    pricing_ok: bool
    visible_account_ids: tuple[str, ...]
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class OandaClient:
    def __init__(self, config: BrokerConfig, timeout_seconds: int = 15) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.ssl_context = _create_ssl_context()

    def get_market_snapshot(self, symbol: str, granularity: Timeframe = Timeframe.H1, count: int = 200) -> MarketSnapshot:
        self._require_read_credentials()
        candles = self.get_candles(symbol=symbol, granularity=granularity, count=count)
        spread_pips = self.get_spread_pips(symbol)
        return MarketSnapshot(
            candles=candles,
            instrument=instrument_spec_for(symbol),
            spread_pips=spread_pips,
            provider="oanda",
        )

    def diagnose_read_access(self, symbol: str = "EUR_USD", granularity: Timeframe = Timeframe.H1) -> OandaDiagnostics:
        token = _clean_token(self.config.token)
        visible_account_ids: tuple[str, ...] = ()
        auth_ok = False
        account_visible = False
        candles_ok = False
        pricing_ok = False
        error = ""

        try:
            self._require_read_credentials()
            accounts_payload = self._get_json("/v3/accounts")
            auth_ok = True
            visible_account_ids = tuple(
                _mask_secret(str(account.get("id", "")))
                for account in accounts_payload.get("accounts", [])
                if isinstance(account, dict) and account.get("id")
            )
            account_visible = any(
                str(account.get("id", "")) == self.config.account_id
                for account in accounts_payload.get("accounts", [])
                if isinstance(account, dict)
            )

            self.get_candles(symbol=symbol, granularity=granularity, count=1)
            candles_ok = True

            self.get_spread_pips(symbol)
            pricing_ok = True
        except BrokerConfigError as broker_error:
            error = str(broker_error)
        except RuntimeError as runtime_error:
            error = str(runtime_error)

        return OandaDiagnostics(
            environment=self.config.environment.value,
            base_url=self.config.base_url,
            configured_account_id=_mask_secret(self.config.account_id),
            token_present=bool(token),
            token_length=len(token),
            token_has_bearer_prefix=self.config.token.strip().lower().startswith("bearer "),
            token_has_whitespace=any(ch.isspace() for ch in token),
            auth_ok=auth_ok,
            account_visible=account_visible,
            candles_ok=candles_ok,
            pricing_ok=pricing_ok,
            visible_account_ids=visible_account_ids,
            error=error,
        )

    def get_candles(self, symbol: str, granularity: Timeframe = Timeframe.H1, count: int = 200) -> list[Candle]:
        instrument = to_oanda_instrument(symbol)
        params = urlencode({
            "count": str(count),
            "granularity": granularity.value,
            "price": "M",
        })
        payload = self._get_json(f"/v3/instruments/{instrument}/candles?{params}")
        candles: list[Candle] = []
        for row in payload.get("candles", []):
            if not row.get("complete", False):
                continue
            mid = row["mid"]
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=granularity,
                    timestamp=_parse_oanda_time(row["time"]),
                    open=Decimal(mid["o"]),
                    high=Decimal(mid["h"]),
                    low=Decimal(mid["l"]),
                    close=Decimal(mid["c"]),
                    volume=Decimal(str(row.get("volume", "0"))),
                )
            )
        return candles

    def get_spread_pips(self, symbol: str) -> Decimal:
        instrument = to_oanda_instrument(symbol)
        params = urlencode({"instruments": instrument})
        payload = self._get_json(f"/v3/accounts/{self.config.account_id}/pricing?{params}")
        prices = payload.get("prices", [])
        if not prices:
            raise RuntimeError(f"OANDA did not return pricing for {symbol}")

        price = prices[0]
        bid = Decimal(price["bids"][0]["price"])
        ask = Decimal(price["asks"][0]["price"])
        spec = instrument_spec_for(symbol)
        return (ask - bid) / spec.pip_size

    def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {_clean_token(self.config.token)}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds, context=self.ssl_context) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise OandaConnectionError(_format_http_error(error, self.config)) from error
        except URLError as error:
            raise OandaConnectionError(_format_url_error(error, self.config)) from error

    def _require_read_credentials(self) -> None:
        missing = []
        if not self.config.account_id or self.config.account_id.startswith("your_"):
            missing.append("OANDA_ACCOUNT_ID")
        token = _clean_token(self.config.token)
        if not token or token.startswith("your_"):
            missing.append("OANDA_TOKEN")
        if missing:
            joined = ", ".join(missing)
            raise OandaConfigError(f"Missing required OANDA setting(s): {joined}")


def to_oanda_instrument(symbol: str) -> str:
    return symbol.replace("/", "_").upper()


def instrument_spec_for(symbol: str) -> InstrumentSpec:
    normalized = to_oanda_instrument(symbol)
    pip_size = Decimal("0.01") if normalized.endswith("_JPY") else Decimal("0.0001")
    return InstrumentSpec(
        symbol=normalized,
        pip_size=pip_size,
        pip_value_per_unit=pip_size,
        min_units=Decimal("1"),
        max_units=Decimal("100000"),
        unit_step=Decimal("1"),
        margin_rate=Decimal("0.0333"),
        max_spread_pips=Decimal("2"),
    )


def _parse_oanda_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _create_ssl_context() -> ssl.SSLContext:
    cafile = environ.get("THESIA_CA_BUNDLE") or environ.get("SSL_CERT_FILE")
    if cafile and Path(cafile).exists():
        return ssl.create_default_context(cafile=cafile)

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _format_url_error(error: URLError, config: BrokerConfig) -> str:
    reason = str(error.reason)
    if "CERTIFICATE_VERIFY_FAILED" in reason:
        return (
            "OANDA API request failed: SSL certificate verification failed. "
            "The client now tries certifi automatically; if this persists, set THESIA_CA_BUNDLE "
            "or SSL_CERT_FILE to a valid CA bundle path."
        )
    if "nodename nor servname provided" in reason or "Name or service not known" in reason:
        return (
            "OANDA API request failed: DNS/network lookup failed. "
            f"Check internet access, DNS, VPN/firewall settings, and that {config.base_url} is reachable."
        )
    return f"OANDA API request failed: {error.reason}"


def _format_http_error(error: HTTPError, config: BrokerConfig) -> str:
    if error.code == 401:
        return (
            "OANDA API request failed with HTTP 401: unauthorized. "
            f"The bearer token was rejected by the {config.environment.value} API endpoint. "
            "Regenerate or re-copy OANDA_TOKEN from the matching OANDA practice/live portal, "
            "and make sure BROKER_ENVIRONMENT points to that same account type."
        )
    if error.code == 403:
        return (
            "OANDA API request failed with HTTP 403: forbidden. "
            "The token may be valid but not allowed to access this account or endpoint."
        )
    if error.code == 404:
        return (
            "OANDA API request failed with HTTP 404: not found. "
            "Check the account id, instrument symbol, and broker environment."
        )
    return f"OANDA API request failed with HTTP {error.code}"


def _clean_token(token: str) -> str:
    value = token.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"
