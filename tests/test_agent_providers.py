import unittest
from unittest.mock import patch

from forex_bot.agent.base import AgentMessage
from forex_bot.agent.factory import create_agent_provider
from forex_bot.agent.openrouter import OpenRouterAgentProvider
from forex_bot.config import AgentConfig
from forex_bot.models import AgentProvider


class AgentProviderTest(unittest.TestCase):
    def test_anthropic_primary_falls_back_to_openrouter_auto(self):
        config = AgentConfig(
            primary_provider=AgentProvider.ANTHROPIC,
            fallback_provider=AgentProvider.OPENROUTER,
            openrouter_api_key="openrouter-key",
            openrouter_model="openrouter/auto",
        )
        provider = create_agent_provider(config)

        with patch.object(
            OpenRouterAgentProvider,
            "_post_json",
            return_value={
                "model": "anthropic/claude-sonnet-4.6",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "No execution is allowed in WATCH mode.",
                        }
                    }
                ],
            },
        ) as post_json:
            response = provider.generate_response(
                [
                    AgentMessage(role="system", content="Explain trading decisions safely."),
                    AgentMessage(role="user", content="Can the bot place this trade in WATCH mode?"),
                ],
                max_tokens=80,
            )

        self.assertEqual(response.provider, "openrouter")
        self.assertEqual(response.model, "anthropic/claude-sonnet-4.6")
        self.assertTrue(response.used_fallback)
        self.assertIn("Anthropic", response.error)
        self.assertIn("WATCH mode", response.content)
        payload = post_json.call_args.args[1]
        self.assertEqual(payload["model"], "openrouter/auto")
        self.assertEqual(payload["max_completion_tokens"], 80)

    def test_openrouter_requires_key(self):
        config = AgentConfig(
            primary_provider=AgentProvider.OPENROUTER,
            fallback_provider=AgentProvider.NONE,
        )
        provider = create_agent_provider(config)

        response = provider.generate_response([AgentMessage(role="user", content="hello")])

        self.assertEqual(response.provider, "openrouter")
        self.assertFalse(response.used_fallback)
        self.assertEqual(response.content, "")
        self.assertIn("OPENROUTER_API_KEY", response.error)

    def test_missing_primary_and_openrouter_credentials_records_both_errors(self):
        provider = create_agent_provider(AgentConfig())

        response = provider.generate_response([AgentMessage(role="user", content="hello")])

        self.assertEqual(response.provider, "openrouter")
        self.assertTrue(response.used_fallback)
        self.assertEqual(response.content, "")
        self.assertIn("ANTHROPIC_API_KEY", response.error)
        self.assertIn("OPENROUTER_API_KEY", response.error)

    def test_none_cannot_be_primary_agent_provider(self):
        config = AgentConfig(primary_provider=AgentProvider.NONE)

        with self.assertRaises(ValueError):
            create_agent_provider(config)


if __name__ == "__main__":
    unittest.main()

