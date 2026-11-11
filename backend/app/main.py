"""HTTP API."""
from __future__ import annotations

import copy
import hmac
import logging
import mimetypes
import os
import re
import tempfile
import uuid
from typing import Literal

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, StrictBool, StrictFloat, StrictInt, field_validator, model_validator

from app.admin import admin_row_view, filter_admin_rows, summarize_validation_errors
from app.auth import AuthUser, EmailTaken, InvalidCredentials
from app.compress import STORED_CONTENT_TYPE, STORED_EXTENSION
from app.comparison import COMPARABLE_STATUSES, compare_earlier_fault, measurement_comparison
from app.faults import METRICS, FaultCatalog, FaultError, FaultExists, new_fault
from app.feedback import find_previous_cue_prompt
from app.history import history_item
from app.lifts import LIFT_LABELS, LIFTS
from app.repository import AdminAnalysisRow
from app.safety import MAX_NOTE_LENGTH
from app.services import Services
from app.uploads import (DURATION_MESSAGE, MAX_DURATION_SECONDS, SIZE_MESSAGE, STORAGE_MESSAGE, TYPE_MESSAGE,
                         UNREADABLE_MESSAGE, VIDEO_TYPES, process_analysis, rep_measurements_view, video_extension)
from app.video import VideoUnreadable

log = logging.getLogger(__name__)

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FINAL_STATUSES = ("passed_first_try", "passed_after_retry", "fallback", "unanalyzable")
EMPTY_RESULT = {
    "final_status": None, "camera_angle": None, "rep_count": None, "unanalyzable_reason": None, "top_fix": None,
    "cue": None, "explanation": None, "no_major_issues": False, "other_faults": [], "not_measured": [],
    "rep_breakdown": None, "measurements": [], "annotated_frame": None, "professional_message": None,
    "fallback_note": None,
}
CHUNK = 1024 * 1024


