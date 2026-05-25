from decimal import Decimal
import unittest

from forex_bot.models import (
    AccountState,
    Direction,
    InstrumentSpec,
    RiskDecision,
    RiskLimits,
    TradeCandidate,
)
from forex_bot.risk_gate import evaluate_risk


class RiskGateTest(unittest.TestCase):
    def test_risk_gate_approves_valid_trade_candidate(self):
        approval = evaluate_risk(
            account=_account(),
            instrument=_eur_usd(),
            candidate=TradeCandidate(
                symbol="EUR_USD",
                direction=Direction.BUY,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
                spread_pips=Decimal("0.8"),
                setup_name="fresh_strong_zone_continuation",
                strategy_decision_id="decision-1",
            ),
            limits=RiskLimits(),
        )

        self.assertEqual(approval.decision, RiskDecision.APPROVED)
        self.assertEqual(approval.units, Decimal("5000"))
        self.assertEqual(approval.risk_amount, Decimal("25.0000"))
        self.assertEqual(approval.reward_to_risk, Decimal("2"))
        self.assertEqual(approval.reasons, ())

    def test_risk_gate_rejects_high_spread_and_missing_decision_id(self):
        approval = evaluate_risk(
            account=_account(),
            instrument=_eur_usd(),
            candidate=TradeCandidate(
                symbol="EUR_USD",
                direction=Direction.SELL,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.1050"),
                take_profit=Decimal("1.0900"),
                spread_pips=Decimal("3"),
                setup_name="fresh_strong_zone_continuation",
                strategy_decision_id="",
            ),
            limits=RiskLimits(),
        )

        self.assertEqual(approval.decision, RiskDecision.REJECTED)
        self.assertEqual(approval.units, Decimal("0"))
        self.assertIn("spread_too_high", approval.reasons)
        self.assertIn("missing_strategy_decision_id", approval.reasons)

    def test_risk_gate_rejects_daily_loss_limit(self):
        approval = evaluate_risk(
            account=_account(daily_realized_loss=Decimal("200")),
            instrument=_eur_usd(),
            candidate=TradeCandidate(
                symbol="EUR_USD",
                direction=Direction.BUY,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
                spread_pips=Decimal("0.8"),
                setup_name="fresh_strong_zone_continuation",
                strategy_decision_id="decision-1",
            ),
            limits=RiskLimits(),
        )

        self.assertEqual(approval.decision, RiskDecision.REJECTED)
        self.assertIn("daily_loss_limit_reached", approval.reasons)


def _account(daily_realized_loss: Decimal = Decimal("0")) -> AccountState:
    return AccountState(
        equity=Decimal("10000"),
        daily_realized_loss=daily_realized_loss,
        weekly_realized_loss=Decimal("0"),
        open_trade_count=0,
        open_risk=Decimal("0"),
        margin_available=Decimal("10000"),
    )


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


if __name__ == "__main__":
    unittest.main()
