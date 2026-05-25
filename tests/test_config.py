import os
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


if __name__ == "__main__":
    unittest.main()