class SignupBody(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL.match(v):
            raise ValueError("enter a valid email address")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class LoginBody(BaseModel):
    email: str
    password: str


class DeleteBody(BaseModel):
    confirmed: StrictBool

    @field_validator("confirmed")
    @classmethod
    def _confirmed(cls, value):
        if not value:
            raise ValueError("Confirm deletion before continuing")
        return value


class FeedbackBody(BaseModel):
    rating: StrictInt | None = None
    tried_cue: Literal["yes", "no", "not_yet"] | None = None

    @model_validator(mode="before")
    @classmethod
    def _present(cls, data):
        if isinstance(data, dict) and "rating" in data and data["rating"] is None:
            raise ValueError("rating must be a number from 1 to 5")
        return data

    @field_validator("rating")
    @classmethod
    def _range(cls, v):
        if v is not None and not 1 <= v <= 5:
            raise ValueError("rating must be from 1 to 5")
        return v

    @model_validator(mode="after")
    def _something(self):
        if self.rating is None and self.tried_cue is None:
            raise ValueError("send a rating, an answer about the cue, or both")
        return self


def _session_body(session) -> dict:
    u = session.user
    return {"access_token": session.access_token, "user": {"id": u.id, "email": u.email, "is_admin": u.is_admin}}


class FaultEditBody(BaseModel):
    """US-25 edits. Only these fields; thresholds are changed by US-24."""
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    short_name: str | None = None
    enabled: StrictBool | None = None

    @model_validator(mode="after")
    def _something(self):
        if not self.model_fields_set:
            raise ValueError("Send a name, short_name or enabled")
        return self


class NewFaultBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lift: str
    id: str
    name: str
    short_name: str
    category: str
    metric: str
    threshold: StrictInt | StrictFloat
    direction: str


def fault_view(fault) -> dict:
    return {"lift": fault.lift, "id": fault.id, "name": fault.name, "short_name": fault.short_name,
            "category": fault.category, "safety": fault.safety, "metric": fault.metric, "metric_label": fault.metric_label,
            "threshold": fault.threshold, "direction": fault.direction, "unit": fault.unit, "enabled": fault.enabled}


def create_app(services: Services) -> FastAPI:
    app = FastAPI(title="Alibi API")
    app.state.services = services
    if services.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(services.cors_origins), allow_methods=["*"],
                           allow_headers=["*"])
    bearer = HTTPBearer(auto_error=False)

    def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> AuthUser:
        user = services.auth.get_user(creds.credentials) if creds else None
        if user is None:
            raise HTTPException(401, "Please log in")
        with services.repo.user_lock(user.id):
            # A request may have authenticated just before account deletion acquired its lock.
            if services.repo.get_user(user.id) is None and services.auth.get_user(creds.credentials) is None:
                raise HTTPException(401, "Please log in")
            services.repo.ensure_user(user.id, user.email, user.is_admin)
        return user

    def admin_user(user: AuthUser = Depends(current_user)) -> AuthUser:
        if not user.is_admin:
            raise HTTPException(403, "Admins only")
        return user

    def absolute(request: Request, url: str) -> str:
        return str(request.base_url).rstrip("/") + url if url.startswith("/") else url

    def own_analysis(analysis_id: str, user: AuthUser):
        a = services.repo.get_analysis(analysis_id)
        if a is None or a.user_id != user.id:
            raise HTTPException(404, "Analysis not found")
        return a

    def analysis_view(request: Request, a, user_id: str) -> dict:
        upload = services.repo.get_upload(a.upload_id)
        view = {**EMPTY_RESULT, **copy.deepcopy(a.result or {})}
        view.update(analysis_id=a.id, created_at=a.created_at.isoformat() if a.created_at else None, status=a.status,
                    final_status=a.final_status, processing_stage=a.processing_stage,
                    lift=a.lift, lift_label=LIFT_LABELS[a.lift],
                    error="Analysis failed" if a.status == "failed" else None)
        view["video_url"] = absolute(request, services.storage.signed_url(upload.video_path))
        if view["annotated_frame"] and a.frame_path:
            view["annotated_frame"]["image_url"] = absolute(request, services.storage.signed_url(a.frame_path))
        view["previous_cue_prompt"] = (find_previous_cue_prompt(services.repo, user_id, a.lift, a.id)
                                       if a.status == "done" else None)
        fb = services.repo.get_feedback(a.id, user_id)
        view["feedback"] = {"rating": fb.rating, "tried_cue": fb.tried_cue} if fb else None
        return view

    # ------------------------------------------------------------------ health and auth

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/auth/signup", status_code=201)
    def signup(body: SignupBody):
        try:
            session = services.auth.sign_up(body.email, body.password)
        except EmailTaken:
            raise HTTPException(409, "An account with this email already exists")
        services.repo.ensure_user(session.user.id, session.user.email, session.user.is_admin)
        return _session_body(session)

    @app.post("/auth/login")
    def login(body: LoginBody):
        try:
            session = services.auth.sign_in(body.email.strip().lower(), body.password)
        except InvalidCredentials:
            raise HTTPException(401, "Incorrect email or password")
        return _session_body(session)

    @app.post("/auth/logout", status_code=204)
    def logout(creds: HTTPAuthorizationCredentials | None = Depends(bearer), user: AuthUser = Depends(current_user)):
        services.auth.sign_out(creds.credentials)
        return Response(status_code=204)

    @app.get("/auth/me")
    def me(user: AuthUser = Depends(current_user)):
        return {"id": user.id, "email": user.email, "is_admin": user.is_admin}

    # ------------------------------------------------------------------ uploads and results

    @app.post("/uploads", status_code=201)
    def create_upload(background: BackgroundTasks, user: AuthUser = Depends(current_user),
                      file: UploadFile = File(...), lift: str = Form(...), note: str | None = Form(None)):
        with services.repo.user_lock(user.id):
            if services.repo.get_user(user.id) is None:
                raise HTTPException(401, "Please log in")
            return store_upload(background, user, file, lift, note)

    def store_upload(background, user, file, lift, note):
        if lift not in LIFTS:
            raise HTTPException(422, "Choose squat, deadlift or bench_press")
        if note is not None and len(note) > MAX_NOTE_LENGTH:
            raise HTTPException(422, f"Notes can be at most {MAX_NOTE_LENGTH} characters")
        ext = video_extension(file.filename)
        if ext is None:
            raise HTTPException(415, TYPE_MESSAGE)

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            size = 0
            while chunk := file.file.read(CHUNK):
                size += len(chunk)
                if size > services.max_upload_bytes:
                    break
                tmp.write(chunk)
        compressed = tmp.name + ".stored.mp4"
        try:
            if size > services.max_upload_bytes:
                raise HTTPException(413, SIZE_MESSAGE)
            try:
                info = services.video.probe(tmp.name)
            except VideoUnreadable:
                raise HTTPException(422, UNREADABLE_MESSAGE)
            if info.duration > MAX_DURATION_SECONDS:
                raise HTTPException(422, DURATION_MESSAGE)
            stored, stored_ext, content_type = tmp.name, ext, VIDEO_TYPES[ext]
            if services.compressor is not None:
                stored, stored_ext, content_type = compressed, STORED_EXTENSION, STORED_CONTENT_TYPE
                try:
                    services.compressor.compress(tmp.name, compressed)
                except VideoUnreadable:
                    log.exception("compressing upload failed")
                    raise HTTPException(422, UNREADABLE_MESSAGE)
            upload_id, analysis_id = str(uuid.uuid4()), str(uuid.uuid4())
            path = f"{user.id}/{upload_id}{stored_ext}"
            try:
                with open(stored, "rb") as f:
                    services.storage.upload(path, f, content_type)
            except httpx.HTTPError:
                log.exception("storing upload failed")
                raise HTTPException(502, STORAGE_MESSAGE)
        finally:
            for leftover in (tmp.name, compressed):
                if os.path.exists(leftover):
                    os.unlink(leftover)

        services.repo.create_upload(upload_id, user.id, lift, path, file.filename, note or None)
        services.repo.create_analysis(analysis_id, upload_id, user.id, lift)
        background.add_task(process_analysis, services, analysis_id)
        return {"upload_id": upload_id, "analysis_id": analysis_id, "status": "queued"}

    @app.get("/analyses/{analysis_id}")
    def get_analysis(analysis_id: str, request: Request, user: AuthUser = Depends(current_user)):
        return analysis_view(request, own_analysis(analysis_id, user), user.id)

    @app.post("/analyses/{analysis_id}/retry", status_code=202)
    def retry_analysis(analysis_id: str, background: BackgroundTasks, user: AuthUser = Depends(current_user)):
        with services.repo.user_lock(user.id):
            if services.repo.get_user(user.id) is None:
                raise HTTPException(401, "Please log in")
            original = own_analysis(analysis_id, user)
            if original.status != "failed":
                raise HTTPException(409, "Only failed analyses can be retried")
            # A fresh analysis preserves the failed attempt and avoids duplicate measurements/logs.
            new_id = str(uuid.uuid4())
            services.repo.create_analysis(new_id, original.upload_id, user.id, original.lift)
            background.add_task(process_analysis, services, new_id)
            return {"analysis_id": new_id, "status": "queued"}

    # ------------------------------------------------------------------ deletion

    def finished_before_deletion(analyses):
        if any(a.status in ("queued", "processing") for a in analyses):
            raise HTTPException(409, "Wait for analyses to finish before deleting. Then try again.")

    @app.delete("/uploads/{upload_id}", status_code=204)
    def delete_upload(upload_id: str, body: DeleteBody, user: AuthUser = Depends(current_user)):
        with services.repo.user_lock(user.id):
            upload = services.repo.get_upload(upload_id)
            if upload is None or upload.user_id != user.id:
                raise HTTPException(404, "Upload not found")
            analyses = [a for a in services.repo.list_analyses_for_user(user.id) if a.upload_id == upload_id]
            finished_before_deletion(analyses)
            paths = {upload.video_path}
            for a in analyses:
                paths.add(f"frames/{user.id}/{a.id}.png")  # includes frames from a partially failed attempt
                if a.frame_path:
                    paths.add(a.frame_path)
            try:
                services.storage.delete(sorted(paths))
                services.repo.delete_upload(upload_id)
            except Exception:
                log.exception("deleting upload %s failed", upload_id)
                raise HTTPException(502, "Couldn't delete the video completely. Please try again.")
        return Response(status_code=204)

    @app.delete("/account", status_code=204)
    def delete_account(body: DeleteBody, user: AuthUser = Depends(current_user)):
        with services.repo.user_lock(user.id):
            finished_before_deletion(services.repo.list_analyses_for_user(user.id))
            try:
                paths = services.storage.list_paths(f"{user.id}/") + services.storage.list_paths(f"frames/{user.id}/")
                services.storage.delete(paths)
                services.repo.delete_user(user.id)
                services.auth.delete_user(user.id)
            except Exception:
                log.exception("deleting account %s failed", user.id)
                raise HTTPException(502, "Couldn't delete your account completely. Please try again.")
        return Response(status_code=204)

    @app.post("/analyses/{analysis_id}/feedback")
    def post_feedback(analysis_id: str, body: FeedbackBody, user: AuthUser = Depends(current_user)):
        own_analysis(analysis_id, user)
        fb = services.repo.upsert_feedback(analysis_id, user.id, body.rating, body.tried_cue)
        return {"rating": fb.rating, "tried_cue": fb.tried_cue}

    @app.get("/history")
    def history(lift: str | None = Query(None), user: AuthUser = Depends(current_user)):
        if lift is not None and lift not in LIFTS:
            raise HTTPException(422, "Unknown lift")
        return {"items": [history_item(a) for a in services.repo.list_analyses_for_user(user.id, lift=lift)]}

    @app.get("/comparisons")
    def get_comparison(request: Request, first_id: str, second_id: str, user: AuthUser = Depends(current_user)):
        # Check both owners before validating the pair or creating private storage URLs.
        first, second = own_analysis(first_id, user), own_analysis(second_id, user)
        if first.upload_id == second.upload_id:
            raise HTTPException(422, "Choose two different uploads")
        actual_first = (first.result or {}).get("lift", first.lift)
        actual_second = (second.result or {}).get("lift", second.lift)
        if first.lift != second.lift or actual_first != actual_second or actual_first != first.lift:
            raise HTTPException(422, "Choose two uploads of the same lift, with matching analyzed movements")
        if any(a.status != "done" or a.final_status not in COMPARABLE_STATUSES for a in (first, second)):
            raise HTTPException(409, "Choose two completed uploads with measurable reps")
        ordered = sorted((first, second), key=lambda a: services.repo.get_upload(a.upload_id).created_at)
        older, newer = ordered
        catalog = FaultCatalog(services.repo.list_faults())
        old_reps = services.repo.list_rep_measurements(older.id)
        new_reps = services.repo.list_rep_measurements(newer.id)
        return {"older": analysis_view(request, older, user.id), "newer": analysis_view(request, newer, user.id),
                "metrics": measurement_comparison(older, newer, old_reps, new_reps, catalog),
                "fault_comparison": compare_earlier_fault(older, newer, new_reps, catalog)}

    # ------------------------------------------------------------------ admin

    @app.get("/admin/analyses")
    def admin_list(lift: str | None = None, final_status: str | None = None, user: AuthUser = Depends(admin_user)):
        if lift is not None and lift not in LIFTS:
            raise HTTPException(422, "Unknown lift")
        if final_status is not None and final_status not in FINAL_STATUSES:
            raise HTTPException(422, "Unknown final status")
        rows = filter_admin_rows(services.repo.list_admin_rows(), lift=lift, final_status=final_status)
        return {"items": [admin_row_view(r) for r in rows]}

    @app.get("/admin/analyses/{analysis_id}")
    def admin_detail(analysis_id: str, request: Request, user: AuthUser = Depends(admin_user)):
        a = services.repo.get_analysis(analysis_id)
        if a is None:
            raise HTTPException(404, "Analysis not found")
        attempts = services.repo.list_llm_attempts(a.id)
        owner = services.repo.get_user(a.user_id)
        upload = services.repo.get_upload(a.upload_id)
        return {
            "analysis": admin_row_view(AdminAnalysisRow(a, len(attempts), owner.email if owner else "")),
            "video_url": absolute(request, services.storage.signed_url(upload.video_path)),
            "measurements": rep_measurements_view(services.repo.list_rep_measurements(a.id)),
            "attempts": [{"attempt_number": t.attempt_number, "output_text": t.output_text,
                          "input_tokens": t.input_tokens, "output_tokens": t.output_tokens, "passed": t.passed,
                          "errors": [i.to_dict() for i in t.issues]} for t in attempts],
            "result": a.result,
        }

    @app.get("/admin/validator-errors")
    def admin_errors(user: AuthUser = Depends(admin_user)):
        return {"counts": summarize_validation_errors(services.repo.all_validation_issues())}

    # ------------------------------------------------------------------ admin: fault list (US-25)

    @app.get("/admin/faults")
    def admin_faults(user: AuthUser = Depends(admin_user)):
        catalog = FaultCatalog(services.repo.list_faults())
        return {"lifts": [{"lift": lift, "lift_label": LIFT_LABELS[lift],
                           "faults": [fault_view(f) for f in catalog.all_for(lift)],
                           "metrics": [{"metric": m.metric, "label": m.label, "unit": m.unit} for m in METRICS[lift].values()]}
                          for lift in LIFTS]}

    @app.patch("/admin/faults/{lift}/{fault_id}")
    def admin_edit_fault(lift: str, fault_id: str, body: FaultEditBody, user: AuthUser = Depends(admin_user)):
        if services.repo.get_fault(lift, fault_id) is None:
            raise HTTPException(404, "Fault not found")
        try:
            return fault_view(services.repo.update_fault(lift, fault_id, **body.model_dump(exclude_unset=True)))
        except FaultError as err:
            raise HTTPException(422, str(err))

    @app.post("/admin/faults", status_code=201)
    def admin_add_fault(body: NewFaultBody, user: AuthUser = Depends(admin_user)):
        try:
            fault = new_fault(**body.model_dump())
            return fault_view(services.repo.create_fault(fault))
        except FaultExists as err:
            raise HTTPException(409, str(err))
        except FaultError as err:
            raise HTTPException(422, str(err))

    # ------------------------------------------------------------------ test mode only

    if services.test_mode:
        @app.get("/test-storage/{path:path}")
        def test_storage(path: str, request: Request, token: str = ""):
            storage = services.storage
            if not hmac.compare_digest(token, storage.token_for(path)) or path not in storage.objects:
                raise HTTPException(403, "Invalid or missing token")
            data = storage.objects[path]
            media = storage.content_types.get(path) or mimetypes.guess_type(path)[0] or "application/octet-stream"
            m = re.match(r"bytes=(\d*)-(\d*)", request.headers.get("range", ""))
            if not m:
                return Response(data, media_type=media, headers={"Accept-Ranges": "bytes"})
            start = int(m.group(1) or 0)
            end = min(int(m.group(2)) if m.group(2) else len(data) - 1, len(data) - 1)
            return Response(data[start:end + 1], status_code=206, media_type=media, headers={
                "Accept-Ranges": "bytes", "Content-Range": f"bytes {start}-{end}/{len(data)}"})

    return app

