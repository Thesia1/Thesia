import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from forex_bot.fixtures import load_fixture_candles
from forex_bot.models import InstrumentSpec
from forex_bot.strategy import StrategyContext
from forex_bot.strategy.fresh_strong_zone import FreshStrongZoneContinuation


def main() -> None:
    parser = argparse.ArgumentParser(prog="forex_bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan")
    scan.add_argument("--pair", default="EUR_USD")
    args = parser.parse_args()

    if args.command == "scan":
        decision = scan_pair(args.pair)
        print(json.dumps(to_primitive(decision), indent=2, sort_keys=True))


def scan_pair(pair: str):
    candles = [candle for candle in load_fixture_candles("eur_usd_fresh_strong_zone.json") if candle.symbol == pair]
    instrument = InstrumentSpec(
        symbol=pair,
        pip_size=Decimal("0.0001"),
        pip_value_per_unit=Decimal("0.0001"),
        min_units=Decimal("1"),
        max_units=Decimal("100000"),
        unit_step=Decimal("1"),
        margin_rate=Decimal("0.0333"),
        max_spread_pips=Decimal("2"),
    )
    strategy = FreshStrongZoneContinuation()
    return strategy.evaluate(
        StrategyContext(
            symbol=pair,
            candles=candles,
            instrument=instrument,
            spread_pips=Decimal("0.8"),
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
