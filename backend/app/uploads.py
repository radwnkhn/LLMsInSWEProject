"""Upload limits and the background job that analyzes an uploaded video."""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone

from app.measure import RepMeasurement
from app.pipeline import analyze_set
from app.results import build_result_view

log = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 60
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
VIDEO_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime"}
TYPE_MESSAGE = "Please upload an MP4 or MOV video"
DURATION_MESSAGE = "Videos must be 60 seconds or shorter"
SIZE_MESSAGE = "Videos must be 200 MB or smaller"
UNREADABLE_MESSAGE = "We couldn't read that video. Please try another file."
STORAGE_MESSAGE = "We couldn't save your video. Please try again."


def video_extension(filename: str | None) -> str | None:
    ext = os.path.splitext(filename or "")[1].lower()
    return ext if ext in VIDEO_TYPES else None


def process_analysis(services, analysis_id: str) -> None:
    """Runs the full pipeline for one analysis and stores everything it produced."""
    repo, storage = services.repo, services.storage
    analysis = repo.get_analysis(analysis_id)
    upload = repo.get_upload(analysis.upload_id)
    path = None
    try:
        repo.update_analysis(analysis_id, status="processing", processing_stage="measuring")
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(upload.video_path)[1], delete=False) as f:
            f.write(storage.download(upload.video_path))
            path = f.name
        info = services.video.probe(path)
        frames = services.video.poses(path, info, upload.filename)
        outcome = analyze_set(frames, analysis.lift, upload.note, services.llm, fps=info.fps,
                              frame_loader=lambda i: services.video.frame(path, i),
                              on_stage=lambda stage: repo.update_analysis(analysis_id, processing_stage=stage))

        repo.save_rep_measurements(analysis_id, outcome.measurements.reps if outcome.final_status != "unanalyzable" else [])
        if outcome.correction:
            for a in outcome.correction.attempts:
                repo.save_llm_attempt(analysis_id, a.attempt_number, a.output_text, a.input_tokens, a.output_tokens, a.issues)
        frame_path = None
        if outcome.annotated_png:
            frame_path = f"frames/{analysis.user_id}/{analysis_id}.png"
            storage.upload(frame_path, outcome.annotated_png, "image/png")
        result = build_result_view(outcome, upload.note)
        repo.update_analysis(
            analysis_id, status="done", processing_stage=None, final_status=outcome.final_status,
            rep_count=outcome.measurements.rep_count if outcome.final_status != "unanalyzable" else 0,
            camera_angle=result["camera_angle"],
            top_fault_id=(result["top_fix"] or {}).get("fault_id"), result=result,
            unanalyzable_reason=outcome.unanalyzable_reason, frame_path=frame_path,
            completed_at=datetime.now(timezone.utc),
        )
    except Exception as err:  # the job must never leave an analysis stuck in "processing"
        log.exception("analysis %s failed", analysis_id)
        repo.update_analysis(analysis_id, status="failed", processing_stage=None, error=str(err) or err.__class__.__name__,
                             completed_at=datetime.now(timezone.utc))
    finally:
        if path:
            os.unlink(path)


def rep_measurements_view(reps: list[RepMeasurement]) -> list[dict]:
    return [r.to_view() for r in reps]
