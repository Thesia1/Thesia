from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from forex_bot.models import Candle, Direction, InstrumentSpec, SignalState, Timeframe
from forex_bot.strategy import StrategyContext
from forex_bot.strategy.trendline_zone_sequence import TrendlineZoneSequence


class TrendlineZoneSequenceTest(unittest.TestCase):
    def test_demand_in_sequence_can_trigger_instant_buy_on_first_touch(self):
        decision = TrendlineZoneSequence().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=_demand_sequence_fixture(),
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
                daily_candles=_aligned_higher_timeframe(Direction.BUY),
                higher_timeframe_candles=_aligned_higher_timeframe(Direction.BUY, Timeframe.H4),
            )
        )

        self.assertEqual(decision.state, SignalState.TRADE_CANDIDATE)
        self.assertIsNotNone(decision.candidate)
        self.assertEqual(decision.setup_name, "trendline_zone_sequence")
        self.assertEqual(decision.candidate.direction, Direction.BUY)
        self.assertGreater(decision.candidate.take_profit, decision.candidate.entry_price)
        trendline = [item for item in decision.evidence if item.rule == "trendline_sequence"][0]
        self.assertIn("Demand in sequence above ascending trendline", trendline.detail)
        first_touch = [item for item in decision.evidence if item.rule == "first_touch_zone"][0]
        self.assertTrue(first_touch.passed)

    def test_supply_in_sequence_can_trigger_instant_sell_on_first_touch(self):
        decision = TrendlineZoneSequence().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=_supply_sequence_fixture(),
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
                daily_candles=_aligned_higher_timeframe(Direction.SELL),
                higher_timeframe_candles=_aligned_higher_timeframe(Direction.SELL, Timeframe.H4),
            )
        )

        self.assertEqual(decision.state, SignalState.TRADE_CANDIDATE)
        self.assertIsNotNone(decision.candidate)
        self.assertEqual(decision.candidate.direction, Direction.SELL)
        self.assertLess(decision.candidate.take_profit, decision.candidate.entry_price)
        trendline = [item for item in decision.evidence if item.rule == "trendline_sequence"][0]
        self.assertIn("Supply in sequence below descending trendline", trendline.detail)

    def test_prior_touch_rejects_sequence_zone(self):
        candles = _demand_sequence_fixture()
        candles[9] = replace(candles[9], low=Decimal("1.0250"))

        decision = TrendlineZoneSequence().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)
        first_touch = [item for item in decision.evidence if item.rule == "first_touch_zone"][0]
        self.assertFalse(first_touch.passed)

    def test_broken_trendline_rejects_sequence(self):
        candles = _demand_sequence_fixture()
        candles[-1] = replace(candles[-1], low=Decimal("1.0180"), close=Decimal("1.0190"))

        decision = TrendlineZoneSequence().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)
        self.assertIn("No first-touch zone", decision.evidence[-1].detail)

    def test_demand_sequence_requires_higher_highs_and_higher_lows(self):
        candles = _demand_sequence_fixture()
        candles[6] = replace(candles[6], low=Decimal("0.9990"))

        decision = TrendlineZoneSequence().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)

    def test_demand_sequence_requires_pullback_near_ascending_trendline(self):
        candles = _demand_sequence_fixture()
        candles[-1] = replace(candles[-1], open=Decimal("1.0305"), high=Decimal("1.0310"), low=Decimal("1.0290"), close=Decimal("1.0300"))

        decision = TrendlineZoneSequence().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)

    def test_weak_departure_rejects_demand_zone(self):
        candles = _demand_sequence_fixture()
        candles[8] = replace(candles[8], high=Decimal("1.0270"), close=Decimal("1.0262"))

        decision = TrendlineZoneSequence().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)

    def test_supply_sequence_requires_lower_highs_and_lower_lows(self):
        candles = _supply_sequence_fixture()
        candles[6] = replace(candles[6], open=Decimal("1.0640"), high=Decimal("1.0660"), low=Decimal("1.0610"), close=Decimal("1.0620"))

        decision = TrendlineZoneSequence().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)

    def test_supply_sequence_requires_pullback_near_descending_trendline(self):
        candles = _supply_sequence_fixture()
        candles[-1] = replace(candles[-1], open=Decimal("1.0810"), high=Decimal("1.0820"), low=Decimal("1.0700"), close=Decimal("1.0815"))

        decision = TrendlineZoneSequence().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)

    def test_weak_departure_rejects_supply_zone(self):
        candles = _supply_sequence_fixture()
        candles[8] = replace(candles[8], low=Decimal("1.0838"), close=Decimal("1.0840"))

        decision = TrendlineZoneSequence().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)


