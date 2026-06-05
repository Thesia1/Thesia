from forex_bot.agent.anthropic import AnthropicAgentProvider
from forex_bot.agent.base import AgentMessage, AgentModelProvider, AgentProviderError, AgentResponse
from forex_bot.agent.openrouter import OpenRouterAgentProvider
from forex_bot.config import AgentConfig
from forex_bot.models import AgentProvider


class FallbackAgentProvider:
    provider_name = "agent_fallback_chain"

    def __init__(self, primary: AgentModelProvider, fallback: AgentModelProvider | None) -> None:
        self.primary = primary
        self.fallback = fallback

    def generate_response(self, messages: list[AgentMessage], max_tokens: int = 400) -> AgentResponse:
        try:
            return self.primary.generate_response(messages=messages, max_tokens=max_tokens)
        except AgentProviderError as error:
            if self.fallback is None:
                return AgentResponse(
                    provider=self.primary.provider_name,
                    model="",
                    content="",
                    used_fallback=False,
                    error=str(error),
                )

            try:
                response = self.fallback.generate_response(messages=messages, max_tokens=max_tokens)
            except AgentProviderError as fallback_error:
                return AgentResponse(
                    provider=self.fallback.provider_name,
                    model="",
                    content="",
                    used_fallback=True,
                    error=f"{error}; fallback failed: {fallback_error}",
                )

            return AgentResponse(
                provider=response.provider,
                model=response.model,
                content=response.content,
                used_fallback=True,
                error=str(error),
            )


def create_agent_provider(config: AgentConfig) -> AgentModelProvider:
    primary = _create_provider(config.primary_provider, config)
    fallback = None if config.fallback_provider == AgentProvider.NONE else _create_provider(config.fallback_provider, config)
    return FallbackAgentProvider(primary, fallback)


def _create_provider(provider: AgentProvider, config: AgentConfig) -> AgentModelProvider:
    if provider == AgentProvider.ANTHROPIC:
        return AnthropicAgentProvider(config)
    if provider == AgentProvider.OPENROUTER:
        return OpenRouterAgentProvider(config)
    if provider == AgentProvider.OPENAI:
        raise ValueError("OpenAI agent provider is configured but not implemented yet")
    if provider == AgentProvider.NONE:
        raise ValueError("Agent provider 'none' can only be used as a fallback setting")
    raise ValueError(f"Unsupported agent provider: {provider}")

