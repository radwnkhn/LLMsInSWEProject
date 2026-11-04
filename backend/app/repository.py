"""Data access. InMemoryRepository for tests and test mode; PostgresRepository for Supabase Postgres."""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.llm.schema import ValidationIssue
from app.measure import RepMeasurement


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UserRecord:
    id: str
    email: str
    is_admin: bool = False


@dataclass
class UploadRecord:
    id: str
    user_id: str
    lift: str
    video_path: str
    filename: str
    note: str | None = None
    created_at: datetime | None = None


@dataclass
class AnalysisRecord:
    id: str
    upload_id: str
    user_id: str
    lift: str
    status: str = "queued"               # queued | processing | done | failed
    final_status: str | None = None      # passed_first_try | passed_after_retry | fallback | unanalyzable
    rep_count: int | None = None
    camera_angle: str | None = None
    top_fault_id: str | None = None
    result: dict | None = None           # exactly what the user was shown
    unanalyzable_reason: str | None = None
    frame_path: str | None = None
    error: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class LLMAttemptRecord:
    id: str
    analysis_id: str
    attempt_number: int
    output_text: str
    input_tokens: int
    output_tokens: int
    issues: list[ValidationIssue] = field(default_factory=list)
    passed: bool = False
    created_at: datetime | None = None


@dataclass
class FeedbackRecord:
    analysis_id: str
    user_id: str
    rating: int | None
    tried_cue: str | None
    updated_at: datetime | None = None


@dataclass
class AdminAnalysisRow:
    analysis: AnalysisRecord
    attempt_count: int
    user_email: str


ANALYSIS_FIELDS = {"status", "final_status", "rep_count", "camera_angle", "top_fault_id", "result",
                   "unanalyzable_reason", "frame_path", "error", "completed_at"}


class Repository(Protocol):
    def ensure_user(self, id: str, email: str, is_admin: bool = False) -> UserRecord: ...
    def get_user(self, id: str) -> UserRecord | None: ...
    def create_upload(self, id: str, user_id: str, lift: str, video_path: str, filename: str, note: str | None) -> UploadRecord: ...
    def get_upload(self, id: str) -> UploadRecord | None: ...
    def create_analysis(self, id: str, upload_id: str, user_id: str, lift: str) -> AnalysisRecord: ...
    def update_analysis(self, id: str, **fields) -> None: ...
    def get_analysis(self, id: str) -> AnalysisRecord | None: ...
    def list_analyses_for_user(self, user_id: str, lift: str | None = None) -> list[AnalysisRecord]: ...
    def save_rep_measurements(self, analysis_id: str, reps: list[RepMeasurement]) -> None: ...
    def list_rep_measurements(self, analysis_id: str) -> list[RepMeasurement]: ...
    def save_llm_attempt(self, analysis_id: str, attempt_number: int, output_text: str, input_tokens: int,
                         output_tokens: int, issues: list[ValidationIssue]) -> LLMAttemptRecord: ...
    def list_llm_attempts(self, analysis_id: str) -> list[LLMAttemptRecord]: ...
    def all_validation_issues(self) -> list[ValidationIssue]: ...
    def upsert_feedback(self, analysis_id: str, user_id: str, rating: int | None, tried_cue: str | None) -> FeedbackRecord: ...
    def get_feedback(self, analysis_id: str, user_id: str) -> FeedbackRecord | None: ...
    def list_feedback(self, analysis_id: str) -> list[FeedbackRecord]: ...
    def list_admin_rows(self, lift: str | None = None, final_status: str | None = None) -> list[AdminAnalysisRow]: ...