def _demand_sequence_fixture() -> list[Candle]:
    return [
        _candle(0, "1.0200", "1.0240", "1.0180", "1.0220"),
        _candle(1, "1.0220", "1.0260", "1.0120", "1.0140"),
        _candle(2, "1.0140", "1.0180", "1.0000", "1.0160"),
        _candle(3, "1.0160", "1.0300", "1.0150", "1.0280"),
        _candle(4, "1.0280", "1.0360", "1.0240", "1.0340"),
        _candle(5, "1.0340", "1.0350", "1.0170", "1.0260"),
        _candle(6, "1.0260", "1.0300", "1.0130", "1.0290"),
        _candle(7, "1.0250", "1.0260", "1.0240", "1.0252"),
        _candle(8, "1.0252", "1.0340", "1.0250", "1.0330"),
        _candle(9, "1.0330", "1.0360", "1.0280", "1.0340"),
        _candle(10, "1.0340", "1.0345", "1.0250", "1.0255"),
    ]


def _supply_sequence_fixture() -> list[Candle]:
    return [
        _candle(0, "1.0800", "1.0820", "1.0740", "1.0780"),
        _candle(1, "1.0780", "1.0900", "1.0770", "1.0880"),
        _candle(2, "1.0880", "1.1000", "1.0860", "1.0890"),
        _candle(3, "1.0890", "1.0910", "1.0700", "1.0740"),
        _candle(4, "1.0740", "1.0760", "1.0600", "1.0640"),
        _candle(5, "1.0640", "1.0950", "1.0630", "1.0820"),
        _candle(6, "1.0820", "1.0840", "1.0520", "1.0580"),
        _candle(7, "1.0848", "1.0860", "1.0840", "1.0846"),
        _candle(8, "1.0846", "1.0850", "1.0740", "1.0750"),
        _candle(9, "1.0750", "1.0810", "1.0700", "1.0710"),
        _candle(10, "1.0710", "1.0860", "1.0700", "1.0845"),
    ]


def _aligned_higher_timeframe(direction: Direction, timeframe: Timeframe = Timeframe.D) -> list[Candle]:
    if direction == Direction.BUY:
        return [
            _candle(0, "1.0000", "1.0200", "0.9900", "1.0100", timeframe=timeframe),
            _candle(1, "1.0100", "1.0300", "1.0000", "1.0200", timeframe=timeframe),
        ]
    return [
        _candle(0, "1.0300", "1.0400", "1.0100", "1.0200", timeframe=timeframe),
        _candle(1, "1.0200", "1.0300", "1.0000", "1.0100", timeframe=timeframe),
    ]


def _eur_usd() -> InstrumentSpec:
    return InstrumentSpec(
        symbol="EUR_USD",
        pip_size=Decimal("0.0001"),
        pip_value_per_unit=Decimal("0.0001"),
        min_units=Decimal("1"),
        max_units=Decimal("100000"),
        unit_step=Decimal("1"),
        margin_rate=Decimal("0.0333"),
        max_spread_pips=Decimal("2"),
    )


def _candle(
    index: int,
    open_price: str,
    high: str,
    low: str,
    close: str,
    timeframe: Timeframe = Timeframe.H1,
) -> Candle:
    return Candle(
        symbol="EUR_USD",
        timeframe=timeframe,
        timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(hours=index),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
    )


if __name__ == "__main__":
    unittest.main()
