from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from forex_bot.config import NewsConfig
from forex_bot.models import NewsProvider
from forex_bot.news.factory import create_market_news_provider
from forex_bot.news.free_sources import AlphaVantageNewsProvider, MarketauxNewsProvider


class NewsProviderTest(unittest.TestCase):
    def test_trading_economics_primary_falls_back_to_alpha_vantage(self):
        config = NewsConfig(
            primary_provider=NewsProvider.TRADING_ECONOMICS,
            fallback_provider=NewsProvider.ALPHA_VANTAGE,
            alpha_vantage_api_key="alpha-key",
        )
        provider = create_market_news_provider(config)

        with patch.object(
            AlphaVantageNewsProvider,
            "_get_json",
            return_value={
                "feed": [
                    {
                        "title": "Dollar steadies before payrolls",
                        "url": "https://example.com/news",
                        "source": "Example News",
                        "time_published": "20260604T143000",
                        "summary": "Markets wait for labor data.",
                        "overall_sentiment_label": "Neutral",
                        "ticker_sentiment": [{"ticker": "EURUSD"}],
                    }
                ]
            },
        ):
            snapshot = provider.get_latest_news(symbols=["EUR_USD"], limit=1)

        self.assertEqual(snapshot.provider, "alpha_vantage")
        self.assertTrue(snapshot.used_fallback)
        self.assertIn("Trading Economics", snapshot.error)
        self.assertEqual(len(snapshot.items), 1)
        self.assertEqual(snapshot.items[0].title, "Dollar steadies before payrolls")
        self.assertEqual(snapshot.items[0].published_at, datetime(2026, 6, 4, 14, 30, tzinfo=timezone.utc))

    def test_marketaux_can_be_selected_as_free_fallback(self):
        config = NewsConfig(
            primary_provider=NewsProvider.TRADING_ECONOMICS,
            fallback_provider=NewsProvider.MARKETAUX,
            marketaux_api_key="marketaux-key",
        )
        provider = create_market_news_provider(config)

        with patch.object(
            MarketauxNewsProvider,
            "_get_json",
            return_value={
                "data": [
                    {
                        "title": "Euro rises after ECB remarks",
                        "url": "https://example.com/euro",
                        "source": "Example Wire",
                        "published_at": "2026-06-04T12:00:00Z",
                        "description": "The euro moved higher.",
                        "entities": [{"symbol": "EUR"}],
                    }
                ]
            },
        ):
            snapshot = provider.get_latest_news(symbols=["EUR"], limit=1)

        self.assertEqual(snapshot.provider, "marketaux")
        self.assertTrue(snapshot.used_fallback)
        self.assertEqual(snapshot.items[0].symbols, ("EUR",))

    def test_free_provider_requires_its_own_key(self):
        config = NewsConfig(
            primary_provider=NewsProvider.ALPHA_VANTAGE,
            fallback_provider=NewsProvider.NONE,
        )
        provider = create_market_news_provider(config)

        snapshot = provider.get_latest_news(symbols=["EUR_USD"], limit=1)

        self.assertEqual(snapshot.provider, "alpha_vantage")
        self.assertFalse(snapshot.used_fallback)
        self.assertEqual(snapshot.items, ())
        self.assertIn("ALPHA_VANTAGE_API_KEY", snapshot.error)

    def test_missing_primary_and_fallback_credentials_records_error(self):
        provider = create_market_news_provider(NewsConfig())

        snapshot = provider.get_latest_news(symbols=["EUR_USD"], limit=1)

        self.assertEqual(snapshot.provider, "alpha_vantage")
        self.assertTrue(snapshot.used_fallback)
        self.assertEqual(snapshot.items, ())
        self.assertIn("TRADING_ECONOMICS_API_KEY", snapshot.error)
        self.assertIn("ALPHA_VANTAGE_API_KEY", snapshot.error)

    def test_none_cannot_be_primary_news_provider(self):
        config = NewsConfig(primary_provider=NewsProvider.NONE)

        with self.assertRaises(ValueError):
            create_market_news_provider(config)


if __name__ == "__main__":
    unittest.main()
