"""Feedback on results, and the follow-up question about the previous cue."""
from __future__ import annotations

ANSWERED = ("yes", "no")  # "not_yet" means ask again next time


def find_previous_cue_prompt(repo, user_id: str, lift: str, current_analysis_id: str) -> dict | None:
    """The cue from this lifter's most recent earlier result for the same lift, if they haven't said whether they
    tried it. None when there's nothing to ask."""
    analyses = repo.list_analyses_for_user(user_id, lift=lift)
    ids = [a.id for a in analyses]
    if current_analysis_id not in ids:
        return None
    for a in analyses[ids.index(current_analysis_id) + 1:]:
        cue = (a.result or {}).get("cue")
        if a.status != "done" or not cue:
            continue
        answer = repo.get_feedback(a.id, user_id)
        if answer and answer.tried_cue in ANSWERED:
            return None
        return {"analysis_id": a.id, "cue": cue, "lift": lift}
    return None
