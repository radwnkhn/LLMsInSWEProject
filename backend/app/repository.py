"""Data access. InMemoryRepository for tests and test mode; PostgresRepository for Supabase Postgres."""
from __future__ import annotations

import json
import threading
import uuid
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import ContextManager, Protocol

from app.faults import FAULT_EDITABLE_FIELDS, Fault, FaultExists, default_faults, edit_fault
from app.llm.schema import ValidationIssue
from app.pricing import AttemptUsage
from app.measure import RepMeasurement


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UserRecord:
    id: str
    email: str
    is_admin: bool = False
    created_at: datetime | None = None  # US-27: when they signed up
    is_trainer: bool = False             # US-22


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
    processing_stage: str | None = None  # measuring | writing_feedback | checking


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
    provider: str | None = None  # US-26; None for attempts saved before usage tracking
    model: str | None = None


@dataclass
class FeedbackRecord:
    analysis_id: str
    user_id: str
    rating: int | None
    tried_cue: str | None
    updated_at: datetime | None = None


@dataclass
class AdminUploadRow:
    """US-27: an upload for the moderation list, with its owner and newest analysis."""
    upload: UploadRecord
    user_email: str
    analysis: AnalysisRecord | None


@dataclass
class ModerationEntry:
    """US-27: one admin removal. Outlives the upload; user references become None if an account is deleted."""
    id: str
    upload_id: str
    analysis_ids: list[str]
    lift: str
    owner_id: str | None
    removed_by: str | None
    reason: str
    note: str | None
    removed_at: datetime | None
    owner_email: str | None = None
    removed_by_email: str | None = None


@dataclass
class ThresholdChange:
    """US-24: one change to a fault's threshold. The admin reference becomes None if their account is deleted."""
    lift: str
    fault_id: str
    old_threshold: float
    new_threshold: float
    changed_by: str | None
    changed_at: datetime | None
    changed_by_email: str | None = None


@dataclass
class GradingAssignment:
    """US-22: one analysis sent to a trainer. trainer_fault_id None with answered_at set means "No major issue"."""
    id: str
    analysis_id: str
    trainer_id: str
    assigned_by: str | None
    assigned_at: datetime | None
    trainer_fault_id: str | None = None
    answered_at: datetime | None = None
    verdict: str | None = None           # correct | partly_correct | wrong
    graded_at: datetime | None = None
    trainer_email: str | None = None


@dataclass
class AdminAnalysisRow:
    analysis: AnalysisRecord
    attempt_count: int
    user_email: str


ANALYSIS_FIELDS = {"status", "final_status", "rep_count", "camera_angle", "top_fault_id", "result",
                   "unanalyzable_reason", "frame_path", "error", "completed_at", "processing_stage"}


