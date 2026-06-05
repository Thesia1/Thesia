from dataclasses import dataclass
from typing import Protocol


class AgentProviderError(ValueError):
    pass


@dataclass(frozen=True)
class AgentMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AgentResponse:
    provider: str
    model: str
    content: str
    used_fallback: bool
    error: str = ""


class AgentModelProvider(Protocol):
    provider_name: str

    def generate_response(self, messages: list[AgentMessage], max_tokens: int = 400) -> AgentResponse:
        raise NotImplementedError

