from forex_bot.config import NewsConfig
from forex_bot.models import NewsProvider
from forex_bot.news.base import MarketNewsProvider, MarketNewsSnapshot, NewsProviderError
from forex_bot.news.free_sources import AlphaVantageNewsProvider, MarketauxNewsProvider
from forex_bot.news.trading_economics import TradingEconomicsNewsProvider


class FallbackMarketNewsProvider:
    provider_name = "fallback_chain"

    def __init__(self, primary: MarketNewsProvider, fallback: MarketNewsProvider | None) -> None:
        self.primary = primary
        self.fallback = fallback

    def get_latest_news(self, symbols: list[str] | None = None, limit: int = 10) -> MarketNewsSnapshot:
        try:
            return self.primary.get_latest_news(symbols=symbols, limit=limit)
        except NewsProviderError as error:
            if self.fallback is None:
                return MarketNewsSnapshot(
                    provider=self.primary.provider_name,
                    used_fallback=False,
                    items=(),
                    error=str(error),
                )

            try:
                snapshot = self.fallback.get_latest_news(symbols=symbols, limit=limit)
            except NewsProviderError as fallback_error:
                return MarketNewsSnapshot(
                    provider=self.fallback.provider_name,
                    used_fallback=True,
                    items=(),
                    error=f"{error}; fallback failed: {fallback_error}",
                )
            return MarketNewsSnapshot(
                provider=snapshot.provider,
                used_fallback=True,
                items=snapshot.items,
                error=str(error),
            )


def create_market_news_provider(config: NewsConfig) -> MarketNewsProvider:
    primary = _create_provider(config.primary_provider, config)
    fallback = None if config.fallback_provider == NewsProvider.NONE else _create_provider(config.fallback_provider, config)
    return FallbackMarketNewsProvider(primary, fallback)


def _create_provider(provider: NewsProvider, config: NewsConfig) -> MarketNewsProvider:
    if provider == NewsProvider.TRADING_ECONOMICS:
        return TradingEconomicsNewsProvider(config)
    if provider == NewsProvider.ALPHA_VANTAGE:
        return AlphaVantageNewsProvider(config)
    if provider == NewsProvider.MARKETAUX:
        return MarketauxNewsProvider(config)
    if provider == NewsProvider.NONE:
        raise ValueError("News provider 'none' can only be used as a fallback setting")
    raise ValueError(f"Unsupported news provider: {provider}")
