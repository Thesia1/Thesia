import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from forex_bot.config import BrokerConfig
from forex_bot.models import Candle, InstrumentSpec, Timeframe


class OandaConfigError(ValueError):
    pass


@dataclass(frozen=True)
class OandaMarketSnapshot:
    candles: list[Candle]
    instrument: InstrumentSpec
    spread_pips: Decimal


class OandaClient:
    def __init__(self, config: BrokerConfig, timeout_seconds: int = 15) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def get_market_snapshot(self, symbol: str, granularity: Timeframe = Timeframe.H1, count: int = 200) -> OandaMarketSnapshot:
        self._require_read_credentials()
        candles = self.get_candles(symbol=symbol, granularity=granularity, count=count)
        spread_pips = self.get_spread_pips(symbol)
        return OandaMarketSnapshot(
            candles=candles,
            instrument=instrument_spec_for(symbol),
            spread_pips=spread_pips,
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
                "Authorization": f"Bearer {self.config.token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _require_read_credentials(self) -> None:
        missing = []
        if not self.config.account_id:
            missing.append("OANDA_ACCOUNT_ID")
        if not self.config.token:
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
