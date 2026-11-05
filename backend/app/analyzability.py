"""Decides whether a video can be analyzed at all, before any AI is involved."""
from __future__ import annotations

from typing import Sequence

from app.measure import CONFIDENCE_THRESHOLD, KEY_GROUPS, group_confidence
from app.pose import PoseFrame

NO_PERSON = "Couldn't analyze: no person found"
BODY_NOT_VISIBLE = "Couldn't analyze: body not clearly visible"
NO_REPS = "Couldn't analyze: no reps found"


def check_analyzable(frames: Sequence[PoseFrame], rep_count: int) -> str | None:
    """Returns the reason the video can't be analyzed, or None if it can."""
    if not any(f.landmarks for f in frames):
        return NO_PERSON
    unclear = sum(
        1 for f in frames
        if not f.landmarks or any(group_confidence(f, g) < CONFIDENCE_THRESHOLD for g in KEY_GROUPS)
    )
    if unclear > len(frames) / 2:
        return BODY_NOT_VISIBLE
    if rep_count == 0:
        return NO_REPS
    return None
