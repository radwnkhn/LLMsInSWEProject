"""Pose quality and timing must be checked before segmentation."""
from types import SimpleNamespace
import numpy as np

from app.pose import MediaPipePoseEstimator


def test_us06_nonfinite_mediapipe_coordinates_are_marked_unusable():
    class Landmarker:
        def detect_for_video(self, image, timestamp):
            return SimpleNamespace(pose_landmarks=[[SimpleNamespace(x=float('nan'), y=.2, visibility=.99, presence=.99)]])
    frames = MediaPipePoseEstimator(landmarker=Landmarker(), image_factory=lambda x: x).estimate([np.zeros((2, 2, 3))], 30)
    point = frames[0].landmarks['nose']
    assert point.confidence == 0


def test_us06_pose_estimation_accepts_source_timestamps_for_variable_frame_rate():
    times = []
    class Landmarker:
        def detect_for_video(self, image, timestamp):
            times.append(timestamp)
            return SimpleNamespace(pose_landmarks=[])
    frames = MediaPipePoseEstimator(landmarker=Landmarker(), image_factory=lambda x: x).estimate(
        [np.zeros((2, 2, 3)) for _ in range(3)], 30, timestamps=[2, 2.05, 2.12])
    assert times == [2000, 2050, 2120]
    assert [f.timestamp for f in frames] == [2, 2.05, 2.12]
