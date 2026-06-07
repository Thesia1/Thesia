import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from forex_bot.config import load_config_from_env
from forex_bot.models import AgentProvider, BotMode, BrokerEnvironment, BrokerProvider, ExecutionProvider, NewsProvider


class ConfigTest(unittest.TestCase):
    def test_default_config_uses_watch_and_practice(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config_from_env(None)

        self.assertEqual(config.mode, BotMode.WATCH)
        self.assertEqual(config.broker.provider, BrokerProvider.OANDA)
        self.assertEqual(config.broker.environment, BrokerEnvironment.PRACTICE)
        self.assertEqual(config.execution.provider, ExecutionProvider.NONE)

    def test_live_autonomy_requires_explicit_enablement(self):
        with patch.dict(
            os.environ,
            {"THESIA_MODE": "AUTONOMOUS_LIVE", "EXECUTION_ENVIRONMENT": "live"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                load_config_from_env()

    def test_config_loads_legacy_broker_provider_as_market_data_provider(self):
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("BROKER_PROVIDER=forex_com\nFOREX_COM_USERNAME=user\nFOREX_COM_PASSWORD=pass\nFOREX_COM_APP_KEY=key\n")
            with patch.dict(os.environ, {}, clear=True):
                config = load_config_from_env(env_file)

        self.assertEqual(config.broker.provider, BrokerProvider.FOREX_COM)
        self.assertEqual(config.broker.username, "user")
        self.assertEqual(config.broker.password, "pass")
        self.assertEqual(config.broker.app_key, "key")

    def test_config_loads_oanda_market_data_and_mt5_execution(self):
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "MARKET_DATA_PROVIDER=oanda",
                        "MARKET_DATA_ENVIRONMENT=live",
                        "EXECUTION_PROVIDER=mt5",
                        "EXECUTION_ENVIRONMENT=practice",
                        "MT5_LOGIN=12345",
                        "MT5_PASSWORD=secret",
                        "MT5_SERVER=Deriv-Demo",
                        "EXECUTION_ENABLE_ORDER_PLACEMENT=true",
                        "EXECUTION_IDEMPOTENCY_LEDGER_PATH=data/live-orders.jsonl",
                        "MT5_DEVIATION_POINTS=30",
                        "MT5_MAGIC=123456",
                        "MT5_TIMEOUT_MS=60000",
                    ]
                )
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_config_from_env(env_file)

        self.assertEqual(config.broker.provider, BrokerProvider.OANDA)
        self.assertEqual(config.broker.environment, BrokerEnvironment.LIVE)
        self.assertEqual(config.execution.provider, ExecutionProvider.MT5)
        self.assertEqual(config.execution.environment, BrokerEnvironment.PRACTICE)
        self.assertEqual(config.execution.mt5_login, "12345")
        self.assertEqual(config.execution.mt5_server, "Deriv-Demo")
        self.assertTrue(config.execution.order_placement_enabled)
        self.assertEqual(config.execution.idempotency_ledger_path, "data/live-orders.jsonl")
        self.assertEqual(config.execution.mt5_deviation_points, 30)
        self.assertEqual(config.execution.mt5_magic, 123456)
        self.assertEqual(config.execution.mt5_timeout_ms, 60000)

    def test_config_loads_mt5_market_data_for_deriv_synthetics(self):
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "MARKET_DATA_PROVIDER=mt5",
                        "MARKET_DATA_ENVIRONMENT=live",
                        "EXECUTION_PROVIDER=mt5",
                        "EXECUTION_ENVIRONMENT=live",
                        "MT5_LOGIN=12345",
                        "MT5_PASSWORD=secret",
                        "MT5_SERVER=DerivSVG-Server",
                    ]
                )
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_config_from_env(env_file)

        self.assertEqual(config.broker.provider, BrokerProvider.MT5)
        self.assertEqual(config.broker.environment, BrokerEnvironment.LIVE)
        self.assertEqual(config.execution.provider, ExecutionProvider.MT5)
        self.assertEqual(config.execution.environment, BrokerEnvironment.LIVE)

    def test_mt5_execution_provider_is_inferred_from_mt5_credentials(self):
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "BROKER_ENVIRONMENT=live",
                        "MT5_LOGIN=12345",
                        "MT5_PASSWORD=secret",
                        "MT5_SERVER=Deriv-Demo",
                    ]
                )
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_config_from_env(env_file)

        self.assertEqual(config.broker.environment, BrokerEnvironment.LIVE)
        self.assertEqual(config.execution.provider, ExecutionProvider.MT5)
        self.assertEqual(config.execution.environment, BrokerEnvironment.PRACTICE)

    def test_legacy_oanda_environment_still_works(self):
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("OANDA_ENVIRONMENT=live\n")
            with patch.dict(os.environ, {}, clear=True):
                config = load_config_from_env(env_file)

        self.assertEqual(config.broker.environment, BrokerEnvironment.LIVE)

    def test_news_provider_config_keeps_trading_economics_primary_with_free_fallback(self):
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "NEWS_FALLBACK_PROVIDER=marketaux",
                        "MARKETAUX_API_KEY=marketaux-key",
                        "NEWS_BLACKOUT_EVENTS_FILE=/tmp/calendar.json",
                        "NEWS_BLACKOUT_BEFORE_MINUTES=90",
                        "NEWS_BLACKOUT_AFTER_MINUTES=45",
                    ]
                )
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_config_from_env(env_file)

        self.assertEqual(config.news.primary_provider, NewsProvider.TRADING_ECONOMICS)
        self.assertEqual(config.news.fallback_provider, NewsProvider.MARKETAUX)
        self.assertEqual(config.news.marketaux_api_key, "marketaux-key")
        self.assertTrue(config.news.blackout_enabled)
        self.assertEqual(config.news.blackout_events_file, "/tmp/calendar.json")
        self.assertEqual(config.news.blackout_before_minutes, 90)
        self.assertEqual(config.news.blackout_after_minutes, 45)

    def test_agent_config_keeps_anthropic_primary_with_openrouter_fallback(self):
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("OPENROUTER_API_KEY=openrouter-key\nOPENROUTER_MODEL=openrouter/auto\n")
            with patch.dict(os.environ, {}, clear=True):
                config = load_config_from_env(env_file)

        self.assertEqual(config.agent.primary_provider, AgentProvider.ANTHROPIC)
        self.assertEqual(config.agent.fallback_provider, AgentProvider.OPENROUTER)
        self.assertEqual(config.agent.openrouter_api_key, "openrouter-key")
        self.assertEqual(config.agent.openrouter_model, "openrouter/auto")


if __name__ == "__main__":
    unittest.main()
