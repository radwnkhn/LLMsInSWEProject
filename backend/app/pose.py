"""Pose estimation (MediaPipe) and pose data types."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Iterable

import numpy as np

LANDMARK_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right", "left_shoulder", "right_shoulder", "left_elbow",
    "right_elbow", "left_wrist", "right_wrist", "left_pinky", "right_pinky", "left_index", "right_index",
    "left_thumb", "right_thumb", "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
    "left_heel", "right_heel", "left_foot_index", "right_foot_index",
]


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float
    confidence: float


@dataclass
class PoseFrame:
    index: int
    timestamp: float
    landmarks: dict[str, Landmark] | None  # None: no person detected on this frame


def _to_mp_image(bgr: np.ndarray):
    import mediapipe as mp

    rgb = np.ascontiguousarray(bgr[:, :, ::-1])
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)


class MediaPipePoseEstimator:
    """Runs MediaPipe's PoseLandmarker in VIDEO mode over decoded frames (BGR, as OpenCV reads them).

    `landmarker` can be injected for tests; otherwise one is created from the .task model at `model_path`.
    """

    def __init__(self, landmarker=None, model_path: str | None = None,
                 image_factory: Callable[[np.ndarray], object] = _to_mp_image):
        self._landmarker = landmarker
        self._model_path = model_path
        self._image_factory = image_factory

    def _get_landmarker(self):
        if self._landmarker is None:
            if not self._model_path:
                raise RuntimeError("POSE_MODEL_PATH is not set; run backend/scripts/download_pose_model.sh")
            from mediapipe.tasks.python import BaseOptions, vision

            options = vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=self._model_path),
                running_mode=vision.RunningMode.VIDEO,
                num_poses=1,
            )
            self._landmarker = vision.PoseLandmarker.create_from_options(options)
        return self._landmarker

    def estimate(self, frames: Iterable[np.ndarray], fps: float,
                 timestamps: Iterable[float] | None = None) -> list[PoseFrame]:
        landmarker = self._get_landmarker()
        out: list[PoseFrame] = []
        source_times = iter(timestamps) if timestamps is not None else None
        previous_ms = -1
        for i, image in enumerate(frames):
            timestamp = next(source_times) if source_times is not None else i / fps
            if not math.isfinite(timestamp):
                raise ValueError("Pose timestamps must be finite and strictly increasing")
            timestamp_ms = round(timestamp * 1000)
            if timestamp_ms <= previous_ms:
                raise ValueError("Pose timestamps must be finite and strictly increasing")
            result = landmarker.detect_for_video(self._image_factory(image), timestamp_ms)
            previous_ms = timestamp_ms
            marks = None
            if result.pose_landmarks:
                person = result.pose_landmarks[0]
                marks = {}
                for name, p in zip(LANDMARK_NAMES, person):
                    x, y = float(p.x), float(p.y)
                    visibility, presence = float(p.visibility or 0), float(p.presence or 0)
                    confidence = (max(0., min(1., visibility, presence))
                                  if all(math.isfinite(v) for v in (x, y, visibility, presence)) else 0.)
                    marks[name] = Landmark(x, y, confidence)
            out.append(PoseFrame(index=i, timestamp=timestamp, landmarks=marks))
        return out
