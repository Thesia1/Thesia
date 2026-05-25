import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from forex_bot.config import load_config_from_env
from forex_bot.models import BotMode, BrokerEnvironment


class ConfigTest(unittest.TestCase):
    def test_default_config_uses_watch_and_practice(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config_from_env()

        self.assertEqual(config.mode, BotMode.WATCH)
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
            env_file.write_text("OANDA_ACCOUNT_ID=abc123\nOANDA_TOKEN=secret\n")
            with patch.dict(os.environ, {}, clear=True):
                config = load_config_from_env(env_file)

        self.assertEqual(config.broker.account_id, "abc123")
        self.assertEqual(config.broker.token, "secret")


if __name__ == "__main__":
    unittest.main()
