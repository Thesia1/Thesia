import unittest

from forex_bot.brokers.factory import create_broker_client
from forex_bot.brokers.forex_com import ForexComClient
from forex_bot.brokers.oanda import OandaClient
from forex_bot.config import BrokerConfig
from forex_bot.models import BrokerProvider


class BrokerFactoryTest(unittest.TestCase):
    def test_creates_oanda_client(self):
        client = create_broker_client(BrokerConfig(provider=BrokerProvider.OANDA))

        self.assertIsInstance(client, OandaClient)

    def test_creates_forex_com_client(self):
        client = create_broker_client(BrokerConfig(provider=BrokerProvider.FOREX_COM))

        self.assertIsInstance(client, ForexComClient)


if __name__ == "__main__":
    unittest.main()
