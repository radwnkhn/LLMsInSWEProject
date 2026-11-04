"""US-04: phone videos up to 200 MB are accepted even though Supabase's free plan stores at most 50 MB per file.

The server re-encodes each upload (H.264 MP4, longer side at most 1280 px) before storing it. Pose estimation
already runs on frames downscaled to 640 px, so the smaller copy loses nothing the analysis uses.
"""
import cv2
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.compress import MAX_LONG_SIDE, FfmpegCompressor
from app.config import load_settings
from app.main import create_app
from app.services import build_services, build_test_services
from app.storage import InMemoryStorage
from app.video import VideoUnreadable
from tests.helpers import signup, upload

STORAGE_MESSAGE = "We couldn't save your video. Please try again."


class FakeCompressor:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def compress(self, src, dst):
        self.calls.append(src)
        if self.fail:
            raise VideoUnreadable("bad video")
        with open(dst, "wb") as f:
            f.write(b"compressed")


class BrokenStorage(InMemoryStorage):
    def upload(self, path, data, content_type):
        request = httpx.Request("POST", f"https://example.supabase.co/storage/v1/object/videos/{path}")
        raise httpx.HTTPStatusError("400 Bad Request", request=request,
                                    response=httpx.Response(400, request=request, json={"statusCode": "413"}))


def _client(**overrides):
    services = build_test_services(**overrides)
    return TestClient(create_app(services)), services


def _clip(path, width, height, frames=45, fps=30):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    rng = np.random.default_rng(0)
    for i in range(frames):
        img = rng.integers(0, 255, (height, width, 3), dtype=np.uint8)  # noise: hard to compress, like real video
        cv2.rectangle(img, (i * 10, 50), (i * 10 + 200, 400), (0, 255, 0), -1)
        writer.write(img)
    writer.release()
    return path


def _info(path):
    cap = cv2.VideoCapture(str(path))
    info = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS))
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode(errors="replace")
    cap.release()
    return info, fourcc


# ---- [integration] the upload route stores the compressed copy ----

def test_us04_upload_stores_the_compressed_video_as_mp4():
    compressor = FakeCompressor()
    client, services = _client(compressor=compressor)
    headers, user_id = signup(client)
    r = upload(client, headers, filename="IMG_0042.MOV", content_type="video/quicktime", content=b"original")
    assert r.status_code == 201, r.text
    row = services.repo.get_upload(r.json()["upload_id"])
    assert row.video_path == f"{user_id}/{r.json()['upload_id']}.mp4"
    assert row.filename == "IMG_0042.MOV"
    assert services.storage.objects[row.video_path] == b"compressed"
    assert services.storage.content_types[row.video_path] == "video/mp4"
    assert len(compressor.calls) == 1


def test_us04_video_that_cannot_be_compressed_is_rejected_as_unreadable():
    client, services = _client(compressor=FakeCompressor(fail=True))
    headers, user_id = signup(client)
    r = upload(client, headers)
    assert r.status_code == 422
    assert r.json()["detail"] == "We couldn't read that video. Please try another file."
    assert services.storage.objects == {}
    assert services.repo.list_analyses_for_user(user_id) == []


def test_us04_storage_failure_returns_a_clear_error_not_a_crash():
    client, services = _client(storage=BrokenStorage())
    headers, user_id = signup(client)
    r = upload(client, headers)
    assert r.status_code == 502
    assert r.json()["detail"] == STORAGE_MESSAGE
    assert services.repo.list_analyses_for_user(user_id) == []


def test_us04_production_services_compress_uploads(monkeypatch):
    monkeypatch.setattr("app.services.PostgresRepository", lambda dsn: None)  # don't open a real pool
    env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_ANON_KEY": "a", "SUPABASE_SERVICE_ROLE_KEY": "s",
           "DATABASE_URL": "postgresql://u:p@localhost:1/db", "LLM_PROVIDER": "claude", "LLM_API_KEY": "k"}
    services = build_services(load_settings(env))
    assert isinstance(services.compressor, FfmpegCompressor)


# ---- [unit] the real ffmpeg compressor ----

@pytest.mark.parametrize("size,expected", [((1920, 1080), (1280, 720)), ((1080, 1920), (720, 1280))])
def test_us04_ffmpeg_shrinks_to_1280_px_and_keeps_orientation(tmp_path, size, expected):
    src = _clip(tmp_path / "in.mp4", *size)
    dst = tmp_path / "out.mp4"
    FfmpegCompressor().compress(str(src), str(dst))
    (w, h, frames, fps), fourcc = _info(dst)
    assert (w, h) == expected
    assert max(w, h) == MAX_LONG_SIDE
    assert fourcc.lower() in ("avc1", "h264")


def test_us04_ffmpeg_keeps_every_frame_and_the_frame_rate(tmp_path):
    src = _clip(tmp_path / "in.mp4", 1280, 720, frames=45, fps=30)
    dst = tmp_path / "out.mp4"
    FfmpegCompressor().compress(str(src), str(dst))
    (_, _, frames, fps), _ = _info(dst)
    assert frames == 45
    assert fps == pytest.approx(30, abs=0.01)


def test_us04_ffmpeg_does_not_upscale_small_videos(tmp_path):
    src = _clip(tmp_path / "in.mp4", 640, 360)
    dst = tmp_path / "out.mp4"
    FfmpegCompressor().compress(str(src), str(dst))
    assert _info(dst)[0][:2] == (640, 360)


def test_us04_ffmpeg_output_is_smaller_than_a_large_input(tmp_path):
    src = _clip(tmp_path / "in.mp4", 1920, 1080)
    dst = tmp_path / "out.mp4"
    FfmpegCompressor().compress(str(src), str(dst))
    assert dst.stat().st_size < src.stat().st_size


def test_us04_ffmpeg_caps_the_bitrate_so_60_seconds_fits_under_50_mb():
    # 60 s at the capped bitrate (plus container overhead) must stay under Supabase's 50 MB free-plan limit.
    assert FfmpegCompressor.MAX_BITRATE_KBPS * 1000 / 8 * 60 < 45 * 1024 * 1024


def test_us04_ffmpeg_raises_unreadable_for_a_file_that_is_not_a_video(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"definitely not a video")
    with pytest.raises(VideoUnreadable):
        FfmpegCompressor().compress(str(src), str(tmp_path / "out.mp4"))