class InMemoryRepository:
    def __init__(self):
        self._lock = threading.Lock()
        self._last = _now()
        self.users: dict[str, UserRecord] = {}
        self.uploads: dict[str, UploadRecord] = {}
        self.analyses: dict[str, AnalysisRecord] = {}
        self.reps: dict[str, list[RepMeasurement]] = {}
        self.attempts: dict[str, list[LLMAttemptRecord]] = {}
        self.feedback: dict[tuple[str, str], FeedbackRecord] = {}

    def _stamp(self) -> datetime:
        # Strictly increasing timestamps, so "newest first" is well defined even within one clock tick.
        with self._lock:
            now = _now()
            self._last = now if now > self._last else self._last + timedelta(microseconds=1)
            return self._last

    def ensure_user(self, id, email, is_admin=False):
        user = UserRecord(id, email, is_admin)
        self.users[id] = user
        return user

    def get_user(self, id):
        return self.users.get(id)

    def create_upload(self, id, user_id, lift, video_path, filename, note):
        rec = UploadRecord(id, user_id, lift, video_path, filename, note, self._stamp())
        self.uploads[id] = rec
        return rec

    def get_upload(self, id):
        return self.uploads.get(id)

    def create_analysis(self, id, upload_id, user_id, lift):
        rec = AnalysisRecord(id=id, upload_id=upload_id, user_id=user_id, lift=lift, created_at=self._stamp())
        self.analyses[id] = rec
        return rec

    def update_analysis(self, id, **fields):
        unknown = set(fields) - ANALYSIS_FIELDS
        if unknown:
            raise ValueError(f"unknown analysis fields: {unknown}")
        self.analyses[id] = replace(self.analyses[id], **fields)

    def get_analysis(self, id):
        return self.analyses.get(id)

    def list_analyses_for_user(self, user_id, lift=None):
        rows = [a for a in self.analyses.values() if a.user_id == user_id and (lift is None or a.lift == lift)]
        return sorted(rows, key=lambda a: a.created_at, reverse=True)

    def save_rep_measurements(self, analysis_id, reps):
        self.reps[analysis_id] = [RepMeasurement.from_dict(r.to_dict()) for r in reps]

    def list_rep_measurements(self, analysis_id):
        return list(self.reps.get(analysis_id, []))

    def save_llm_attempt(self, analysis_id, attempt_number, output_text, input_tokens, output_tokens, issues):
        rec = LLMAttemptRecord(str(uuid.uuid4()), analysis_id, attempt_number, output_text, input_tokens,
                               output_tokens, list(issues), not issues, self._stamp())
        self.attempts.setdefault(analysis_id, []).append(rec)
        return rec

    def list_llm_attempts(self, analysis_id):
        return sorted(self.attempts.get(analysis_id, []), key=lambda a: a.attempt_number)

    def all_validation_issues(self):
        return [i for attempts in self.attempts.values() for a in attempts for i in a.issues]

    def upsert_feedback(self, analysis_id, user_id, rating, tried_cue):
        old = self.feedback.get((analysis_id, user_id))
        rec = FeedbackRecord(analysis_id, user_id,
                             rating if rating is not None else (old.rating if old else None),
                             tried_cue if tried_cue is not None else (old.tried_cue if old else None), self._stamp())
        self.feedback[(analysis_id, user_id)] = rec
        return rec

    def get_feedback(self, analysis_id, user_id):
        return self.feedback.get((analysis_id, user_id))

    def list_feedback(self, analysis_id):
        return [f for (aid, _), f in self.feedback.items() if aid == analysis_id]

    def list_admin_rows(self, lift=None, final_status=None):
        rows = [a for a in self.analyses.values()
                if (lift is None or a.lift == lift) and (final_status is None or a.final_status == final_status)]
        rows.sort(key=lambda a: a.created_at, reverse=True)
        return [AdminAnalysisRow(a, len(self.attempts.get(a.id, [])), self.users.get(a.user_id, UserRecord(a.user_id, "")).email)
                for a in rows]


