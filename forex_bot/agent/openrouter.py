import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from forex_bot.agent.base import AgentMessage, AgentProviderError, AgentResponse
from forex_bot.config import AgentConfig


class OpenRouterAgentProvider:
    provider_name = "openrouter"

    def __init__(self, config: AgentConfig, timeout_seconds: int = 30) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def generate_response(self, messages: list[AgentMessage], max_tokens: int = 400) -> AgentResponse:
        self._require_credentials()
        payload = {
            "model": self.config.openrouter_model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "max_completion_tokens": max_tokens,
            "temperature": 0.2,
        }
        response = self._post_json(f"{self.config.openrouter_base_url.rstrip('/')}/chat/completions", payload)
        choices = response.get("choices", [])
        if not choices:
            raise AgentProviderError("OpenRouter returned no completion choices")

        first = choices[0]
        message = first.get("message", {}) if isinstance(first, dict) else {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        if not content:
            raise AgentProviderError("OpenRouter returned an empty agent response")

        return AgentResponse(
            provider=self.provider_name,
            model=str(response.get("model", self.config.openrouter_model)),
            content=str(content),
            used_fallback=False,
        )

    def _require_credentials(self) -> None:
        token = self.config.openrouter_api_key
        if not token or token.startswith("your_"):
            raise AgentProviderError("Missing required OpenRouter setting: OPENROUTER_API_KEY")

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.config.openrouter_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise AgentProviderError(f"OpenRouter agent request failed with HTTP {error.code}") from error
        except URLError as error:
            raise AgentProviderError(f"OpenRouter agent request failed: {error.reason}") from error

