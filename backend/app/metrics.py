"""US-23: the hypothesis metrics on the admin dashboard, each against its target and fail line.

Grades (US-22), ratings and cue answers (US-16) are counted for analyses created in the chosen range. A lifter
counts toward 7-day return when their first upload is in the range and at least 7 days old.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

RETURN_WINDOW = timedelta(days=7)
HELPFUL_RATING = 4  # ratings of 4 or 5 out of 5


@dataclass(frozen=True)
class Target:
    label: str
    target: float       # on target at or above this share
    fail_below: float   # failing below this share
    point: tuple[str, str]  # what one data point is, singular and plural


TARGETS: dict[str, Target] = {
    "trainer_agreement": Target("Trainer agreement", 0.8, 0.6, ("graded set", "graded sets")),
    "helpful_ratings": Target("Helpful ratings (4–5)", 0.7, 0.5, ("rating", "ratings")),
    "cue_tried": Target("Cue tried", 0.6, 0.4, ("answer", "answers")),
    "seven_day_return": Target("7-day return", 0.5, 0.3, ("lifter", "lifters")),
}
STATUS_LABELS = {"on_target": "On target", "below_target": "Below target", "failing": "Failing", "no_data": "No data"}


def status(value: float | None, target: float, fail_below: float) -> str:
    if value is None:
        return "no_data"
    if value >= target:
        return "on_target"
    return "below_target" if value >= fail_below else "failing"


def trainer_agreement(verdicts: Iterable[str]) -> tuple[int, int]:
    """(marked correct, graded). "Partly correct" doesn't count as agreeing."""
    verdicts = list(verdicts)
    return sum(v == "correct" for v in verdicts), len(verdicts)


def helpful_ratings(ratings: Iterable[int | None]) -> tuple[int, int]:
    rated = [r for r in ratings if r is not None]
    return sum(r >= HELPFUL_RATING for r in rated), len(rated)


def cue_tried(answers: Iterable[str | None]) -> tuple[int, int]:
    """(yes, yes or no). "Not yet" isn't an answer about whether the cue was tried."""
    answered = [a for a in answers if a in ("yes", "no")]
    return answered.count("yes"), len(answered)


def seven_day_return(uploads: Iterable[tuple[str, datetime]], since: datetime, until: datetime,
                     now: datetime) -> tuple[int, int, int]:
    """(came back, counted, still waiting) for lifters whose first upload is in [since, until).

    A lifter came back if they uploaded again within 7 days of their first upload. Lifters whose first upload is
    less than 7 days old can't be judged yet, so they are only counted as waiting."""
    by_user: dict[str, list[datetime]] = {}
    for user_id, when in uploads:
        by_user.setdefault(user_id, []).append(when)
    came_back = counted = waiting = 0
    for times in by_user.values():
        times.sort()
        first = times[0]
        if not since <= first < until:
            continue
        if first + RETURN_WINDOW > now:
            waiting += 1
            continue
        counted += 1
        came_back += any(first < t <= first + RETURN_WINDOW for t in times[1:])
    return came_back, counted, waiting


def metric(key: str, hits: int, count: int) -> dict:
    t = TARGETS[key]
    value = hits / count if count else None
    s = status(value, t.target, t.fail_below)
    return {"key": key, "label": t.label, "value": value, "hits": hits, "count": count,
            "basis": f"{count} {t.point[0] if count == 1 else t.point[1]}", "target": t.target,
            "fail_below": t.fail_below, "status": s, "status_label": STATUS_LABELS[s]}


def build_metrics(verdicts, ratings, tried, uploads, since: datetime, until: datetime, now: datetime) -> list[dict]:
    came_back, counted, _ = seven_day_return(uploads, since, until, now)
    return [metric("trainer_agreement", *trainer_agreement(verdicts)),
            metric("helpful_ratings", *helpful_ratings(ratings)),
            metric("cue_tried", *cue_tried(tried)),
            metric("seven_day_return", came_back, counted)]
