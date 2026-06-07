import unittest

from forex_bot.brokers.factory import create_broker_client
from forex_bot.brokers.forex_com import ForexComClient
from forex_bot.brokers.mt5 import Mt5MarketDataClient
from forex_bot.brokers.oanda import OandaClient
from forex_bot.config import BrokerConfig, ExecutionConfig
from forex_bot.models import BrokerProvider


class BrokerFactoryTest(unittest.TestCase):
    def test_creates_oanda_client(self):
        client = create_broker_client(BrokerConfig(provider=BrokerProvider.OANDA))

        self.assertIsInstance(client, OandaClient)

    def test_creates_forex_com_client(self):
        client = create_broker_client(BrokerConfig(provider=BrokerProvider.FOREX_COM))

        self.assertIsInstance(client, ForexComClient)

    def test_creates_mt5_market_data_client(self):
        client = create_broker_client(
            BrokerConfig(provider=BrokerProvider.MT5),
            ExecutionConfig(mt5_login="12345", mt5_password="secret", mt5_server="Deriv-Live"),
        )

        self.assertIsInstance(client, Mt5MarketDataClient)

    def test_mt5_market_data_requires_execution_config(self):
        with self.assertRaises(ValueError):
            create_broker_client(BrokerConfig(provider=BrokerProvider.MT5))


if __name__ == "__main__":
    unittest.main()