class Repository(Protocol):
    def user_lock(self, user_id: str) -> ContextManager[None]: ...
    def ensure_user(self, id: str, email: str, is_admin: bool = False, is_trainer: bool = False) -> UserRecord: ...
    def get_user(self, id: str) -> UserRecord | None: ...
    # US-22: trainers and their grading assignments. Answers and verdicts return None when not allowed yet.
    def list_trainers(self) -> list[UserRecord]: ...
    def create_assignments(self, trainer_id: str, analysis_ids: list[str], assigned_by: str | None) -> list[GradingAssignment]: ...
    def list_assignments(self, trainer_id: str | None = None) -> list[GradingAssignment]: ...
    def get_assignment(self, id: str) -> GradingAssignment | None: ...
    def save_trainer_answer(self, id: str, fault_id: str | None) -> GradingAssignment | None: ...
    def save_verdict(self, id: str, verdict: str) -> GradingAssignment | None: ...
    # US-23: the data points behind the hypothesis metrics. Ranges are [start, end) of analysis creation.
    def list_feedback_between(self, start: datetime, end: datetime) -> list[FeedbackRecord]: ...
    def list_graded_verdicts(self, start: datetime, end: datetime) -> list[str]: ...
    def list_upload_times(self) -> list[tuple[str, datetime]]: ...
    def create_upload(self, id: str, user_id: str, lift: str, video_path: str, filename: str, note: str | None) -> UploadRecord: ...
    def get_upload(self, id: str) -> UploadRecord | None: ...
    def list_uploads_for_user(self, user_id: str) -> list[UploadRecord]: ...
    def delete_upload(self, upload_id: str) -> None: ...
    def delete_user(self, user_id: str) -> None: ...
    def create_analysis(self, id: str, upload_id: str, user_id: str, lift: str) -> AnalysisRecord: ...
    def update_analysis(self, id: str, **fields) -> None: ...
    def get_analysis(self, id: str) -> AnalysisRecord | None: ...
    def list_analyses_for_user(self, user_id: str, lift: str | None = None) -> list[AnalysisRecord]: ...
    def save_rep_measurements(self, analysis_id: str, reps: list[RepMeasurement]) -> None: ...
    def list_rep_measurements(self, analysis_id: str) -> list[RepMeasurement]: ...
    def save_llm_attempt(self, analysis_id: str, attempt_number: int, output_text: str, input_tokens: int,
                         output_tokens: int, issues: list[ValidationIssue], provider: str | None = None,
                         model: str | None = None) -> LLMAttemptRecord: ...
    # US-26: every attempt of analyses created in [start, end), for cost summaries.
    def list_attempt_usage(self, start: datetime, end: datetime) -> list[AttemptUsage]: ...
    # US-27: usage over time and the moderation log. Ranges are [start, end).
    def list_signup_times(self, start: datetime, end: datetime) -> list[datetime]: ...
    def list_upload_rows(self, start: datetime, end: datetime, lift: str | None = None) -> list[AdminUploadRow]: ...
    def create_moderation_entry(self, upload_id: str, analysis_ids: list[str], lift: str, owner_id: str,
                                removed_by: str, reason: str, note: str | None) -> ModerationEntry: ...
    def delete_moderation_entry(self, entry_id: str) -> None: ...
    def list_moderation_entries(self) -> list[ModerationEntry]: ...
    def get_removal_for_analysis(self, analysis_id: str) -> ModerationEntry | None: ...
    def list_llm_attempts(self, analysis_id: str) -> list[LLMAttemptRecord]: ...
    def all_validation_issues(self) -> list[ValidationIssue]: ...
    def upsert_feedback(self, analysis_id: str, user_id: str, rating: int | None, tried_cue: str | None) -> FeedbackRecord: ...
    def get_feedback(self, analysis_id: str, user_id: str) -> FeedbackRecord | None: ...
    def list_feedback(self, analysis_id: str) -> list[FeedbackRecord]: ...
    def list_admin_rows(self, lift: str | None = None, final_status: str | None = None) -> list[AdminAnalysisRow]: ...
    # US-25: the saved fault list. Seeded with app.faults.FAULTS; faults are disabled, never deleted.
    def list_faults(self) -> list[Fault]: ...
    def get_fault(self, lift: str, fault_id: str) -> Fault | None: ...
    def create_fault(self, fault: Fault) -> Fault: ...
    # US-24: a threshold change is logged with changed_by; other edits and unchanged values aren't.
    def update_fault(self, lift: str, fault_id: str, changed_by: str | None = None, **fields) -> Fault: ...
    def list_threshold_changes(self) -> list[ThresholdChange]: ...


def _check_fault_fields(fields: dict) -> None:
    """Only FAULT_EDITABLE_FIELDS can change."""
    unknown = set(fields) - FAULT_EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"unknown or read-only fault fields: {sorted(unknown)}")


