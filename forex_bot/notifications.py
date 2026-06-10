from dataclasses import dataclass
import json
from urllib import request
from urllib.error import URLError

from forex_bot.agent.policy import AgentAutonomyDecision
from forex_bot.config import AlertConfig
from forex_bot.models import RiskApproval, StrategyDecision


@dataclass(frozen=True)
class NotificationResult:
    state: str
    provider: str
    message: str


class SetupNotifier:
    def __init__(self, config: AlertConfig, timeout_seconds: int = 10) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def send_setup_alert(
        self,
        decision: StrategyDecision,
        risk_approval: RiskApproval | None,
        policy: AgentAutonomyDecision,
    ) -> tuple[NotificationResult, ...]:
        message = _setup_message(decision, risk_approval, policy)
        results: list[NotificationResult] = []
        if self.config.discord_webhook_url:
            results.append(self._send_discord(message))
        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            results.append(self._send_telegram(message))
        if not results:
            return (NotificationResult("SKIPPED", "none", "No notification provider is configured."),)
        return tuple(results)

    def _send_discord(self, message: str) -> NotificationResult:
        payload = json.dumps({"content": message}).encode("utf-8")
        req = request.Request(
            self.config.discord_webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return _send_request("discord", req, self.timeout_seconds)

    def _send_telegram(self, message: str) -> NotificationResult:
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        payload = json.dumps({"chat_id": self.config.telegram_chat_id, "text": message}).encode("utf-8")
        req = request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        return _send_request("telegram", req, self.timeout_seconds)


def _send_request(provider: str, req: request.Request, timeout_seconds: int) -> NotificationResult:
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if 200 <= status < 300:
                return NotificationResult("SENT", provider, f"Notification sent with HTTP {status}.")
            return NotificationResult("FAILED", provider, f"Notification returned HTTP {status}.")
    except URLError as error:
        return NotificationResult("FAILED", provider, str(error))


def _setup_message(
    decision: StrategyDecision,
    risk_approval: RiskApproval | None,
    policy: AgentAutonomyDecision,
) -> str:
    candidate = decision.candidate
    if candidate is None:
        return f"Thesia setup alert skipped: {decision.symbol} has no trade candidate."
    risk = "risk not approved"
    if risk_approval is not None:
        risk = f"risk={risk_approval.decision.value}, units={risk_approval.units}, amount={risk_approval.risk_amount}"
    allowed = "allowed" if policy.allowed else f"blocked: {', '.join(policy.reasons)}"
    return (
        "Thesia setup alert\n"
        f"Symbol: {candidate.symbol}\n"
        f"Strategy: {candidate.setup_name}\n"
        f"Direction: {candidate.direction.value}\n"
        f"Entry: {candidate.entry_price}\n"
        f"Stop: {candidate.stop_loss}\n"
        f"Target: {candidate.take_profit}\n"
        f"Spread pips: {candidate.spread_pips}\n"
        f"{risk}\n"
        f"Execution policy: {allowed}"
    )


def create_notifier(config: AlertConfig) -> SetupNotifier:
    return SetupNotifier(config)

