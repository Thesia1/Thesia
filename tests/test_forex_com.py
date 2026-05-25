import unittest

from forex_bot.brokers.forex_com import ForexComClient, ForexComConfigError
from forex_bot.config import BrokerConfig
from forex_bot.models import BrokerProvider


class ForexComClientTest(unittest.TestCase):
    def test_requires_forex_com_credentials(self):
        client = ForexComClient(BrokerConfig(provider=BrokerProvider.FOREX_COM))

        with self.assertRaises(ForexComConfigError) as context:
            client.get_market_snapshot("EUR_USD")

        self.assertIn("FOREX_COM_USERNAME", str(context.exception))

    def test_scaffold_fails_clearly_after_credentials_exist(self):
        client = ForexComClient(
            BrokerConfig(
                provider=BrokerProvider.FOREX_COM,
                username="user",
                password="pass",
                app_key="key",
            )
        )

        with self.assertRaises(ForexComConfigError) as context:
            client.get_market_snapshot("EUR_USD")

        self.assertIn("scaffolded but not implemented", str(context.exception))


if __name__ == "__main__":
    unittest.main()

