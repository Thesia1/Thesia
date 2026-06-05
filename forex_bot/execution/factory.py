from forex_bot.config import ExecutionConfig
from forex_bot.execution.base import ExecutionClient, ExecutionDiagnostics, ExecutionProviderError
from forex_bot.execution.mt5 import Mt5ExecutionClient
from forex_bot.models import ExecutionProvider


class NoExecutionClient:
    provider_name = "none"

    def __init__(self, config: ExecutionConfig) -> None:
        self.config = config

    def diagnose(self, probe_terminal: bool = False, symbols: tuple[str, ...] = ()) -> ExecutionDiagnostics:
        return ExecutionDiagnostics(
            provider=self.provider_name,
            environment=self.config.environment.value,
            configured=False,
            can_place_orders=False,
            reason="No execution provider is configured.",
        )

    def submit_order(self, request, ledger=None):
        raise ExecutionProviderError("No execution provider is configured.")


def create_execution_client(config: ExecutionConfig) -> ExecutionClient:
    if config.provider == ExecutionProvider.MT5:
        return Mt5ExecutionClient(config)
    if config.provider == ExecutionProvider.NONE:
        return NoExecutionClient(config)
    if config.provider == ExecutionProvider.OANDA:
        return NoExecutionClient(config)
    raise ValueError(f"Unsupported execution provider: {config.provider}")
