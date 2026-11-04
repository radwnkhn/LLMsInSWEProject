"""Reading uploaded videos with OpenCV and running pose estimation on them."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol

import cv2
import numpy as np

from app.pose import MediaPipePoseEstimator, PoseFrame

TARGET_FPS = 30          # pose estimation runs on at most ~30 frames per second
MAX_POSE_WIDTH = 640     # frames are downscaled before pose estimation


class VideoUnreadable(Exception):
    pass


@dataclass(frozen=True)
class VideoInfo:
    duration: float
    fps: float
    frame_count: int
    width: int
    height: int


class VideoBackend(Protocol):
    def probe(self, path: str) -> VideoInfo: ...
    def poses(self, path: str, info: VideoInfo, filename: str) -> list[PoseFrame]: ...
    def frame(self, path: str, index: int) -> np.ndarray: ...


def probe_video(path: str) -> VideoInfo:
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise VideoUnreadable(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0 or count <= 0:
            raise VideoUnreadable(path)
        return VideoInfo(duration=count / fps, fps=fps, frame_count=count,
                         width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    finally:
        cap.release()


def _resize(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    return cv2.resize(image, (MAX_POSE_WIDTH, int(h * MAX_POSE_WIDTH / w))) if w > MAX_POSE_WIDTH else image


class OpenCVMediaPipeBackend:
    def __init__(self, estimator: MediaPipePoseEstimator | None = None, model_path: str | None = None):
        self.model_path = model_path
        self.estimator = estimator

    def probe(self, path: str) -> VideoInfo:
        return probe_video(path)

    def _frames(self, path: str, stride: int) -> Iterator[tuple[int, np.ndarray]]:
        cap = cv2.VideoCapture(path)
        try:
            i = 0
            while True:
                ok, image = cap.read()
                if not ok:
                    break
                if i % stride == 0:
                    yield i, image
                i += 1
        finally:
            cap.release()

    def poses(self, path: str, info: VideoInfo, filename: str) -> list[PoseFrame]:
        stride = max(1, round(info.fps / TARGET_FPS))
        sampled = list(self._frames(path, stride))
        # A fresh landmarker per video: VIDEO mode needs increasing timestamps.
        estimator = self.estimator or MediaPipePoseEstimator(model_path=self.model_path)
        poses = estimator.estimate((_resize(img) for _, img in sampled), fps=info.fps / stride)
        # Report original frame numbers and times so frames can be looked up again later.
        return [PoseFrame(index=idx, timestamp=idx / info.fps, landmarks=p.landmarks) for (idx, _), p in zip(sampled, poses)]

    def frame(self, path: str, index: int) -> np.ndarray:
        cap = cv2.VideoCapture(path)
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, image = cap.read()
            if not ok:
                raise VideoUnreadable(f"frame {index}")
            return image
        finally:
            cap.release()
