import unittest

from forex_bot.playbook.coverage import PlaybookCoverageState, current_playbook_coverage


class PlaybookCoverageTest(unittest.TestCase):
    def test_current_playbook_coverage_has_no_required_strategy_translation_blockers(self):
        report = current_playbook_coverage()

        self.assertTrue(report.automation_ready)
        self.assertGreaterEqual(report.implemented_count, 9)
        self.assertNotIn("opposite_structure_removal", report.required_blockers)
        self.assertNotIn("multi_timeframe_direction", report.required_blockers)
        self.assertNotIn("high_low_curve_location", report.required_blockers)
        self.assertNotIn("news_blackout", report.required_blockers)
        self.assertNotIn("deriv_mt5_reconciliation", report.required_blockers)

    def test_required_blockers_exclude_optional_pob_expansion(self):
        report = current_playbook_coverage()
        optional = [concept for concept in report.concepts if concept.name == "pob_setup_families"][0]

        self.assertEqual(optional.state, PlaybookCoverageState.MISSING)
        self.assertFalse(optional.automation_required)
        self.assertNotIn("pob_setup_families", report.required_blockers)

    def test_session_visual_concepts_are_tracked_without_blocking_current_automation(self):
        report = current_playbook_coverage()
        concepts = {concept.name: concept for concept in report.concepts}

        self.assertEqual(concepts["base_quality_patterns"].state, PlaybookCoverageState.PARTIAL)
        self.assertEqual(concepts["stairs_zone_rejection"].state, PlaybookCoverageState.MISSING)
        self.assertEqual(concepts["trendline_break_change"].state, PlaybookCoverageState.MISSING)
        self.assertFalse(concepts["trendline_break_change"].automation_required)
        self.assertNotIn("stairs_zone_rejection", report.required_blockers)


if __name__ == "__main__":
    unittest.main()
