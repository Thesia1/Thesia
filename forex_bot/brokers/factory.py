from forex_bot.brokers.base import BrokerClient
from forex_bot.brokers.forex_com import ForexComClient
from forex_bot.brokers.oanda import OandaClient
from forex_bot.config import BrokerConfig
from forex_bot.models import BrokerProvider


def create_broker_client(config: BrokerConfig) -> BrokerClient:
    if config.provider == BrokerProvider.OANDA:
        return OandaClient(config)
    if config.provider == BrokerProvider.FOREX_COM:
        return ForexComClient(config)
    raise ValueError(f"Unsupported broker provider: {config.provider}")