class PostgresRepository:
    """Talks to Supabase Postgres directly with a server-side connection (bypasses RLS; the API checks ownership)."""

    def __init__(self, dsn: str):
        from psycopg_pool import ConnectionPool

        self.pool = ConnectionPool(dsn, min_size=1, max_size=5, kwargs={"autocommit": True}, open=True)

    def _q(self, sql: str, params=(), one=False, rows=False):
        from psycopg.rows import dict_row

        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            if one:
                return cur.fetchone()
            if rows:
                return cur.fetchall()
            return None

    @staticmethod
    def _analysis(r) -> AnalysisRecord | None:
        if r is None:
            return None
        return AnalysisRecord(id=str(r["id"]), upload_id=str(r["upload_id"]), user_id=str(r["user_id"]), lift=r["lift"],
                              status=r["status"], final_status=r["final_status"], rep_count=r["rep_count"],
                              camera_angle=r["camera_angle"], top_fault_id=r["top_fault_id"], result=r["result"],
                              unanalyzable_reason=r["unanalyzable_reason"], frame_path=r["frame_path"],
                              error=r["error"], created_at=r["created_at"], completed_at=r["completed_at"])

    def ensure_user(self, id, email, is_admin=False):
        self._q("insert into public.users (id, email, is_admin) values (%s, %s, %s) "
                "on conflict (id) do update set email = excluded.email, is_admin = excluded.is_admin",
                (id, email, is_admin))
        return UserRecord(id, email, is_admin)

    def get_user(self, id):
        r = self._q("select * from public.users where id::text = %s", (id,), one=True)
        return r and UserRecord(str(r["id"]), r["email"], r["is_admin"])

    def create_upload(self, id, user_id, lift, video_path, filename, note):
        r = self._q("insert into public.uploads (id, user_id, lift, video_path, filename, note) "
                    "values (%s, %s, %s, %s, %s, %s) returning created_at",
                    (id, user_id, lift, video_path, filename, note), one=True)
        return UploadRecord(id, user_id, lift, video_path, filename, note, r["created_at"])

    def get_upload(self, id):
        r = self._q("select * from public.uploads where id::text = %s", (id,), one=True)
        return r and UploadRecord(str(r["id"]), str(r["user_id"]), r["lift"], r["video_path"], r["filename"],
                                  r["note"], r["created_at"])

    def create_analysis(self, id, upload_id, user_id, lift):
        r = self._q("insert into public.analyses (id, upload_id, user_id, lift) values (%s, %s, %s, %s) returning *",
                    (id, upload_id, user_id, lift), one=True)
        return self._analysis(r)

    def update_analysis(self, id, **fields):
        unknown = set(fields) - ANALYSIS_FIELDS
        if unknown:
            raise ValueError(f"unknown analysis fields: {unknown}")
        if "result" in fields and fields["result"] is not None:
            fields["result"] = json.dumps(fields["result"])
        sets = ", ".join(f"{k} = %s" for k in fields)
        self._q(f"update public.analyses set {sets} where id = %s", (*fields.values(), id))

    def get_analysis(self, id):
        return self._analysis(self._q("select * from public.analyses where id::text = %s", (id,), one=True))

    def list_analyses_for_user(self, user_id, lift=None):
        rows = self._q("select * from public.analyses where user_id = %s and (%s::text is null or lift = %s) "
                       "order by created_at desc", (user_id, lift, lift), rows=True)
        return [self._analysis(r) for r in rows]

    def save_rep_measurements(self, analysis_id, reps):
        for r in reps:
            d = r.to_dict()
            self._q("insert into public.rep_measurements (analysis_id, rep, start_frame, turn_frame, end_frame, "
                    "start_time, end_time, metrics, worst_frames, depth_reached) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (analysis_id, d["rep"], d["start_frame"], d["turn_frame"], d["end_frame"], d["start_time"],
                     d["end_time"], json.dumps(d["metrics"]), json.dumps(d["worst_frames"]), d["depth_reached"]))

    def list_rep_measurements(self, analysis_id):
        rows = self._q("select * from public.rep_measurements where analysis_id::text = %s order by rep",
                       (analysis_id,), rows=True)
        return [RepMeasurement.from_dict(r) for r in rows]

    def save_llm_attempt(self, analysis_id, attempt_number, output_text, input_tokens, output_tokens, issues):
        r = self._q("insert into public.llm_attempts (analysis_id, attempt_number, output_text, input_tokens, "
                    "output_tokens, passed) values (%s,%s,%s,%s,%s,%s) returning id, created_at",
                    (analysis_id, attempt_number, output_text, input_tokens, output_tokens, not issues), one=True)
        for issue in issues:
            self._q("insert into public.validation_results (attempt_id, analysis_id, code, message) values (%s,%s,%s,%s)",
                    (r["id"], analysis_id, issue.code, issue.message))
        return LLMAttemptRecord(str(r["id"]), analysis_id, attempt_number, output_text, input_tokens, output_tokens,
                                list(issues), not issues, r["created_at"])

    def list_llm_attempts(self, analysis_id):
        rows = self._q("select * from public.llm_attempts where analysis_id::text = %s order by attempt_number",
                       (analysis_id,), rows=True)
        issues = self._q("select attempt_id, code, message from public.validation_results where analysis_id::text = %s "
                         "order by id", (analysis_id,), rows=True)
        by_attempt: dict = {}
        for i in issues:
            by_attempt.setdefault(i["attempt_id"], []).append(ValidationIssue(i["code"], i["message"]))
        return [LLMAttemptRecord(str(r["id"]), str(r["analysis_id"]), r["attempt_number"], r["output_text"],
                                 r["input_tokens"], r["output_tokens"], by_attempt.get(r["id"], []), r["passed"],
                                 r["created_at"]) for r in rows]

    def all_validation_issues(self):
        return [ValidationIssue(r["code"], r["message"])
                for r in self._q("select code, message from public.validation_results", rows=True)]

    def upsert_feedback(self, analysis_id, user_id, rating, tried_cue):
        r = self._q("insert into public.feedback_responses (analysis_id, user_id, rating, tried_cue) "
                    "values (%s, %s, %s, %s) on conflict (analysis_id, user_id) do update set "
                    "rating = coalesce(excluded.rating, feedback_responses.rating), "
                    "tried_cue = coalesce(excluded.tried_cue, feedback_responses.tried_cue), updated_at = now() "
                    "returning *", (analysis_id, user_id, rating, tried_cue), one=True)
        return FeedbackRecord(str(r["analysis_id"]), str(r["user_id"]), r["rating"], r["tried_cue"], r["updated_at"])

    def get_feedback(self, analysis_id, user_id):
        r = self._q("select * from public.feedback_responses where analysis_id::text = %s and user_id::text = %s",
                    (analysis_id, user_id), one=True)
        return r and FeedbackRecord(str(r["analysis_id"]), str(r["user_id"]), r["rating"], r["tried_cue"], r["updated_at"])

    def list_feedback(self, analysis_id):
        rows = self._q("select * from public.feedback_responses where analysis_id::text = %s", (analysis_id,), rows=True)
        return [FeedbackRecord(str(r["analysis_id"]), str(r["user_id"]), r["rating"], r["tried_cue"], r["updated_at"])
                for r in rows]

    def list_admin_rows(self, lift=None, final_status=None):
        rows = self._q(
            "select a.*, u.email as user_email, (select count(*) from public.llm_attempts t where t.analysis_id = a.id) "
            "as attempt_count from public.analyses a left join public.users u on u.id = a.user_id "
            "where (%s::text is null or a.lift = %s) and (%s::text is null or a.final_status = %s) "
            "order by a.created_at desc", (lift, lift, final_status, final_status), rows=True)
        return [AdminAnalysisRow(self._analysis(r), r["attempt_count"], r["user_email"] or "") for r in rows]

