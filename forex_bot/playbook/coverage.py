from dataclasses import dataclass
from enum import Enum


class PlaybookCoverageState(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


@dataclass(frozen=True)
class PlaybookConcept:
    name: str
    source: str
    state: PlaybookCoverageState
    automation_required: bool
    notes: str


@dataclass(frozen=True)
class PlaybookCoverageReport:
    automation_ready: bool
    implemented_count: int
    partial_count: int
    missing_count: int
    required_blockers: tuple[str, ...]
    concepts: tuple[PlaybookConcept, ...]


def current_playbook_coverage() -> PlaybookCoverageReport:
    concepts = (
        PlaybookConcept(
            name="base_candle_detection",
            source="Echo/Raja",
            state=PlaybookCoverageState.IMPLEMENTED,
            automation_required=True,
            notes="Implemented with body-to-range threshold.",
        ),
        PlaybookConcept(
            name="bullish_and_bearish_departure",
            source="Echo/Raja",
            state=PlaybookCoverageState.IMPLEMENTED,
            automation_required=True,
            notes="Implemented for demand and supply continuation setups.",
        ),
        PlaybookConcept(
            name="opposite_structure_removal",
            source="Echo/Raja",
            state=PlaybookCoverageState.IMPLEMENTED,
            automation_required=True,
            notes="Uses active prior opposing zone objects; buys must close above opposing supply and sells must close below opposing demand.",
        ),
        PlaybookConcept(
            name="fresh_zone_tracking",
            source="Echo/Raja",
            state=PlaybookCoverageState.IMPLEMENTED,
            automation_required=True,
            notes="Tracks prior retests and invalidation before the current return.",
        ),
        PlaybookConcept(
            name="multi_timeframe_direction",
            source="Echo/Raja",
            state=PlaybookCoverageState.IMPLEMENTED,
            automation_required=True,
            notes="Monthly, weekly, and daily candle context is supported; incomplete supplied context fails closed.",
        ),
        PlaybookConcept(
            name="high_low_curve_location",
            source="Echo/Raja",
            state=PlaybookCoverageState.IMPLEMENTED,
            automation_required=True,
            notes="Uses the documented 0-25% higher-timeframe curve extremes: buys require low curve, sells require high curve.",
        ),
        PlaybookConcept(
            name="nearest_opposing_zone_target",
            source="Echo/Raja",
            state=PlaybookCoverageState.IMPLEMENTED,
            automation_required=True,
            notes="Uses nearest opposing zone when it still satisfies the minimum reward target; otherwise fixed 2R is retained.",
        ),
        PlaybookConcept(
            name="news_blackout",
            source="Risk/Execution",
            state=PlaybookCoverageState.IMPLEMENTED,
            automation_required=True,
            notes="Scheduled economic-calendar blackout gating blocks matching high-impact currency events inside the configured window.",
        ),
        PlaybookConcept(
            name="deriv_mt5_reconciliation",
            source="Execution",
            state=PlaybookCoverageState.IMPLEMENTED,
            automation_required=True,
            notes="MT5 terminal probe verifies account, positions, open orders, equity, margin, symbol metadata, and ticks before broker state is trusted.",
        ),
        PlaybookConcept(
            name="pob_engulfing_body_confirmation",
            source="PoB",
            state=PlaybookCoverageState.MISSING,
            automation_required=False,
            notes="Important expansion path, but not required for the first fresh strong zone automation gate.",
        ),
        PlaybookConcept(
            name="proximal_distal_zone_lines",
            source="Session 1",
            state=PlaybookCoverageState.PARTIAL,
            automation_required=False,
            notes="Zone high/low boundaries exist, but explicit proximal/distal entry-stop semantics are not surfaced as first-class evidence.",
        ),
        PlaybookConcept(
            name="base_quality_patterns",
            source="Session 1",
            state=PlaybookCoverageState.PARTIAL,
            automation_required=False,
            notes="Base body-to-range threshold exists; 1-6 candle bases, hammer/doji/marubozu classification, and doji danger scoring are not implemented.",
        ),
        PlaybookConcept(
            name="fresh_original_retested_taxonomy",
            source="Session 1",
            state=PlaybookCoverageState.PARTIAL,
            automation_required=False,
            notes="Fresh/retested lifecycle is implemented; original-zone classification is not implemented.",
        ),
        PlaybookConcept(
            name="cp_pcp_arrival_realignment",
            source="Echo/Raja/Session 1-2",
            state=PlaybookCoverageState.MISSING,
            automation_required=False,
            notes="CP, PCP, arrival, and realignment concepts are documented visually; they should become separate deterministic detectors/specs.",
        ),
        PlaybookConcept(
            name="gap_zone_before_gap",
            source="Session 1",
            state=PlaybookCoverageState.MISSING,
            automation_required=False,
            notes="Docs say gaps are clues and the zone before the gap is trade-relevant; no gap detector exists.",
        ),
        PlaybookConcept(
            name="stairs_zone_rejection",
            source="Session 1",
            state=PlaybookCoverageState.MISSING,
            automation_required=False,
            notes="Docs classify stairs zones as poor quality; no detector rejects stair-step zones yet.",
        ),
        PlaybookConcept(
            name="touch_confirmation_rules",
            source="Session 2",
            state=PlaybookCoverageState.MISSING,
            automation_required=False,
            notes="Monthly third-touch and weekly/daily second-touch confirmation rules are documented but not executable.",
        ),
        PlaybookConcept(
            name="inheritance_and_flip_zones",
            source="Session 2",
            state=PlaybookCoverageState.MISSING,
            automation_required=False,
            notes="Inheritance and flip-zone context is documented; no classifier exists.",
        ),
        PlaybookConcept(
            name="trendline_break_change",
            source="Session 2-3",
            state=PlaybookCoverageState.MISSING,
            automation_required=False,
            notes="Docs use last two swing highs/lows for trendline and require trendline break plus opposing-zone removal for trend change; no trendline detector is wired.",
        ),
        PlaybookConcept(
            name="nested_monthly_curve_model",
            source="Session 3",
            state=PlaybookCoverageState.PARTIAL,
            automation_required=False,
            notes="0-25% monthly buyer/seller edge is implemented as a higher-timeframe curve filter; full monthly supply/demand area nesting and 50% middle-zone treatment are not complete.",
        ),
        PlaybookConcept(
            name="pob_setup_families",
            source="PoB",
            state=PlaybookCoverageState.MISSING,
            automation_required=False,
            notes="RBR, DBD, RBD, DBR, SNRC, QML/QMC/QMM, blindspots, manipulation, CLAB, CK variants are not executable yet.",
        ),
    )
    blockers = tuple(
        concept.name
        for concept in concepts
        if concept.automation_required and concept.state != PlaybookCoverageState.IMPLEMENTED
    )
    return PlaybookCoverageReport(
        automation_ready=not blockers,
        implemented_count=sum(1 for concept in concepts if concept.state == PlaybookCoverageState.IMPLEMENTED),
        partial_count=sum(1 for concept in concepts if concept.state == PlaybookCoverageState.PARTIAL),
        missing_count=sum(1 for concept in concepts if concept.state == PlaybookCoverageState.MISSING),
        required_blockers=blockers,
        concepts=concepts,
    )
