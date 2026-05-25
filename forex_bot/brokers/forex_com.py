from forex_bot.brokers.base import BrokerConfigError, MarketSnapshot
from forex_bot.config import BrokerConfig
from forex_bot.models import BrokerEnvironment, Timeframe


class ForexComConfigError(BrokerConfigError):
    pass


class ForexComClient:
    """FOREX.com adapter scaffold.

    FOREX.com REST access can require account enablement and an app key.
    Until we have confirmed credentials and endpoint details for the user's
    account, this adapter fails clearly instead of pretending to fetch data.
    """

    def __init__(self, config: BrokerConfig, timeout_seconds: int = 15) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def get_market_snapshot(self, symbol: str, granularity: Timeframe = Timeframe.H1, count: int = 200) -> MarketSnapshot:
        self._require_read_credentials()
        raise ForexComConfigError(
            "FOREX.com REST adapter is scaffolded but not implemented yet. "
            "Confirm REST API access, app key, and endpoint docs for this account before enabling scans."
        )

    def _require_read_credentials(self) -> None:
        missing = []
        if not self.config.username or self.config.username.startswith("your_"):
            missing.append("FOREX_COM_USERNAME")
        if not self.config.password or self.config.password.startswith("your_"):
            missing.append("FOREX_COM_PASSWORD")
        if not self.config.app_key or self.config.app_key.startswith("your_"):
            missing.append("FOREX_COM_APP_KEY")
        if missing:
            joined = ", ".join(missing)
            raise ForexComConfigError(f"Missing required FOREX.com setting(s): {joined}")

        if self.config.environment == BrokerEnvironment.LIVE:
            raise ForexComConfigError(
                "FOREX.com live mode is not enabled in code yet. Start with demo/read-only once REST access is confirmed."
            )
