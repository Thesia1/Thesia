import unittest

from forex_bot.agent.playbook import assess_playbook_grounding, build_playbook_messages


class AgentPlaybookTest(unittest.TestCase):
    def test_playbook_prompt_contains_strategy_and_execution_boundaries(self):
        report = assess_playbook_grounding(build_playbook_messages())

        self.assertTrue(report.grounded)
        self.assertEqual(report.missing_topics, ())
        self.assertIn("fresh_strong_zone_continuation", report.prompt_preview)
        self.assertIn("trendline_zone_sequence", report.prompt_preview)
        self.assertIn("Stairs zones", report.prompt_preview)
        self.assertIn("CP levels", report.prompt_preview)
        self.assertIn("Supply-in-sequence", report.prompt_preview)
        self.assertIn("Demand-in-sequence", report.prompt_preview)

    def test_incomplete_messages_report_missing_topics(self):
        report = assess_playbook_grounding([])

        self.assertFalse(report.grounded)
        self.assertIn("fresh_strong_zone", report.missing_topics)
        self.assertIn("deriv_mt5_execution", report.missing_topics)


if __name__ == "__main__":
    unittest.main()
