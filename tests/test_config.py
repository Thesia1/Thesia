import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from forex_bot.config import load_config_from_env
from forex_bot.models import BotMode, BrokerEnvironment, BrokerProvider


class ConfigTest(unittest.TestCase):
    def test_default_config_uses_watch_and_practice(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config_from_env()

        self.assertEqual(config.mode, BotMode.WATCH)
        self.assertEqual(config.broker.provider, BrokerProvider.OANDA)
        self.assertEqual(config.broker.environment, BrokerEnvironment.PRACTICE)

    def test_live_autonomy_requires_explicit_enablement(self):
        with patch.dict(
            os.environ,
            {"THESIA_MODE": "AUTONOMOUS_LIVE", "OANDA_ENVIRONMENT": "live"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                load_config_from_env()

    def test_config_loads_env_file_without_requiring_shell_exports(self):
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("BROKER_PROVIDER=forex_com\nFOREX_COM_USERNAME=user\nFOREX_COM_PASSWORD=pass\nFOREX_COM_APP_KEY=key\n")
            with patch.dict(os.environ, {}, clear=True):
                config = load_config_from_env(env_file)

        self.assertEqual(config.broker.provider, BrokerProvider.FOREX_COM)
        self.assertEqual(config.broker.username, "user")
        self.assertEqual(config.broker.password, "pass")
        self.assertEqual(config.broker.app_key, "key")

    def test_legacy_oanda_environment_still_works(self):
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("OANDA_ENVIRONMENT=live\n")
            with patch.dict(os.environ, {}, clear=True):
                config = load_config_from_env(env_file)

        self.assertEqual(config.broker.environment, BrokerEnvironment.LIVE)


if __name__ == "__main__":
    unittest.main()
