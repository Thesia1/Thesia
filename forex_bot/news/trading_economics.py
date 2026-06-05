from forex_bot.config import NewsConfig
from forex_bot.news.base import MarketNewsSnapshot, NewsProviderError


class TradingEconomicsNewsProvider:
    provider_name = "trading_economics"

    def __init__(self, config: NewsConfig) -> None:
        self.config = config

    def get_latest_news(self, symbols: list[str] | None = None, limit: int = 10) -> MarketNewsSnapshot:
        self._require_credentials()
        raise NewsProviderError(
            "Trading Economics news/calendar adapter is configured as primary but is not implemented yet. "
            "Use fallback market news for watch-mode context only until official calendar blackout support is wired."
        )

    def _require_credentials(self) -> None:
        token = self.config.trading_economics_api_key
        if not token or token.startswith("your_"):
            raise NewsProviderError("Missing required Trading Economics setting: TRADING_ECONOMICS_API_KEY")

