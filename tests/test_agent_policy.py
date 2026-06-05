from datetime import datetime, timezone
from decimal import Decimal
import unittest

from forex_bot.agent.policy import evaluate_agent_autonomy
from forex_bot.execution.base import ExecutionDiagnostics
from forex_bot.models import BotMode, Direction, RiskApproval, RiskDecision, SignalState, StrategyDecision, TradeCandidate
from forex_bot.playbook.coverage import PlaybookCoverageReport, PlaybookConcept, PlaybookCoverageState


class AgentPolicyTest(unittest.TestCase):
    def test_agent_autonomy_blocks_when_playbook_and_execution_are_not_ready(self):
        decision = StrategyDecision(
            id="decision-1",
            symbol="EUR_USD",
            state=SignalState.NO_TRADE,
            setup_name="fresh_strong_zone_continuation",
            created_at=datetime.now(timezone.utc),
            evidence=(),
            candidate=None,
        )
        execution = ExecutionDiagnostics(
            provider="mt5",
            environment="live",
            configured=True,
            can_place_orders=False,
            reason="disabled",
        )

        policy = evaluate_agent_autonomy(
            mode=BotMode.AUTONOMOUS_LIVE,
            strategy_decision=decision,
            risk_approval=None,
            execution=execution,
        )

        self.assertFalse(policy.allowed)
        self.assertEqual(policy.action, "BLOCK_EXECUTION")
        self.assertIn("no_strategy_trade_candidate", policy.reasons)
        self.assertIn("execution_order_placement_disabled", policy.reasons)
        self.assertIn("execution_state_not_reconciled", policy.reasons)

    def test_agent_autonomy_allows_only_when_every_gate_is_ready(self):
        candidate = TradeCandidate(
            symbol="EUR_USD",
            direction=Direction.BUY,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
            spread_pips=Decimal("0.8"),
            setup_name="fresh_strong_zone_continuation",
            strategy_decision_id="decision-1",
        )
        decision = StrategyDecision(
            id="decision-1",
            symbol="EUR_USD",
            state=SignalState.TRADE_CANDIDATE,
            setup_name="fresh_strong_zone_continuation",
            created_at=datetime.now(timezone.utc),
            evidence=(),
            candidate=candidate,
        )
        approval = RiskApproval(
            decision=RiskDecision.APPROVED,
            units=Decimal("1000"),
            risk_amount=Decimal("25"),
            reward_to_risk=Decimal("2"),
            reasons=(),
        )
        execution = ExecutionDiagnostics(
            provider="mt5",
            environment="live",
            configured=True,
            can_place_orders=True,
            reason="ready",
            read_only_probe_ok=True,
            reconciliation_ok=True,
        )
        playbook = PlaybookCoverageReport(
            automation_ready=True,
            implemented_count=1,
            partial_count=0,
            missing_count=0,
            required_blockers=(),
            concepts=(
                PlaybookConcept(
                    name="test",
                    source="test",
                    state=PlaybookCoverageState.IMPLEMENTED,
                    automation_required=True,
                    notes="",
                ),
            ),
        )

        policy = evaluate_agent_autonomy(
            mode=BotMode.AUTONOMOUS_LIVE,
            strategy_decision=decision,
            risk_approval=approval,
            execution=execution,
            playbook=playbook,
        )

        self.assertTrue(policy.allowed)
        self.assertEqual(policy.action, "REQUEST_EXECUTION")
        self.assertEqual(policy.reasons, ())


if __name__ == "__main__":
    unittest.main()
