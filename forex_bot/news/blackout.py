import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from forex_bot.config import NewsConfig


_IMPACT_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


@dataclass(frozen=True)
class EconomicCalendarEvent:
    title: str
    currency: str
    impact: str
    starts_at: datetime
    source: str = "local"


@dataclass(frozen=True)
class NewsBlackoutDecision:
    blocked: bool
    reason: str
    matched_events: tuple[EconomicCalendarEvent, ...]
    checked_event_count: int


def evaluate_news_blackout(
    symbol: str,
    now: datetime,
    events: tuple[EconomicCalendarEvent, ...],
    before_minutes: int = 60,
    after_minutes: int = 30,
    min_impact: str = "high",
) -> NewsBlackoutDecision:
    currencies = _symbol_currencies(symbol)
    normalized_now = now.astimezone(timezone.utc)
    threshold = _IMPACT_RANK.get(min_impact.lower(), _IMPACT_RANK["high"])
    matched = tuple(
        event
        for event in events
        if event.currency.upper() in currencies
        and _IMPACT_RANK.get(event.impact.lower(), 0) >= threshold
        and event.starts_at - timedelta(minutes=before_minutes) <= normalized_now <= event.starts_at + timedelta(minutes=after_minutes)
    )
    if matched:
        labels = ", ".join(f"{event.currency.upper()} {event.impact.lower()} {event.title}" for event in matched)
        return NewsBlackoutDecision(
            blocked=True,
            reason=f"Scheduled economic-news blackout active: {labels}.",
            matched_events=matched,
            checked_event_count=len(events),
        )
    return NewsBlackoutDecision(
        blocked=False,
        reason="No scheduled high-impact event is inside the configured blackout window.",
        matched_events=(),
        checked_event_count=len(events),
    )


def blackout_from_config(symbol: str, now: datetime, config: NewsConfig) -> NewsBlackoutDecision:
    if not config.blackout_enabled:
        return NewsBlackoutDecision(
            blocked=False,
            reason="News blackout gate is disabled by configuration.",
            matched_events=(),
            checked_event_count=0,
        )
    if not config.blackout_events_file:
        return NewsBlackoutDecision(
            blocked=False,
            reason="No economic-calendar event file is configured.",
            matched_events=(),
            checked_event_count=0,
        )
    events = load_economic_events(config.blackout_events_file)
    return evaluate_news_blackout(
        symbol=symbol,
        now=now,
        events=events,
        before_minutes=config.blackout_before_minutes,
        after_minutes=config.blackout_after_minutes,
        min_impact=config.blackout_min_impact,
    )


def load_economic_events(path: str | Path) -> tuple[EconomicCalendarEvent, ...]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("economic-calendar event file must contain a JSON list")
    return tuple(_event_from_row(row) for row in rows)


def _event_from_row(row) -> EconomicCalendarEvent:
    if not isinstance(row, dict):
        raise ValueError("economic-calendar event rows must be objects")
    return EconomicCalendarEvent(
        title=str(row.get("title", "")),
        currency=str(row.get("currency", "")).upper(),
        impact=str(row.get("impact", "")).lower(),
        starts_at=_parse_time(str(row.get("starts_at", ""))),
        source=str(row.get("source", "local")),
    )


def _parse_time(value: str) -> datetime:
    if not value:
        raise ValueError("economic-calendar event requires starts_at")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _symbol_currencies(symbol: str) -> set[str]:
    clean = symbol.replace("/", "").replace("_", "").upper()
    if len(clean) < 6:
        return {clean}
    return {clean[:3], clean[3:6]}
