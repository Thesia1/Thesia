from decimal import Decimal
import unittest

from forex_bot.agent.policy import AgentAutonomyDecision
from forex_bot.config import AlertConfig
from forex_bot.models import Direction, RiskApproval, RiskDecision, StrategyDecision, SignalState, TradeCandidate
from forex_bot.notifications import SetupNotifier


class NotificationsTest(unittest.TestCase):
    def test_setup_alert_skips_when_no_provider_is_configured(self):
        notifier = SetupNotifier(AlertConfig())
        decision = _candidate_decision()
        result = notifier.send_setup_alert(
            decision,
            RiskApproval(
                decision=RiskDecision.APPROVED,
                units=Decimal("1000"),
                risk_amount=Decimal("5"),
                reward_to_risk=Decimal("2"),
                reasons=(),
            ),
            AgentAutonomyDecision(
                allowed=True,
                action="REQUEST_EXECUTION",
                reasons=(),
                playbook_automation_ready=True,
            ),
        )

        self.assertEqual(result[0].state, "SKIPPED")
        self.assertEqual(result[0].provider, "none")


def _candidate_decision() -> StrategyDecision:
    return StrategyDecision(
        id="decision-1",
        symbol="EUR_USD",
        state=SignalState.TRADE_CANDIDATE,
        setup_name="trendline_zone_sequence",
        created_at=__import__("datetime").datetime.fromisoformat("2026-06-09T12:00:00+00:00"),
        evidence=(),
        candidate=TradeCandidate(
            symbol="EUR_USD",
            direction=Direction.BUY,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
            spread_pips=Decimal("0.8"),
            setup_name="trendline_zone_sequence",
            strategy_decision_id="decision-1",
        ),
    )


if __name__ == "__main__":
    unittest.main()

