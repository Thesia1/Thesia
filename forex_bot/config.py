from dataclasses import dataclass, field
from decimal import Decimal
from os import environ
from pathlib import Path

from forex_bot.models import BotMode, BrokerEnvironment, BrokerProvider


@dataclass(frozen=True)
class BrokerConfig:
    provider: BrokerProvider = BrokerProvider.OANDA
    environment: BrokerEnvironment = BrokerEnvironment.PRACTICE
    account_id: str = ""
    token: str = ""
    username: str = ""
    password: str = ""
    app_key: str = ""
    practice_url: str = "https://api-fxpractice.oanda.com"
    live_url: str = "https://api-fxtrade.oanda.com"
    forex_com_demo_url: str = "https://ciapi.cityindex.com/tradingapi"
    forex_com_live_url: str = "https://ciapi.cityindex.com/tradingapi"

    @property
    def base_url(self) -> str:
        if self.provider == BrokerProvider.FOREX_COM:
            if self.environment == BrokerEnvironment.LIVE:
                return self.forex_com_live_url
            return self.forex_com_demo_url
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


def load_config_from_env(env_file: str | Path | None = ".env") -> BotConfig:
    values = _load_env_values(env_file)

    mode = BotMode(_get_config_value(values, "THESIA_MODE", BotMode.WATCH.value))
    provider = BrokerProvider(_get_config_value(values, "BROKER_PROVIDER", BrokerProvider.OANDA.value))
    environment = BrokerEnvironment(_get_config_value(values, "BROKER_ENVIRONMENT", _legacy_environment_default(values)))
    explicit_live_enabled = _get_config_value(values, "THESIA_ENABLE_LIVE", "").lower() == "true"

    config = BotConfig(
        mode=mode,
        broker=BrokerConfig(
            provider=provider,
            environment=environment,
            account_id=_get_config_value(values, "OANDA_ACCOUNT_ID", ""),
            token=_get_config_value(values, "OANDA_TOKEN", ""),
            username=_get_config_value(values, "FOREX_COM_USERNAME", ""),
            password=_get_config_value(values, "FOREX_COM_PASSWORD", ""),
            app_key=_get_config_value(values, "FOREX_COM_APP_KEY", ""),
        ),
        risk=RiskConfig(
            risk_percent=Decimal(_get_config_value(values, "THESIA_RISK_PERCENT", "0.0025")),
            max_daily_loss_percent=Decimal(_get_config_value(values, "THESIA_MAX_DAILY_LOSS_PERCENT", "0.02")),
            max_weekly_loss_percent=Decimal(_get_config_value(values, "THESIA_MAX_WEEKLY_LOSS_PERCENT", "0.05")),
        ),
        explicit_live_enabled=explicit_live_enabled,
    )
    config.validate()
    return config


def _get_config_value(values: dict[str, str], key: str, default: str) -> str:
    return environ.get(key, values.get(key, default))


def _load_env_values(env_file: str | Path | None) -> dict[str, str]:
    if env_file is None:
        return {}

    path = Path(env_file)
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _legacy_environment_default(values: dict[str, str]) -> str:
    return _get_config_value(values, "OANDA_ENVIRONMENT", BrokerEnvironment.PRACTICE.value)
