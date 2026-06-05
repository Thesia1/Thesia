from decimal import Decimal
from datetime import datetime, timezone, timedelta
from dataclasses import replace
import unittest

from forex_bot.fixtures import load_fixture_candles
from forex_bot.models import Candle, Direction, InstrumentSpec, RiskDecision, RiskLimits, SignalState, Timeframe
from forex_bot.risk_gate import evaluate_risk
from forex_bot.strategy import StrategyContext
from forex_bot.strategy.fresh_strong_zone import FreshStrongZoneContinuation


class FreshStrongZoneTest(unittest.TestCase):
    def test_fixture_produces_trade_candidate_and_passes_risk(self):
        candles = load_fixture_candles("eur_usd_fresh_strong_zone.json")
        instrument = _eur_usd()
        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=instrument,
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.TRADE_CANDIDATE)
        self.assertIsNotNone(decision.candidate)
        self.assertEqual(decision.candidate.direction, Direction.BUY)
        opposite_evidence = [item for item in decision.evidence if item.rule == "opposite_zone_removed"][0]
        self.assertIn("opposing supply zone high", opposite_evidence.detail)

        approval = evaluate_risk(
            account=_account(),
            instrument=instrument,
            candidate=decision.candidate,
            limits=RiskLimits(min_reward_to_risk=Decimal("2")),
        )

        self.assertEqual(approval.decision, RiskDecision.APPROVED)

    def test_short_history_returns_no_trade(self):
        candles = load_fixture_candles("eur_usd_fresh_strong_zone.json")[:3]
        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)

    def test_bearish_supply_setup_can_produce_sell_candidate(self):
        candles = _bearish_supply_fixture()
        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.TRADE_CANDIDATE)
        self.assertIsNotNone(decision.candidate)
        self.assertEqual(decision.candidate.direction, Direction.SELL)
        self.assertLess(decision.candidate.take_profit, decision.candidate.entry_price)
        self.assertGreater(decision.candidate.stop_loss, decision.candidate.entry_price)
        opposite_evidence = [item for item in decision.evidence if item.rule == "opposite_zone_removed"][0]
        self.assertIn("opposing demand zone low", opposite_evidence.detail)

    def test_higher_timeframe_filter_can_reject_candidate(self):
        candles = _bearish_supply_fixture()
        higher_timeframe = [
            _candle(0, "1.0900", "1.1000", "1.0850", "1.0950", timeframe=Timeframe.H4),
            _candle(1, "1.0950", "1.1050", "1.0920", "1.1000", timeframe=Timeframe.H4),
        ]
        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
                higher_timeframe_candles=higher_timeframe,
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)
        htf_evidence = [item for item in decision.evidence if item.rule == "higher_timeframe_confirmation"][0]
        self.assertFalse(htf_evidence.passed)

    def test_prior_retest_rejects_no_longer_fresh_zone(self):
        candles = load_fixture_candles("eur_usd_fresh_strong_zone.json")
        candles[7] = replace(candles[7], low=Decimal("1.1005"))

        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)
        freshness = [item for item in decision.evidence if item.rule == "zone_freshness"][0]
        self.assertFalse(freshness.passed)
        self.assertIn("prior retests=1", freshness.detail)

    def test_prior_invalidation_rejects_zone(self):
        candles = load_fixture_candles("eur_usd_fresh_strong_zone.json")
        candles[7] = replace(candles[7], low=Decimal("1.0988"), close=Decimal("1.0990"))

        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)
        freshness = [item for item in decision.evidence if item.rule == "zone_freshness"][0]
        self.assertFalse(freshness.passed)
        self.assertIn("invalidated", freshness.detail)

    def test_curve_location_rejects_buy_outside_low_curve(self):
        candles = load_fixture_candles("eur_usd_fresh_strong_zone.json")
        higher_timeframe = [
            _candle(0, "1.1000", "1.2000", "1.0000", "1.1500", timeframe=Timeframe.H4),
            _candle(1, "1.1500", "1.2000", "1.0000", "1.1700", timeframe=Timeframe.H4),
            _candle(2, "1.1700", "1.2000", "1.0000", "1.1800", timeframe=Timeframe.H4),
        ]

        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
                higher_timeframe_candles=higher_timeframe,
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)
        curve = [item for item in decision.evidence if item.rule == "curve_location"][0]
        self.assertFalse(curve.passed)
        self.assertIn("desired=LOW_CURVE", curve.detail)

    def test_curve_location_allows_buy_in_low_25_percent(self):
        candles = load_fixture_candles("eur_usd_fresh_strong_zone.json")
        higher_timeframe = [
            _candle(0, "1.0200", "1.2000", "1.0000", "1.0300", timeframe=Timeframe.H4),
            _candle(1, "1.0300", "1.2000", "1.0000", "1.0400", timeframe=Timeframe.H4),
            _candle(2, "1.0400", "1.2000", "1.0000", "1.0450", timeframe=Timeframe.H4),
        ]

        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
                higher_timeframe_candles=higher_timeframe,
            )
        )

        self.assertEqual(decision.state, SignalState.TRADE_CANDIDATE)
        curve = [item for item in decision.evidence if item.rule == "curve_location"][0]
        self.assertTrue(curve.passed)
        self.assertIn("location=LOW_CURVE", curve.detail)
        self.assertIn("position=0.2250", curve.detail)

    def test_monthly_weekly_daily_alignment_can_confirm_candidate(self):
        candles = load_fixture_candles("eur_usd_fresh_strong_zone.json")

        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
                monthly_candles=_aligned_higher_timeframe(Timeframe.M),
                weekly_candles=_aligned_higher_timeframe(Timeframe.W),
                daily_candles=_aligned_higher_timeframe(Timeframe.D),
            )
        )

        self.assertEqual(decision.state, SignalState.TRADE_CANDIDATE)
        alignment = [item for item in decision.evidence if item.rule == "monthly_weekly_daily_alignment"][0]
        self.assertTrue(alignment.passed)
        self.assertIn("M:aligned", alignment.detail)
        self.assertIn("W:aligned", alignment.detail)
        self.assertIn("D:aligned", alignment.detail)

    def test_monthly_weekly_daily_alignment_fails_closed_when_context_is_incomplete(self):
        candles = load_fixture_candles("eur_usd_fresh_strong_zone.json")

        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
                monthly_candles=_aligned_higher_timeframe(Timeframe.M),
            )
        )

        self.assertEqual(decision.state, SignalState.NO_TRADE)
        alignment = [item for item in decision.evidence if item.rule == "monthly_weekly_daily_alignment"][0]
        self.assertFalse(alignment.passed)
        self.assertIn("W:missing_or_insufficient", alignment.detail)
        self.assertIn("D:missing_or_insufficient", alignment.detail)

    def test_nearest_opposing_zone_can_replace_fixed_target(self):
        candles = _prior_supply_plus_bullish_fixture()

        decision = FreshStrongZoneContinuation().evaluate(
            StrategyContext(
                symbol="EUR_USD",
                candles=candles,
                instrument=_eur_usd(),
                spread_pips=Decimal("0.8"),
            )
        )

        self.assertEqual(decision.state, SignalState.TRADE_CANDIDATE)
        self.assertIsNotNone(decision.candidate)
        self.assertEqual(decision.candidate.take_profit, Decimal("1.1055"))
        target = [item for item in decision.evidence if item.rule == "target_selection"][0]
        self.assertIn("nearest opposing supply", target.detail)


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


