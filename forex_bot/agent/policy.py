from dataclasses import dataclass

from forex_bot.execution.base import ExecutionDiagnostics
from forex_bot.models import BotMode, RiskApproval, RiskDecision, SignalState, StrategyDecision
from forex_bot.playbook.coverage import PlaybookCoverageReport, current_playbook_coverage


@dataclass(frozen=True)
class AgentAutonomyDecision:
    allowed: bool
    action: str
    reasons: tuple[str, ...]
    playbook_automation_ready: bool


def evaluate_agent_autonomy(
    mode: BotMode,
    strategy_decision: StrategyDecision,
    risk_approval: RiskApproval | None,
    execution: ExecutionDiagnostics,
    playbook: PlaybookCoverageReport | None = None,
) -> AgentAutonomyDecision:
    playbook = playbook or current_playbook_coverage()
    reasons: list[str] = []

    if mode not in (BotMode.AUTONOMOUS_PAPER, BotMode.AUTONOMOUS_LIVE):
        reasons.append("mode_not_autonomous")

    if not playbook.automation_ready:
        reasons.append("playbook_not_automation_ready")

    if strategy_decision.state != SignalState.TRADE_CANDIDATE or strategy_decision.candidate is None:
        reasons.append("no_strategy_trade_candidate")

    if risk_approval is None:
        reasons.append("missing_risk_approval")
    elif risk_approval.decision != RiskDecision.APPROVED:
        reasons.append("risk_not_approved")

    if not execution.configured:
        reasons.append("execution_provider_not_configured")

    if not execution.can_place_orders:
        reasons.append("execution_order_placement_disabled")

    if not execution.reconciliation_ok:
        reasons.append("execution_state_not_reconciled")

    return AgentAutonomyDecision(
        allowed=not reasons,
        action="REQUEST_EXECUTION" if not reasons else "BLOCK_EXECUTION",
        reasons=tuple(reasons),
        playbook_automation_ready=playbook.automation_ready,
    )