class InMemoryRepository:
    def __init__(self):
        self._lock = threading.Lock()
        self._user_locks: dict[str, threading.RLock] = {}
        self._last = _now()
        self.users: dict[str, UserRecord] = {}
        self.uploads: dict[str, UploadRecord] = {}
        self.analyses: dict[str, AnalysisRecord] = {}
        self.reps: dict[str, list[RepMeasurement]] = {}
        self.attempts: dict[str, list[LLMAttemptRecord]] = {}
        self.feedback: dict[tuple[str, str], FeedbackRecord] = {}
        self.faults: list[Fault] = default_faults()
        self.moderation: list[ModerationEntry] = []
        self.threshold_changes: list[ThresholdChange] = []
        self.assignments: dict[str, GradingAssignment] = {}

    @contextmanager
    def user_lock(self, user_id):
        with self._lock:
            guard = self._user_locks.setdefault(user_id, threading.RLock())
        with guard:
            yield

    def _stamp(self) -> datetime:
        # Strictly increasing timestamps, so "newest first" is well defined even within one clock tick.
        with self._lock:
            now = _now()
            self._last = now if now > self._last else self._last + timedelta(microseconds=1)
            return self._last

    def ensure_user(self, id, email, is_admin=False, is_trainer=False):
        old = self.users.get(id)
        user = UserRecord(id, email, is_admin, old.created_at if old else self._stamp(), is_trainer)
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

    def list_uploads_for_user(self, user_id):
        return [u for u in list(self.uploads.values()) if u.user_id == user_id]

    def delete_upload(self, upload_id):
        analysis_ids = {a.id for a in list(self.analyses.values()) if a.upload_id == upload_id}
        for aid in analysis_ids:
            self.reps.pop(aid, None)
            self.attempts.pop(aid, None)
            self.analyses.pop(aid, None)
        for key in list(self.feedback):
            if key[0] in analysis_ids:
                self.feedback.pop(key, None)
        for key, a in list(self.assignments.items()):
            if a.analysis_id in analysis_ids:
                self.assignments.pop(key, None)
        self.uploads.pop(upload_id, None)

    def delete_user(self, user_id):
        for upload in self.list_uploads_for_user(user_id):
            self.delete_upload(upload.id)
        for key in list(self.feedback):
            if key[1] == user_id:
                self.feedback.pop(key, None)
        # Like the Postgres foreign keys: the moderation log stays, without the deleted account.
        self.moderation = [replace(m, owner_id=None if m.owner_id == user_id else m.owner_id,
                                   removed_by=None if m.removed_by == user_id else m.removed_by)
                           for m in self.moderation]
        self.threshold_changes = [replace(c, changed_by=None) if c.changed_by == user_id else c
                                  for c in self.threshold_changes]
        # Like the Postgres foreign keys: a trainer's assignments go with them; who assigned them is forgotten.
        self.assignments = {k: replace(a, assigned_by=None if a.assigned_by == user_id else a.assigned_by)
                            for k, a in self.assignments.items() if a.trainer_id != user_id}
        self.users.pop(user_id, None)

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
        rows = [a for a in list(self.analyses.values()) if a.user_id == user_id and (lift is None or a.lift == lift)]
        return sorted(rows, key=lambda a: a.created_at, reverse=True)

    def save_rep_measurements(self, analysis_id, reps):
        self.reps[analysis_id] = [RepMeasurement.from_dict(r.to_dict()) for r in reps]

    def list_rep_measurements(self, analysis_id):
        return list(self.reps.get(analysis_id, []))

    def save_llm_attempt(self, analysis_id, attempt_number, output_text, input_tokens, output_tokens, issues,
                         provider=None, model=None):
        rec = LLMAttemptRecord(str(uuid.uuid4()), analysis_id, attempt_number, output_text, input_tokens,
                               output_tokens, list(issues), not issues, self._stamp(), provider, model)
        self.attempts.setdefault(analysis_id, []).append(rec)
        return rec

    def list_llm_attempts(self, analysis_id):
        return sorted(self.attempts.get(analysis_id, []), key=lambda a: a.attempt_number)

    def all_validation_issues(self):
        return [i for attempts in self.attempts.values() for a in attempts for i in a.issues]

    def list_signup_times(self, start, end):
        return [u.created_at for u in list(self.users.values()) if u.created_at and start <= u.created_at < end]

    def list_upload_rows(self, start, end, lift=None):
        rows = []
        for u in sorted(list(self.uploads.values()), key=lambda u: u.created_at, reverse=True):
            if not (start <= u.created_at < end) or (lift is not None and u.lift != lift):
                continue
            analyses = [a for a in list(self.analyses.values()) if a.upload_id == u.id]
            newest = max(analyses, key=lambda a: a.created_at) if analyses else None
            rows.append(AdminUploadRow(u, self.users.get(u.user_id, UserRecord(u.user_id, "")).email, newest))
        return rows

    def _with_emails(self, m):
        email = lambda uid: self.users[uid].email if uid in self.users else None
        return replace(m, owner_email=email(m.owner_id), removed_by_email=email(m.removed_by))

    def create_moderation_entry(self, upload_id, analysis_ids, lift, owner_id, removed_by, reason, note):
        entry = ModerationEntry(str(uuid.uuid4()), upload_id, list(analysis_ids), lift, owner_id, removed_by, reason,
                                note, self._stamp())
        self.moderation.append(entry)
        return self._with_emails(entry)

    def delete_moderation_entry(self, entry_id):
        self.moderation = [m for m in self.moderation if m.id != entry_id]

    def list_moderation_entries(self):
        return [self._with_emails(m) for m in sorted(self.moderation, key=lambda m: m.removed_at, reverse=True)]

    def get_removal_for_analysis(self, analysis_id):
        return next((self._with_emails(m) for m in self.moderation if analysis_id in m.analysis_ids), None)

    def list_attempt_usage(self, start, end):
        rows = []
        for analysis_id, attempts in list(self.attempts.items()):
            analysis = self.analyses.get(analysis_id)
            if analysis is None or not (start <= analysis.created_at < end):
                continue
            rows += [AttemptUsage(analysis_id, analysis.created_at, a.attempt_number, a.input_tokens, a.output_tokens,
                                  a.provider, a.model) for a in attempts]
        return rows

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

    def list_trainers(self):
        return sorted((u for u in list(self.users.values()) if u.is_trainer), key=lambda u: u.email)

    def create_assignments(self, trainer_id, analysis_ids, assigned_by):
        made = []
        for analysis_id in analysis_ids:
            if any((a.analysis_id, a.trainer_id) == (analysis_id, trainer_id) for a in list(self.assignments.values())):
                continue
            rec = GradingAssignment(str(uuid.uuid4()), analysis_id, trainer_id, assigned_by, self._stamp())
            self.assignments[rec.id] = rec
            made.append(self._with_trainer(rec))
        return made

    def _with_trainer(self, a):
        return replace(a, trainer_email=self.users[a.trainer_id].email if a.trainer_id in self.users else None)

    def list_assignments(self, trainer_id=None):
        rows = [a for a in list(self.assignments.values()) if trainer_id is None or a.trainer_id == trainer_id]
        return [self._with_trainer(a) for a in sorted(rows, key=lambda a: a.assigned_at, reverse=True)]

    def get_assignment(self, id):
        a = self.assignments.get(id)
        return self._with_trainer(a) if a else None

    def save_trainer_answer(self, id, fault_id):
        stamp = self._stamp()
        with self._lock:
            a = self.assignments.get(id)
            if a is None or a.answered_at is not None:
                return None
            self.assignments[id] = replace(a, trainer_fault_id=fault_id, answered_at=stamp)
        return self.get_assignment(id)

    def save_verdict(self, id, verdict):
        stamp = self._stamp()
        with self._lock:
            a = self.assignments.get(id)
            if a is None or a.answered_at is None:
                return None
            self.assignments[id] = replace(a, verdict=verdict, graded_at=stamp)
        return self.get_assignment(id)

    def list_feedback_between(self, start, end):
        created = {a.id: a.created_at for a in list(self.analyses.values())}
        return [f for (aid, _), f in list(self.feedback.items()) if aid in created and start <= created[aid] < end]

    def list_graded_verdicts(self, start, end):
        rows = []
        for g in sorted(list(self.assignments.values()), key=lambda g: g.assigned_at):
            a = self.analyses.get(g.analysis_id)
            if g.verdict is not None and a is not None and start <= a.created_at < end:
                rows.append(g.verdict)
        return rows

    def list_upload_times(self):
        return [(u.user_id, u.created_at) for u in list(self.uploads.values())]

    def list_faults(self):
        return list(self.faults)

    def get_fault(self, lift, fault_id):
        return next((f for f in self.faults if (f.lift, f.id) == (lift, fault_id)), None)

    def create_fault(self, fault):
        with self._lock:
            if any((f.lift, f.id) == (fault.lift, fault.id) for f in self.faults):
                raise FaultExists(f"{fault.lift} already has a fault with ID '{fault.id}'")
            self.faults.append(fault)
        return fault

    def update_fault(self, lift, fault_id, changed_by=None, **fields):
        _check_fault_fields(fields)
        stamp = self._stamp()  # taken first: _stamp() uses the same lock
        with self._lock:
            for i, f in enumerate(self.faults):
                if (f.lift, f.id) == (lift, fault_id):
                    self.faults[i] = edit_fault(f, **fields)
                    if self.faults[i].threshold != f.threshold:
                        self.threshold_changes.append(ThresholdChange(lift, fault_id, f.threshold,
                                                                      self.faults[i].threshold, changed_by, stamp))
                    return self.faults[i]
        raise KeyError(f"no {lift} fault '{fault_id}'")

    def list_threshold_changes(self):
        email = lambda uid: self.users[uid].email if uid in self.users else None
        return [replace(c, changed_by_email=email(c.changed_by))
                for c in sorted(self.threshold_changes, key=lambda c: c.changed_at, reverse=True)]


