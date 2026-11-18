"""US-04/US-06: optional non-destructive trimming applies before pose analysis."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.pose import PoseFrame
from app.services import build_test_services
from app.testing.fakes import FakeVideoBackend
from app.testing.synthetic import squat
from app.video import OpenCVMediaPipeBackend, VideoInfo
from tests.helpers import signup
from tests.segmentation_sequences import join


def send(client, headers, **bounds):
    return client.post('/uploads', headers=headers, data={'lift': 'squat', **bounds},
                       files={'file': ('set.mp4', b'original-full-video', 'video/mp4')})


@pytest.mark.parametrize('bounds', [
    {'trim_start': -1, 'trim_end': 4}, {'trim_start': 4, 'trim_end': 4},
    {'trim_start': 5, 'trim_end': 4}, {'trim_start': 0, 'trim_end': 11},
    {'trim_start': 'NaN', 'trim_end': 4}, {'trim_start': 0, 'trim_end': 'Infinity'},
    {'trim_start': 1}, {'trim_end': 4}, {'trim_start': 10, 'trim_end': 10.1},
])
def test_us04_invalid_boundaries_rejected_before_storage(client, services, bounds):
    headers, _ = signup(client)
    response = send(client, headers, **bounds)
    assert response.status_code == 422
    assert services.storage.objects == {}
    assert services.repo.uploads == {}


def test_us04_trim_limits_feedback_to_selection_and_preserves_original_times_and_video():
    clip = squat(1)
    # Give the excluded first rep an ascent fault; selection contains only the clean second rep.
    from app.testing.synthetic import SetSpec, RepSpec, make_frames
    frames = join(make_frames(SetSpec(reps=[RepSpec(torso_bump=35)])), clip)
    services = build_test_services(video=FakeVideoBackend(frames=frames))
    client = TestClient(create_app(services))
    headers, _ = signup(client)
    start, end = len(clip) / 30, len(frames) / 30
    response = send(client, headers, trim_start=start, trim_end=end)
    assert response.status_code == 201
    body = response.json()
    row = services.repo.get_upload(body['upload_id'])
    assert (row.trim_start, row.trim_end) == (start, end)
    assert services.storage.objects[row.video_path] == b'original-full-video'
    result = client.get('/analyses/' + body['analysis_id'], headers=headers).json()
    assert result['status'] == 'done'
    assert result['rep_count'] == 1
    assert result['analysis_range'] == {'start_time': start, 'end_time': end}
    assert result['measurements'][0]['start_time'] >= start
    assert result['measurements'][0]['end_time'] < end
    assert result['top_fix'] is None


def test_us04_untrimmed_upload_uses_all_reps(client, services):
    headers, _ = signup(client)
    body = send(client, headers).json()
    row = services.repo.get_upload(body['upload_id'])
    assert row.trim_start is None and row.trim_end is None
    result = client.get('/analyses/' + body['analysis_id'], headers=headers).json()
    assert result['rep_count'] == 5
    assert result.get('analysis_range') is None


def test_us04_retry_preserves_selection_and_original_video():
    video = FakeVideoBackend(frames=join(squat(1), squat(1)), fail_on_poses=True)
    services = build_test_services(video=video)
    client = TestClient(create_app(services))
    headers, _ = signup(client)
    start, end = len(squat(1)) / 30, len(squat(1)) * 2 / 30
    body = send(client, headers, trim_start=start, trim_end=end).json()
    assert services.repo.get_analysis(body['analysis_id']).status == 'failed'
    video.fail_on_poses = False
    retry = client.post('/analyses/' + body['analysis_id'] + '/retry', headers=headers).json()
    result = client.get('/analyses/' + retry['analysis_id'], headers=headers).json()
    assert result['rep_count'] == 1
    assert result['analysis_range']['start_time'] == start


def test_us04_opencv_passes_only_selected_frames_to_pose_and_preserves_source_indices(monkeypatch):
    seen = []
    class Estimator:
        def estimate(self, images, fps):
            return [PoseFrame(i, i / fps, None) for i, img in enumerate(images) if not seen.append(int(img[0, 0, 0]))]
    video = OpenCVMediaPipeBackend(estimator=Estimator())
    monkeypatch.setattr(video, '_frames', lambda path, stride: ((i, np.full((2, 2, 3), i, np.uint8)) for i in range(90) if i % stride == 0))
    frames = video.poses('unused', VideoInfo(3, 30, 90, 2, 2), 'set.mp4', start_time=1, end_time=2)
    assert seen == list(range(30, 60))
    assert [f.index for f in frames] == list(range(30, 60))
    assert frames[0].timestamp == 1
    assert frames[-1].timestamp == 59 / 30
