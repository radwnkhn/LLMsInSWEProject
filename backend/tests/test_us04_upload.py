"""US-04: Upload a set video from my phone.

File-type, size, duration and progress checks in the browser are frontend unit tests
(frontend/src/lib/__tests__/us04-*.test.ts); the server repeats them so they can't be bypassed.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import build_test_services
from app.testing.fakes import FakeVideoBackend
from app.uploads import MAX_DURATION_SECONDS, MAX_UPLOAD_BYTES
from tests.helpers import signup, upload, upload_ok

TYPE_MESSAGE = "Please upload an MP4 or MOV video"


def test_us04_limits_are_60_seconds_and_200_mb():
    assert MAX_DURATION_SECONDS == 60
    assert MAX_UPLOAD_BYTES == 200 * 1024 * 1024


# ---- [integration] a successful upload stores the video privately and creates an analysis job ----

def test_us04_upload_stores_video_and_creates_analysis_job(client, services):
    headers, user_id = signup(client)
    r = upload(client, headers, content=b"video-bytes")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "queued"
    upload_row = services.repo.get_upload(body["upload_id"])
    assert upload_row.video_path == f"{user_id}/{body['upload_id']}.mp4"
    assert services.storage.objects[upload_row.video_path] == b"video-bytes"
    # The job runs after the response; by the time the test client returns it has finished.
    assert services.repo.get_analysis(body["analysis_id"]).status == "done"


def test_us04_stored_video_is_not_publicly_reachable(client, services):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    path = services.repo.get_upload(services.repo.get_analysis(analysis_id).upload_id).video_path
    anonymous = client.get(f"/test-storage/{path}")
    assert anonymous.status_code in (401, 403, 404)


@pytest.mark.parametrize("filename,content_type", [
    ("set.mp4", "video/mp4"),
    ("set.MP4", "video/mp4"),
    ("IMG_0042.MOV", "video/quicktime"),
    ("clip.mov", "application/octet-stream"),
])
def test_us04_mp4_and_mov_accepted(client, filename, content_type):
    headers, _ = signup(client)
    assert upload(client, headers, filename=filename, content_type=content_type).status_code == 201


@pytest.mark.parametrize("filename,content_type", [
    ("set.avi", "video/x-msvideo"),
    ("set.webm", "video/webm"),
    ("photo.jpg", "image/jpeg"),
    ("notes.txt", "text/plain"),
    ("set.mp4.exe", "application/octet-stream"),
    ("noextension", "application/octet-stream"),
])
def test_us04_other_file_types_rejected(client, services, filename, content_type):
    headers, _ = signup(client)
    r = upload(client, headers, filename=filename, content_type=content_type)
    assert r.status_code == 415
    assert r.json()["detail"] == TYPE_MESSAGE
    assert services.storage.objects == {}


def _client_with(**backend):
    services = build_test_services(video=FakeVideoBackend(**backend))
    return TestClient(create_app(services)), services


def test_us04_video_longer_than_60_seconds_rejected():
    client, services = _client_with(duration=60.5)
    headers, _ = signup(client)
    r = upload(client, headers)
    assert r.status_code == 422
    assert r.json()["detail"] == "Videos must be 60 seconds or shorter"
    assert services.storage.objects == {}


def test_us04_video_of_exactly_60_seconds_accepted():
    client, _ = _client_with(duration=60.0)
    headers, _ = signup(client)
    assert upload(client, headers).status_code == 201


def test_us04_file_larger_than_limit_rejected():
    services = build_test_services(max_upload_bytes=1000)
    client = TestClient(create_app(services))
    headers, _ = signup(client)
    r = upload(client, headers, content=b"x" * 1001)
    assert r.status_code == 413
    assert r.json()["detail"] == "Videos must be 200 MB or smaller"
    assert upload(client, headers, content=b"x" * 1000).status_code == 201


def test_us04_unreadable_video_rejected():
    client, services = _client_with(unreadable=True)
    headers, _ = signup(client)
    r = upload(client, headers)
    assert r.status_code == 422
    assert r.json()["detail"] == "We couldn't read that video. Please try another file."
    assert services.storage.objects == {}


def test_us04_processing_error_marks_analysis_failed_instead_of_crashing():
    client, services = _client_with(fail_on_poses=True)
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    assert services.repo.get_analysis(analysis_id).status == "failed"
    assert client.get(f"/analyses/{analysis_id}", headers=headers).json()["status"] == "failed"