def _account():
    from forex_bot.models import AccountState

    return AccountState(
        equity=Decimal("10000"),
        daily_realized_loss=Decimal("0"),
        weekly_realized_loss=Decimal("0"),
        open_trade_count=0,
        open_risk=Decimal("0"),
        margin_available=Decimal("10000"),
    )


def _bearish_supply_fixture() -> list[Candle]:
    return [
        _candle(0, "1.0954", "1.0958", "1.0952", "1.0955"),
        _candle(1, "1.0955", "1.0988", "1.0954", "1.0985"),
        _candle(2, "1.1000", "1.1030", "1.0990", "1.1020"),
        _candle(3, "1.1020", "1.1040", "1.1000", "1.1030"),
        _candle(4, "1.1030", "1.1050", "1.1010", "1.1040"),
        _candle(5, "1.1040", "1.1048", "1.1038", "1.1042"),
        _candle(6, "1.1041", "1.1044", "1.0940", "1.0950"),
        _candle(7, "1.0950", "1.0965", "1.0930", "1.0932"),
        _candle(8, "1.0932", "1.0980", "1.0928", "1.0970"),
        _candle(9, "1.1035", "1.1038", "1.0950", "1.0958"),
    ]


def _prior_supply_plus_bullish_fixture() -> list[Candle]:
    supply = [
        _candle_at(0, "1.1056", "1.1058", "1.1055", "1.1057"),
        _candle_at(1, "1.1057", "1.1059", "1.1038", "1.1040"),
    ]
    shifted = [
        replace(candle, timestamp=candle.timestamp + timedelta(hours=2))
        for candle in load_fixture_candles("eur_usd_fresh_strong_zone.json")
    ]
    return supply + shifted


def _aligned_higher_timeframe(timeframe: Timeframe) -> list[Candle]:
    return [
        _candle(0, "1.0200", "1.0400", "1.0100", "1.0300", timeframe=timeframe),
        _candle(1, "1.0300", "1.0500", "1.0200", "1.0400", timeframe=timeframe),
    ]


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


def _candle_at(
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
        timestamp=datetime(2026, 5, 25, 7, tzinfo=timezone.utc) + timedelta(hours=index),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
    )


if __name__ == "__main__":
    unittest.main()
