import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from sys import stderr, exit

from forex_bot.brokers.base import BrokerConfigError
from forex_bot.brokers.factory import create_broker_client
from forex_bot.brokers.oanda import instrument_spec_for, to_oanda_instrument
from forex_bot.config import load_config_from_env
from forex_bot.fixtures import load_fixture_candles
from forex_bot.models import BrokerProvider, Timeframe
from forex_bot.strategy import StrategyContext
from forex_bot.strategy.fresh_strong_zone import FreshStrongZoneContinuation


def main() -> None:
    parser = argparse.ArgumentParser(prog="forex_bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan")
    scan.add_argument("--pair", default="EUR_USD")
    scan.add_argument("--source", choices=["broker", "fixture"], default="broker")
    scan.add_argument("--broker-provider", choices=[provider.value for provider in BrokerProvider], default=None)
    scan.add_argument("--granularity", choices=[timeframe.value for timeframe in Timeframe], default=Timeframe.H1.value)
    scan.add_argument("--count", type=int, default=200)
    args = parser.parse_args()

    if args.command == "scan":
        try:
            decision = scan_pair(
                args.pair,
                source=args.source,
                broker_provider=BrokerProvider(args.broker_provider) if args.broker_provider else None,
                granularity=Timeframe(args.granularity),
                count=args.count,
            )
        except BrokerConfigError as error:
            print(json.dumps({"error": str(error), "source": args.source}, indent=2), file=stderr)
            exit(2)
        print(json.dumps(to_primitive(decision), indent=2, sort_keys=True))


def scan_pair(
    pair: str,
    source: str = "broker",
    broker_provider: BrokerProvider | None = None,
    granularity: Timeframe = Timeframe.H1,
    count: int = 200,
):
    normalized_pair = to_oanda_instrument(pair)
    if source == "fixture":
        candles = [candle for candle in load_fixture_candles("eur_usd_fresh_strong_zone.json") if candle.symbol == normalized_pair]
        instrument = instrument_spec_for(normalized_pair)
        spread_pips = Decimal("0.8")
    else:
        config = load_config_from_env()
        if broker_provider is not None:
            config = config.__class__(
                mode=config.mode,
                broker=config.broker.__class__(
                    provider=broker_provider,
                    environment=config.broker.environment,
                    account_id=config.broker.account_id,
                    token=config.broker.token,
                    username=config.broker.username,
                    password=config.broker.password,
                    app_key=config.broker.app_key,
                    practice_url=config.broker.practice_url,
                    live_url=config.broker.live_url,
                    forex_com_demo_url=config.broker.forex_com_demo_url,
                    forex_com_live_url=config.broker.forex_com_live_url,
                ),
                risk=config.risk,
                explicit_live_enabled=config.explicit_live_enabled,
            )
        snapshot = create_broker_client(config.broker).get_market_snapshot(
            symbol=normalized_pair,
            granularity=granularity,
            count=count,
        )
        candles = snapshot.candles
        instrument = snapshot.instrument
        spread_pips = snapshot.spread_pips

    strategy = FreshStrongZoneContinuation()
    return strategy.evaluate(
        StrategyContext(
            symbol=normalized_pair,
            candles=candles,
            instrument=instrument,
            spread_pips=spread_pips,
        )
    )


def to_primitive(value):
    if is_dataclass(value):
        return to_primitive(asdict(value))
    if isinstance(value, dict):
        return {key: to_primitive(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_primitive(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


if __name__ == "__main__":
    main()