class PostgresRepository:
    """Talks to Supabase Postgres directly with a server-side connection (bypasses RLS; the API checks ownership)."""

    def __init__(self, dsn: str):
        from psycopg_pool import ConnectionPool

        self.pool = ConnectionPool(dsn, min_size=1, max_size=5, kwargs={"autocommit": True}, open=True)
        self._local = threading.local()

    @contextmanager
    def user_lock(self, user_id):
        # Pin the connection for queries inside the guard. Waiting requests must not
        # exhaust the pool while the lock holder needs a second connection to make progress.
        previous = getattr(self._local, "connection", None)
        with (nullcontext(previous) if previous is not None else self.pool.connection()) as conn:
            conn.execute("select pg_advisory_lock(hashtextextended(%s, 0))", (user_id,))
            self._local.connection = conn
            try:
                yield
            finally:
                self._local.connection = previous
                conn.execute("select pg_advisory_unlock(hashtextextended(%s, 0))", (user_id,))

    def _q(self, sql: str, params=(), one=False, rows=False):
        from psycopg.rows import dict_row

        pinned = getattr(self._local, "connection", None)
        with (nullcontext(pinned) if pinned is not None else self.pool.connection()) as conn, conn.cursor(row_factory=dict_row) as cur:
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
                              error=r["error"], created_at=r["created_at"], completed_at=r["completed_at"],
                              processing_stage=r["processing_stage"])

    def ensure_user(self, id, email, is_admin=False, is_trainer=False):
        r = self._q("insert into public.users (id, email, is_admin, is_trainer) values (%s, %s, %s, %s) "
                    "on conflict (id) do update set email = excluded.email, is_admin = excluded.is_admin, "
                    "is_trainer = excluded.is_trainer returning created_at", (id, email, is_admin, is_trainer), one=True)
        return UserRecord(id, email, is_admin, r["created_at"], is_trainer)

    def get_user(self, id):
        r = self._q("select * from public.users where id::text = %s", (id,), one=True)
        return r and UserRecord(str(r["id"]), r["email"], r["is_admin"], r["created_at"], r["is_trainer"])

    # ------------------------------------------------------------------ trainer grading (US-22)

    def list_trainers(self):
        rows = self._q("select * from public.users where is_trainer order by email", rows=True)
        return [UserRecord(str(r["id"]), r["email"], r["is_admin"], r["created_at"], r["is_trainer"]) for r in rows]

    _ASSIGNMENT_SELECT = ("select g.*, u.email as trainer_email from public.grading_assignments g "
                          "left join public.users u on u.id = g.trainer_id ")

    @staticmethod
    def _assignment(r) -> GradingAssignment | None:
        if r is None:
            return None
        return GradingAssignment(str(r["id"]), str(r["analysis_id"]), str(r["trainer_id"]),
                                 str(r["assigned_by"]) if r["assigned_by"] else None, r["assigned_at"],
                                 r["trainer_fault_id"], r["answered_at"], r["verdict"], r["graded_at"], r["trainer_email"])

    def create_assignments(self, trainer_id, analysis_ids, assigned_by):
        made = []
        for analysis_id in analysis_ids:
            r = self._q("insert into public.grading_assignments (analysis_id, trainer_id, assigned_by) values (%s, %s, %s) "
                        "on conflict (analysis_id, trainer_id) do nothing returning id",
                        (analysis_id, trainer_id, assigned_by), one=True)
            if r:
                made.append(self.get_assignment(str(r["id"])))
        return made

    def list_assignments(self, trainer_id=None):
        rows = self._q(self._ASSIGNMENT_SELECT + "where (%s::text is null or g.trainer_id::text = %s) "
                       "order by g.assigned_at desc, g.id desc", (trainer_id, trainer_id), rows=True)
        return [self._assignment(r) for r in rows]

    def get_assignment(self, id):
        return self._assignment(self._q(self._ASSIGNMENT_SELECT + "where g.id::text = %s", (id,), one=True))

    def save_trainer_answer(self, id, fault_id):
        # Only once: after the answer our feedback is shown, so changing it would no longer be blind.
        r = self._q("update public.grading_assignments set trainer_fault_id = %s, answered_at = now() "
                    "where id::text = %s and answered_at is null returning id", (fault_id, id), one=True)
        return self.get_assignment(id) if r else None

    def save_verdict(self, id, verdict):
        r = self._q("update public.grading_assignments set verdict = %s, graded_at = now() "
                    "where id::text = %s and answered_at is not null returning id", (verdict, id), one=True)
        return self.get_assignment(id) if r else None

    # ------------------------------------------------------------------ hypothesis metrics (US-23)

    def list_feedback_between(self, start, end):
        rows = self._q("select f.* from public.feedback_responses f join public.analyses a on a.id = f.analysis_id "
                       "where a.created_at >= %s and a.created_at < %s", (start, end), rows=True)
        return [FeedbackRecord(str(r["analysis_id"]), str(r["user_id"]), r["rating"], r["tried_cue"], r["updated_at"])
                for r in rows]

    def list_graded_verdicts(self, start, end):
        rows = self._q("select g.verdict from public.grading_assignments g join public.analyses a on a.id = g.analysis_id "
                       "where g.verdict is not null and a.created_at >= %s and a.created_at < %s order by g.assigned_at",
                       (start, end), rows=True)
        return [r["verdict"] for r in rows]

    def list_upload_times(self):
        return [(str(r["user_id"]), r["created_at"])
                for r in self._q("select user_id, created_at from public.uploads", rows=True)]

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

    def list_uploads_for_user(self, user_id):
        rows = self._q("select * from public.uploads where user_id = %s order by created_at", (user_id,), rows=True)
        return [UploadRecord(str(r["id"]), str(r["user_id"]), r["lift"], r["video_path"], r["filename"],
                             r["note"], r["created_at"]) for r in rows]

    def delete_upload(self, upload_id):
        # Existing foreign keys cascade to analyses, measurements, attempts, errors and feedback.
        self._q("delete from public.uploads where id::text = %s", (upload_id,))

    def delete_user(self, user_id):
        self._q("delete from public.users where id::text = %s", (user_id,))

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

    def save_llm_attempt(self, analysis_id, attempt_number, output_text, input_tokens, output_tokens, issues,
                         provider=None, model=None):
        r = self._q("insert into public.llm_attempts (analysis_id, attempt_number, output_text, input_tokens, "
                    "output_tokens, passed, provider, model) values (%s,%s,%s,%s,%s,%s,%s,%s) returning id, created_at",
                    (analysis_id, attempt_number, output_text, input_tokens, output_tokens, not issues, provider, model),
                    one=True)
        for issue in issues:
            self._q("insert into public.validation_results (attempt_id, analysis_id, code, message) values (%s,%s,%s,%s)",
                    (r["id"], analysis_id, issue.code, issue.message))
        return LLMAttemptRecord(str(r["id"]), analysis_id, attempt_number, output_text, input_tokens, output_tokens,
                                list(issues), not issues, r["created_at"], provider, model)

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
                                 r["created_at"], r["provider"], r["model"]) for r in rows]

    def all_validation_issues(self):
        return [ValidationIssue(r["code"], r["message"])
                for r in self._q("select code, message from public.validation_results", rows=True)]

    def list_attempt_usage(self, start, end):
        rows = self._q(
            "select t.analysis_id, a.created_at as analysis_created_at, t.attempt_number, t.input_tokens, "
            "t.output_tokens, t.provider, t.model from public.llm_attempts t "
            "join public.analyses a on a.id = t.analysis_id where a.created_at >= %s and a.created_at < %s "
            "order by a.created_at, t.attempt_number", (start, end), rows=True)
        return [AttemptUsage(str(r["analysis_id"]), r["analysis_created_at"], r["attempt_number"], r["input_tokens"],
                             r["output_tokens"], r["provider"], r["model"]) for r in rows]

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

    # ------------------------------------------------------------------ fault list (US-25)

    _VIEW_ORDER = ("side", "front", "angled")

    @staticmethod
    def _fault(r) -> Fault | None:
        if r is None:
            return None
        return Fault(id=r["id"], lift=r["lift"], name=r["name"], short_name=r["short_name"], category=r["category"],
                     metric=r["metric"], metric_label=r["metric_label"], threshold=r["threshold"],
                     direction=r["direction"], unit=r["unit"], views=frozenset(r["views"]), joints=tuple(r["joints"]),
                     label_format=r["label_format"], enabled=r["enabled"])

    def list_faults(self):
        return [self._fault(r) for r in self._q("select * from public.faults order by position", rows=True)]

    def get_fault(self, lift, fault_id):
        return self._fault(self._q("select * from public.faults where lift = %s and id = %s", (lift, fault_id), one=True))

    def create_fault(self, fault):
        r = self._q(
            "insert into public.faults (lift, id, name, short_name, category, metric, metric_label, threshold, direction, "
            "unit, views, joints, label_format, enabled, position) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
            "(select coalesce(max(position), 0) + 1 from public.faults)) on conflict (lift, id) do nothing returning *",
            (fault.lift, fault.id, fault.name, fault.short_name, fault.category, fault.metric, fault.metric_label,
             fault.threshold, fault.direction, fault.unit, [v for v in self._VIEW_ORDER if v in fault.views],
             list(fault.joints), fault.label_format, fault.enabled), one=True)
        if r is None:
            raise FaultExists(f"{fault.lift} already has a fault with ID '{fault.id}'")
        return self._fault(r)

    def update_fault(self, lift, fault_id, changed_by=None, **fields):
        from psycopg.rows import dict_row

        _check_fault_fields(fields)
        # One transaction, with the row locked, so a threshold change and its log entry are saved together.
        with self.pool.connection() as conn, conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
            cur.execute("select * from public.faults where lift = %s and id = %s for update", (lift, fault_id))
            current = self._fault(cur.fetchone())
            if current is None:
                raise KeyError(f"no {lift} fault '{fault_id}'")
            edited = edit_fault(current, **fields)
            changes = {k: getattr(edited, k) for k in fields}
            sets = ", ".join(f"{k} = %s" for k in changes)
            cur.execute(f"update public.faults set {sets}, updated_at = now() where lift = %s and id = %s returning *",
                        (*changes.values(), lift, fault_id))
            saved = self._fault(cur.fetchone())
            if edited.threshold != current.threshold:
                cur.execute("insert into public.fault_threshold_changes (lift, fault_id, old_threshold, new_threshold, "
                            "changed_by) values (%s, %s, %s, %s, %s)",
                            (lift, fault_id, current.threshold, edited.threshold, changed_by))
        return saved

    def list_threshold_changes(self):
        rows = self._q("select c.*, u.email as changed_by_email from public.fault_threshold_changes c "
                       "left join public.users u on u.id = c.changed_by order by c.changed_at desc, c.id desc", rows=True)
        return [ThresholdChange(r["lift"], r["fault_id"], r["old_threshold"], r["new_threshold"],
                                str(r["changed_by"]) if r["changed_by"] else None, r["changed_at"], r["changed_by_email"])
                for r in rows]

    # ------------------------------------------------------------------ usage and moderation (US-27)

    def list_signup_times(self, start, end):
        rows = self._q("select created_at from public.users where created_at >= %s and created_at < %s",
                       (start, end), rows=True)
        return [r["created_at"] for r in rows]

    def list_upload_rows(self, start, end, lift=None):
        rows = self._q(
            "select u.*, us.email as user_email, a.id as a_id from public.uploads u "
            "left join public.users us on us.id = u.user_id "
            "left join lateral (select id from public.analyses where upload_id = u.id "
            "order by created_at desc limit 1) a on true "
            "where u.created_at >= %s and u.created_at < %s and (%s::text is null or u.lift = %s) "
            "order by u.created_at desc", (start, end, lift, lift), rows=True)
        return [AdminUploadRow(UploadRecord(str(r["id"]), str(r["user_id"]), r["lift"], r["video_path"], r["filename"],
                                            r["note"], r["created_at"]), r["user_email"] or "",
                               self.get_analysis(str(r["a_id"])) if r["a_id"] else None) for r in rows]

    _MODERATION_SELECT = ("select m.*, o.email as owner_email, a.email as removed_by_email from public.moderation_log m "
                          "left join public.users o on o.id = m.owner_id left join public.users a on a.id = m.removed_by ")

    @staticmethod
    def _moderation(r) -> ModerationEntry | None:
        if r is None:
            return None
        text = lambda v: str(v) if v is not None else None
        return ModerationEntry(str(r["id"]), str(r["upload_id"]), [str(a) for a in r["analysis_ids"]], r["lift"],
                               text(r["owner_id"]), text(r["removed_by"]), r["reason"], r["note"], r["removed_at"],
                               r["owner_email"], r["removed_by_email"])

    def create_moderation_entry(self, upload_id, analysis_ids, lift, owner_id, removed_by, reason, note):
        r = self._q("insert into public.moderation_log (upload_id, analysis_ids, lift, owner_id, removed_by, reason, note) "
                    "values (%s, %s::uuid[], %s, %s, %s, %s, %s) returning id",
                    (upload_id, list(analysis_ids), lift, owner_id, removed_by, reason, note), one=True)
        return self._moderation(self._q(self._MODERATION_SELECT + "where m.id = %s", (r["id"],), one=True))

    def delete_moderation_entry(self, entry_id):
        self._q("delete from public.moderation_log where id::text = %s", (entry_id,))

    def list_moderation_entries(self):
        return [self._moderation(r) for r in self._q(self._MODERATION_SELECT + "order by m.removed_at desc", rows=True)]

    def get_removal_for_analysis(self, analysis_id):
        return self._moderation(self._q(self._MODERATION_SELECT + "where %s = any(m.analysis_ids::text[]) "
                                        "order by m.removed_at desc limit 1", (analysis_id,), one=True))
