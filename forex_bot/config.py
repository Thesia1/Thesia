from dataclasses import dataclass, field
from decimal import Decimal
from os import environ
from pathlib import Path

from forex_bot.models import AgentProvider, BotMode, BrokerEnvironment, BrokerProvider, ExecutionProvider, NewsProvider


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
class ExecutionConfig:
    provider: ExecutionProvider = ExecutionProvider.NONE
    environment: BrokerEnvironment = BrokerEnvironment.PRACTICE
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""
    order_placement_enabled: bool = False
    idempotency_ledger_path: str = "data/order-ledger.jsonl"
    mt5_deviation_points: int = 20
    mt5_magic: int = 260604


@dataclass(frozen=True)
class NewsConfig:
    primary_provider: NewsProvider = NewsProvider.TRADING_ECONOMICS
    fallback_provider: NewsProvider = NewsProvider.ALPHA_VANTAGE
    trading_economics_api_key: str = ""
    econoday_api_key: str = ""
    alpha_vantage_api_key: str = ""
    marketaux_api_key: str = ""
    blackout_enabled: bool = True
    blackout_events_file: str = ""
    blackout_before_minutes: int = 60
    blackout_after_minutes: int = 30
    blackout_min_impact: str = "high"


@dataclass(frozen=True)
class AgentConfig:
    primary_provider: AgentProvider = AgentProvider.ANTHROPIC
    fallback_provider: AgentProvider = AgentProvider.OPENROUTER
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    openai_model: str = "gpt-5-mini"
    openrouter_model: str = "openrouter/auto"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class BotConfig:
    mode: BotMode = BotMode.WATCH
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    news: NewsConfig = field(default_factory=NewsConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    explicit_live_enabled: bool = False

    def validate(self) -> None:
        if self.mode == BotMode.AUTONOMOUS_LIVE and not self.explicit_live_enabled:
            raise ValueError("AUTONOMOUS_LIVE requires explicit live enablement")
        if self.mode == BotMode.AUTONOMOUS_LIVE and self.execution.environment != BrokerEnvironment.LIVE:
            raise ValueError("AUTONOMOUS_LIVE requires live execution environment")
        if self.mode == BotMode.AUTONOMOUS_LIVE and self.execution.provider == ExecutionProvider.NONE:
            raise ValueError("AUTONOMOUS_LIVE requires an execution provider")


def load_config_from_env(env_file: str | Path | None = ".env") -> BotConfig:
    values = _load_env_values(env_file)

    mode = BotMode(_get_config_value(values, "THESIA_MODE", BotMode.WATCH.value))
    market_data_provider = BrokerProvider(
        _get_config_value(values, "MARKET_DATA_PROVIDER", _get_config_value(values, "BROKER_PROVIDER", BrokerProvider.OANDA.value))
    )
    market_data_environment = BrokerEnvironment(
        _get_config_value(values, "MARKET_DATA_ENVIRONMENT", _get_config_value(values, "BROKER_ENVIRONMENT", _legacy_environment_default(values)))
    )
    execution_provider = ExecutionProvider(_get_config_value(values, "EXECUTION_PROVIDER", _execution_provider_default(values)))
    execution_environment = BrokerEnvironment(
        _get_config_value(values, "EXECUTION_ENVIRONMENT", BrokerEnvironment.PRACTICE.value)
    )
    news_primary = NewsProvider(_get_config_value(values, "NEWS_PRIMARY_PROVIDER", NewsProvider.TRADING_ECONOMICS.value))
    news_fallback = NewsProvider(_get_config_value(values, "NEWS_FALLBACK_PROVIDER", NewsProvider.ALPHA_VANTAGE.value))
    agent_primary = AgentProvider(_get_config_value(values, "AGENT_PRIMARY_PROVIDER", AgentProvider.ANTHROPIC.value))
    agent_fallback = AgentProvider(_get_config_value(values, "AGENT_FALLBACK_PROVIDER", AgentProvider.OPENROUTER.value))
    explicit_live_enabled = _get_config_value(values, "THESIA_ENABLE_LIVE", "").lower() == "true"

    config = BotConfig(
        mode=mode,
        broker=BrokerConfig(
            provider=market_data_provider,
            environment=market_data_environment,
            account_id=_get_config_value(values, "OANDA_ACCOUNT_ID", ""),
            token=_get_config_value(values, "OANDA_TOKEN", ""),
            username=_get_config_value(values, "FOREX_COM_USERNAME", ""),
            password=_get_config_value(values, "FOREX_COM_PASSWORD", ""),
            app_key=_get_config_value(values, "FOREX_COM_APP_KEY", ""),
        ),
        execution=ExecutionConfig(
            provider=execution_provider,
            environment=execution_environment,
            mt5_login=_get_config_value(values, "MT5_LOGIN", ""),
            mt5_password=_get_config_value(values, "MT5_PASSWORD", ""),
            mt5_server=_get_config_value(values, "MT5_SERVER", ""),
            mt5_path=_get_config_value(values, "MT5_PATH", ""),
            order_placement_enabled=_get_config_value(values, "EXECUTION_ENABLE_ORDER_PLACEMENT", "false").lower() == "true",
            idempotency_ledger_path=_get_config_value(values, "EXECUTION_IDEMPOTENCY_LEDGER_PATH", "data/order-ledger.jsonl"),
            mt5_deviation_points=int(_get_config_value(values, "MT5_DEVIATION_POINTS", "20")),
            mt5_magic=int(_get_config_value(values, "MT5_MAGIC", "260604")),
        ),
        risk=RiskConfig(
            risk_percent=Decimal(_get_config_value(values, "THESIA_RISK_PERCENT", "0.0025")),
            max_daily_loss_percent=Decimal(_get_config_value(values, "THESIA_MAX_DAILY_LOSS_PERCENT", "0.02")),
            max_weekly_loss_percent=Decimal(_get_config_value(values, "THESIA_MAX_WEEKLY_LOSS_PERCENT", "0.05")),
        ),
        news=NewsConfig(
            primary_provider=news_primary,
            fallback_provider=news_fallback,
            trading_economics_api_key=_get_config_value(values, "TRADING_ECONOMICS_API_KEY", ""),
            econoday_api_key=_get_config_value(values, "ECONODAY_API_KEY", ""),
            alpha_vantage_api_key=_get_config_value(values, "ALPHA_VANTAGE_API_KEY", ""),
            marketaux_api_key=_get_config_value(values, "MARKETAUX_API_KEY", ""),
            blackout_enabled=_get_config_value(values, "NEWS_BLACKOUT_ENABLED", "true").lower() == "true",
            blackout_events_file=_get_config_value(values, "NEWS_BLACKOUT_EVENTS_FILE", ""),
            blackout_before_minutes=int(_get_config_value(values, "NEWS_BLACKOUT_BEFORE_MINUTES", "60")),
            blackout_after_minutes=int(_get_config_value(values, "NEWS_BLACKOUT_AFTER_MINUTES", "30")),
            blackout_min_impact=_get_config_value(values, "NEWS_BLACKOUT_MIN_IMPACT", "high"),
        ),
        agent=AgentConfig(
            primary_provider=agent_primary,
            fallback_provider=agent_fallback,
            anthropic_api_key=_get_config_value(values, "ANTHROPIC_API_KEY", ""),
            openai_api_key=_get_config_value(values, "OPENAI_API_KEY", ""),
            openrouter_api_key=_get_config_value(values, "OPENROUTER_API_KEY", ""),
            anthropic_model=_get_config_value(values, "ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            openai_model=_get_config_value(values, "OPENAI_MODEL", "gpt-5-mini"),
            openrouter_model=_get_config_value(values, "OPENROUTER_MODEL", "openrouter/auto"),
            openrouter_base_url=_get_config_value(values, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
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


def _execution_provider_default(values: dict[str, str]) -> str:
    mt5_keys = ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")
    if any(_get_config_value(values, key, "").strip() and not _get_config_value(values, key, "").startswith("your_") for key in mt5_keys):
        return ExecutionProvider.MT5.value
    return ExecutionProvider.NONE.value
