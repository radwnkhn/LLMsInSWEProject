"""US-19: observable processing steps, terminal outcomes, and retrying saved videos."""
import uuid
from dataclasses import replace
from threading import Event, Thread

import pytest

from app.uploads import process_analysis
from tests.helpers import signup, upload_ok


def queued_analysis(services, user_id, filename="set.mp4"):
    upload_id, analysis_id = str(uuid.uuid4()), str(uuid.uuid4())
    path = f"{user_id}/{upload_id}.mp4"
    services.storage.upload(path, b"video", "video/mp4")
    services.repo.create_upload(upload_id, user_id, "squat", path, filename, None)
    services.repo.create_analysis(analysis_id, upload_id, user_id, "squat")
    return analysis_id


@pytest.mark.parametrize("stage", ["measuring", "writing_feedback", "checking"])
def test_us19_owner_can_poll_the_persisted_processing_stage(client, services, stage):
    headers, uid = signup(client)
    aid = queued_analysis(services, uid)
    services.repo.update_analysis(aid, status="processing", processing_stage=stage)
    response = client.get(f"/analyses/{aid}", headers=headers)
    assert response.status_code == 200
    assert response.json()["processing_stage"] == stage
    assert response.json()["status"] == "processing"


def test_us19_queued_analysis_has_no_started_stage(client, services):
    headers, uid = signup(client)
    aid = queued_analysis(services, uid)
    data = client.get(f"/analyses/{aid}", headers=headers).json()
    assert "processing_stage" in data and data["processing_stage"] is None


def test_us19_pipeline_reports_real_steps_before_the_corresponding_work(client, services, monkeypatch):
    _, uid = signup(client)
    aid = queued_analysis(services, uid)
    observed = []
    poses, complete = services.video.poses, services.llm.complete
    from app import correction
    validate = correction.validate

    def observe(label, function):
        def call(*args, **kwargs):
            observed.append((label, getattr(services.repo.get_analysis(aid), "processing_stage", None)))
            return function(*args, **kwargs)
        return call

    monkeypatch.setattr(services.video, "poses", observe("poses", poses))
    monkeypatch.setattr(services.llm, "complete", observe("llm", complete))
    monkeypatch.setattr(correction, "validate", observe("validator", validate))
    process_analysis(services, aid)
    assert observed == [("poses", "measuring"), ("llm", "writing_feedback"), ("validator", "checking")]
    saved = services.repo.get_analysis(aid)
    assert saved.status == "done" and saved.processing_stage is None


def test_us19_each_correction_attempt_reports_writing_then_checking(client, services, monkeypatch):
    _, uid = signup(client)
    aid = queued_analysis(services, uid)
    observed = []
    complete = services.llm.complete

    def reply(request):
        observed.append(getattr(services.repo.get_analysis(aid), "processing_stage", None))
        result = complete(request)
        if len(observed) == 1:
            result = replace(result, text="invalid JSON")
        return result

    monkeypatch.setattr(services.llm, "complete", reply)
    process_analysis(services, aid)
    assert observed == ["writing_feedback", "writing_feedback"]
    assert services.repo.get_analysis(aid).final_status == "passed_after_retry"


def test_us19_client_can_poll_each_step_while_the_worker_is_running(client, services, monkeypatch):
    headers, uid = signup(client)
    aid = queued_analysis(services, uid)
    from app import correction

    reached = {stage: Event() for stage in ("measuring", "writing_feedback", "checking")}
    proceed = {stage: Event() for stage in reached}

    def gate(stage, function):
        def call(*args, **kwargs):
            reached[stage].set()
            if not proceed[stage].wait(10):
                raise TimeoutError(f"Test did not release {stage}")
            return function(*args, **kwargs)
        return call

    monkeypatch.setattr(services.video, "poses", gate("measuring", services.video.poses))
    monkeypatch.setattr(services.llm, "complete", gate("writing_feedback", services.llm.complete))
    monkeypatch.setattr(correction, "validate", gate("checking", correction.validate))
    worker = Thread(target=process_analysis, args=(services, aid), daemon=True)
    worker.start()
    try:
        for stage in reached:
            assert reached[stage].wait(5), f"Worker never reached {stage}"
            data = client.get(f"/analyses/{aid}", headers=headers).json()
            assert data["status"] == "processing" and data["processing_stage"] == stage
            proceed[stage].set()
    finally:
        for event in proceed.values():
            event.set()
        worker.join(5)
    assert not worker.is_alive()
    assert client.get(f"/analyses/{aid}", headers=headers).json()["status"] == "done"


@pytest.mark.parametrize("filename, final_status", [("no_person.mp4", "unanalyzable"), ("set.mp4", "passed_first_try")])
def test_us19_completion_exposes_results_and_clears_the_stage(client, services, filename, final_status):
    headers, _ = signup(client)
    aid = upload_ok(client, headers, filename=filename)
    data = client.get(f"/analyses/{aid}", headers=headers).json()
    assert data["status"] == "done" and data["final_status"] == final_status
    assert "processing_stage" in data and data["processing_stage"] is None


def test_us19_processing_failure_is_terminal_and_does_not_expose_internal_errors(client, services, monkeypatch):
    headers, uid = signup(client)
    aid = queued_analysis(services, uid)

    def fail(*args):
        raise RuntimeError("private storage credentials")

    monkeypatch.setattr(services.video, "poses", fail)
    process_analysis(services, aid)
    data = client.get(f"/analyses/{aid}", headers=headers).json()
    assert data["status"] == "failed"
    assert "processing_stage" in data and data["processing_stage"] is None
    assert data["error"] == "Analysis failed"
    assert "private storage credentials" not in str(data)


def test_us19_retry_uses_the_saved_video_and_preserves_the_failed_attempt(client, services):
    headers, uid = signup(client)
    aid = queued_analysis(services, uid)
    services.repo.update_analysis(aid, status="failed", error="temporary failure")
    response = client.post(f"/analyses/{aid}/retry", headers=headers)
    assert response.status_code == 202
    new_id = response.json()["analysis_id"]
    assert new_id != aid and response.json()["status"] == "queued"
    original, retried = services.repo.get_analysis(aid), services.repo.get_analysis(new_id)
    assert original.status == "failed" and original.error == "temporary failure"
    assert retried.upload_id == original.upload_id and retried.user_id == uid
    assert retried.status == "done" and retried.final_status == "passed_first_try"
    assert len(services.repo.uploads) == 1


@pytest.mark.parametrize("status", ["queued", "processing", "done"])
def test_us19_only_failed_analyses_can_be_retried(client, services, status):
    headers, uid = signup(client)
    aid = queued_analysis(services, uid)
    services.repo.update_analysis(aid, status=status)
    assert client.post(f"/analyses/{aid}/retry", headers=headers).status_code == 409
    assert len(services.repo.analyses) == 1


def test_us19_status_and_retry_require_ownership(client, services):
    owner, uid = signup(client)
    aid = queued_analysis(services, uid)
    services.repo.update_analysis(aid, status="failed")
    other, _ = signup(client, "other@virginia.edu")
    for method, path in [(client.get, f"/analyses/{aid}"), (client.post, f"/analyses/{aid}/retry")]:
        assert method(path).status_code == 401
        assert method(path, headers=other).status_code == 404
        assert method(path.replace(aid, "missing"), headers=owner).status_code == 404

