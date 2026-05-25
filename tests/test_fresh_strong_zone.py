from decimal import Decimal
import unittest

from forex_bot.fixtures import load_fixture_candles
from forex_bot.models import Direction, InstrumentSpec, RiskDecision, RiskLimits, SignalState
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


if __name__ == "__main__":
    unittest.main()

