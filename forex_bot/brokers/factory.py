from forex_bot.brokers.base import BrokerClient
from forex_bot.brokers.forex_com import ForexComClient
from forex_bot.brokers.mt5 import Mt5MarketDataClient
from forex_bot.brokers.oanda import OandaClient
from forex_bot.config import BrokerConfig, ExecutionConfig
from forex_bot.models import BrokerProvider


def create_broker_client(config: BrokerConfig, execution_config: ExecutionConfig | None = None) -> BrokerClient:
    if config.provider == BrokerProvider.OANDA:
        return OandaClient(config)
    if config.provider == BrokerProvider.FOREX_COM:
        return ForexComClient(config)
    if config.provider == BrokerProvider.MT5:
        if execution_config is None:
            raise ValueError("MT5 market data requires execution MT5 configuration.")
        return Mt5MarketDataClient(execution_config)
    raise ValueError(f"Unsupported broker provider: {config.provider}")
