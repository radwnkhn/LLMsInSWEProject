"""US-27: usage over time and moderation removals. Plain functions; the API wires them to the repository."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

# The only reasons an admin can give for removing an upload (value -> label).
REMOVAL_REASONS = {"off_topic": "Off-topic", "inappropriate": "Inappropriate", "other": "Other"}
MAX_REMOVAL_NOTE_LENGTH = 200
REMOVED_MESSAGE = "This upload was removed by a moderator"


def _utc_day(moment: datetime) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).date()


def daily_usage(signups: Iterable[datetime], uploads: Iterable[datetime], start: date, end: date) -> dict:
    """Sign-ups and uploads per UTC day from start to end (inclusive), zero days included, plus totals."""
    days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
    in_range = lambda times: Counter(d for d in map(_utc_day, times) if start <= d <= end)
    signed_up, uploaded = in_range(signups), in_range(uploads)
    return {
        "days": [{"date": d.isoformat(), "signups": signed_up[d], "uploads": uploaded[d]} for d in days],
        "totals": {"signups": sum(signed_up.values()), "uploads": sum(uploaded.values())},
    }


def removed_detail(reason: str) -> str:
    """What the owner of a removed upload is told."""
    return f"{REMOVED_MESSAGE}. Reason: {REMOVAL_REASONS.get(reason, 'Other')}."
