from dataclasses import dataclass, field
from decimal import Decimal
from os import environ

from forex_bot.models import BotMode, BrokerEnvironment


@dataclass(frozen=True)
class BrokerConfig:
    environment: BrokerEnvironment = BrokerEnvironment.PRACTICE
    account_id: str = ""
    token: str = ""
    practice_url: str = "https://api-fxpractice.oanda.com"
    live_url: str = "https://api-fxtrade.oanda.com"

    @property
    def base_url(self) -> str:
        if self.environment == BrokerEnvironment.LIVE:
            return self.live_url
        return self.practice_url


@dataclass(frozen=True)
class RiskConfig:
    risk_percent: Decimal = Decimal("0.0025")
    max_daily_loss_percent: Decimal = Decimal("0.02")
    max_weekly_loss_percent: Decimal = Decimal("0.05")


@dataclass(frozen=True)
class BotConfig:
    mode: BotMode = BotMode.WATCH
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    explicit_live_enabled: bool = False

    def validate(self) -> None:
        if self.mode == BotMode.AUTONOMOUS_LIVE and not self.explicit_live_enabled:
            raise ValueError("AUTONOMOUS_LIVE requires explicit live enablement")
        if self.mode == BotMode.AUTONOMOUS_LIVE and self.broker.environment != BrokerEnvironment.LIVE:
            raise ValueError("AUTONOMOUS_LIVE requires live broker environment")


def load_config_from_env() -> BotConfig:
    mode = BotMode(environ.get("THESIA_MODE", BotMode.WATCH.value))
    environment = BrokerEnvironment(environ.get("OANDA_ENVIRONMENT", BrokerEnvironment.PRACTICE.value))
    explicit_live_enabled = environ.get("THESIA_ENABLE_LIVE", "").lower() == "true"

    config = BotConfig(
        mode=mode,
        broker=BrokerConfig(
            environment=environment,
            account_id=environ.get("OANDA_ACCOUNT_ID", ""),
            token=environ.get("OANDA_TOKEN", ""),
        ),
        risk=RiskConfig(
            risk_percent=Decimal(environ.get("THESIA_RISK_PERCENT", "0.0025")),
            max_daily_loss_percent=Decimal(environ.get("THESIA_MAX_DAILY_LOSS_PERCENT", "0.02")),
            max_weekly_loss_percent=Decimal(environ.get("THESIA_MAX_WEEKLY_LOSS_PERCENT", "0.05")),
        ),
        explicit_live_enabled=explicit_live_enabled,
    )
    config.validate()
    return config
