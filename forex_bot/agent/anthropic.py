from forex_bot.agent.base import AgentMessage, AgentProviderError, AgentResponse
from forex_bot.config import AgentConfig


class AnthropicAgentProvider:
    provider_name = "anthropic"

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def generate_response(self, messages: list[AgentMessage], max_tokens: int = 400) -> AgentResponse:
        self._require_credentials()
        raise AgentProviderError(
            "Anthropic agent adapter is configured as primary but is not implemented yet. "
            "Use OpenRouter fallback for agent testing only until native agent policies and tools are wired."
        )

    def _require_credentials(self) -> None:
        token = self.config.anthropic_api_key
        if not token or token.startswith("your_"):
            raise AgentProviderError("Missing required Anthropic setting: ANTHROPIC_API_KEY")

