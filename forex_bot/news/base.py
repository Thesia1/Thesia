from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class NewsProviderError(ValueError):
    pass


@dataclass(frozen=True)
class MarketNewsItem:
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str = ""
    symbols: tuple[str, ...] = ()
    sentiment_label: str = ""


@dataclass(frozen=True)
class MarketNewsSnapshot:
    provider: str
    used_fallback: bool
    items: tuple[MarketNewsItem, ...]
    error: str = ""


class MarketNewsProvider(Protocol):
    provider_name: str

    def get_latest_news(self, symbols: list[str] | None = None, limit: int = 10) -> MarketNewsSnapshot:
        raise NotImplementedError

