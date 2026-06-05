import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from forex_bot.config import NewsConfig
from forex_bot.news.base import MarketNewsItem, MarketNewsSnapshot, NewsProviderError


class AlphaVantageNewsProvider:
    provider_name = "alpha_vantage"

    def __init__(self, config: NewsConfig, timeout_seconds: int = 15) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def get_latest_news(self, symbols: list[str] | None = None, limit: int = 10) -> MarketNewsSnapshot:
        self._require_credentials()
        params = {
            "function": "NEWS_SENTIMENT",
            "apikey": self.config.alpha_vantage_api_key,
            "limit": str(limit),
        }
        if symbols:
            params["tickers"] = ",".join(_alpha_vantage_symbol(symbol) for symbol in symbols)

        payload = self._get_json(f"https://www.alphavantage.co/query?{urlencode(params)}")
        rows = payload.get("feed", [])
        if not isinstance(rows, list):
            raise NewsProviderError("Alpha Vantage returned an unexpected news payload")

        items = tuple(_alpha_vantage_item(row) for row in rows[:limit])
        return MarketNewsSnapshot(provider=self.provider_name, used_fallback=False, items=items)

    def _require_credentials(self) -> None:
        token = self.config.alpha_vantage_api_key
        if not token or token.startswith("your_"):
            raise NewsProviderError("Missing required Alpha Vantage setting: ALPHA_VANTAGE_API_KEY")

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise NewsProviderError(f"Alpha Vantage news request failed with HTTP {error.code}") from error
        except URLError as error:
            raise NewsProviderError(f"Alpha Vantage news request failed: {error.reason}") from error


class MarketauxNewsProvider:
    provider_name = "marketaux"

    def __init__(self, config: NewsConfig, timeout_seconds: int = 15) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def get_latest_news(self, symbols: list[str] | None = None, limit: int = 10) -> MarketNewsSnapshot:
        self._require_credentials()
        params = {
            "api_token": self.config.marketaux_api_key,
            "limit": str(limit),
            "language": "en",
        }
        if symbols:
            params["symbols"] = ",".join(symbols)

        payload = self._get_json(f"https://api.marketaux.com/v1/news/all?{urlencode(params)}")
        rows = payload.get("data", [])
        if not isinstance(rows, list):
            raise NewsProviderError("Marketaux returned an unexpected news payload")

        items = tuple(_marketaux_item(row) for row in rows[:limit])
        return MarketNewsSnapshot(provider=self.provider_name, used_fallback=False, items=items)

    def _require_credentials(self) -> None:
        token = self.config.marketaux_api_key
        if not token or token.startswith("your_"):
            raise NewsProviderError("Missing required Marketaux setting: MARKETAUX_API_KEY")

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise NewsProviderError(f"Marketaux news request failed with HTTP {error.code}") from error
        except URLError as error:
            raise NewsProviderError(f"Marketaux news request failed: {error.reason}") from error


def _alpha_vantage_item(row: dict[str, Any]) -> MarketNewsItem:
    ticker_sentiment = row.get("ticker_sentiment", [])
    symbols = tuple(
        item.get("ticker", "")
        for item in ticker_sentiment
        if isinstance(item, dict) and item.get("ticker")
    )
    return MarketNewsItem(
        title=str(row.get("title", "")),
        url=str(row.get("url", "")),
        source=str(row.get("source", "")),
        published_at=_parse_alpha_vantage_time(str(row.get("time_published", ""))),
        summary=str(row.get("summary", "")),
        symbols=symbols,
        sentiment_label=str(row.get("overall_sentiment_label", "")),
    )


def _marketaux_item(row: dict[str, Any]) -> MarketNewsItem:
    entities = row.get("entities", [])
    symbols = tuple(
        item.get("symbol", "")
        for item in entities
        if isinstance(item, dict) and item.get("symbol")
    )
    return MarketNewsItem(
        title=str(row.get("title", "")),
        url=str(row.get("url", "")),
        source=str(row.get("source", "")),
        published_at=_parse_iso_time(str(row.get("published_at", ""))),
        summary=str(row.get("description", "")),
        symbols=symbols,
        sentiment_label="",
    )


def _alpha_vantage_symbol(symbol: str) -> str:
    return symbol.replace("/", "").replace("_", "").upper()


def _parse_alpha_vantage_time(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def _parse_iso_time(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

