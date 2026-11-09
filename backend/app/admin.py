"""Admin views over analyses, LLM attempts and validator errors."""
from __future__ import annotations

from collections import Counter

from app.history import JOB_LABELS
from app.lifts import LIFT_LABELS
from app.llm.schema import ValidationIssue
from app.repository import AdminAnalysisRow

FINAL_STATUS_LABELS = {
    "passed_first_try": "Passed first try",
    "passed_after_retry": "Passed after retry",
    "fallback": "Fallback",
    "unanalyzable": "Couldn't analyze",
}


def filter_admin_rows(rows: list[AdminAnalysisRow], lift: str | None = None,
                      final_status: str | None = None) -> list[AdminAnalysisRow]:
    return [r for r in rows if (lift is None or r.analysis.lift == lift)
            and (final_status is None or r.analysis.final_status == final_status)]


def summarize_validation_errors(issues: list[ValidationIssue]) -> dict[str, int]:
    """How often each validator error type occurred, most common first."""
    return dict(Counter(i.code for i in issues).most_common())


def admin_row_view(row: AdminAnalysisRow) -> dict:
    a = row.analysis
    return {
        "analysis_id": a.id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "user_email": row.user_email,
        "lift": a.lift,
        "lift_label": LIFT_LABELS[a.lift],
        "attempt_count": row.attempt_count,
        "final_status": a.final_status,
        "final_status_label": FINAL_STATUS_LABELS.get(a.final_status) or JOB_LABELS.get(a.status, a.status),
    }
