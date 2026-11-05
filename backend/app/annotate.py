"""Annotated frame: the worst moment of the cited rep with the skeleton and measurement drawn on it."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.faults import Fault
from app.measure import RepMeasurement
from app.pose import Landmark

SKELETON = [
    ("left_shoulder", "right_shoulder"), ("left_hip", "right_hip"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
    ("left_ear", "left_shoulder"), ("right_ear", "right_shoulder"),
]
LINE_COLOR = (0, 220, 255)      # BGR yellow
JOINT_COLOR = (255, 255, 255)
LABEL_BG = (24, 24, 24)
MIN_DRAW_CONFIDENCE = 0.3


@dataclass(frozen=True)
class AnnotationMeta:
    fault_id: str
    rep: int
    frame_index: int
    timestamp: float
    rep_start_time: float
    metric: str
    value: float
    label: str

    def to_dict(self) -> dict:
        return asdict(self)


def select_annotation_frame(rep: RepMeasurement, metric: str) -> int:
    """The frame of `rep` where `metric` is at its worst."""
    return rep.worst_frames.get(metric, rep.turn_frame)


def measurement_label(fault: Fault, value: float) -> str:
    return fault.label_format.format(value=value)


def draw_annotation(image: np.ndarray, landmarks: dict[str, Landmark] | None, label: str) -> np.ndarray:
    """Returns a copy of `image` (BGR) with the skeleton and a measurement label drawn on it."""
    out = image.copy()
    h, w = out.shape[:2]
    thickness = max(2, w // 200)
    if landmarks:
        def px(name):
            lm = landmarks[name]
            return (int(round(lm.x * w)), int(round(lm.y * h))) if lm.confidence >= MIN_DRAW_CONFIDENCE else None

        def mid(a, b):
            pa, pb = px(a), px(b)
            return ((pa[0] + pb[0]) // 2, (pa[1] + pb[1]) // 2) if pa and pb else None

        for a, b in SKELETON:
            pa, pb = px(a), px(b)
            if pa and pb:
                cv2.line(out, pa, pb, LINE_COLOR, thickness, cv2.LINE_AA)
        spine = (mid("left_shoulder", "right_shoulder"), mid("left_hip", "right_hip"))
        if all(spine):
            cv2.line(out, spine[0], spine[1], LINE_COLOR, thickness, cv2.LINE_AA)
        for name in {n for pair in SKELETON for n in pair}:
            p = px(name)
            if p:
                cv2.circle(out, p, thickness + 1, JOINT_COLOR, -1, cv2.LINE_AA)

    # OpenCV can't draw "°", so the label is drawn with Pillow.
    font_size = max(14, h // 18)
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    pil = Image.fromarray(out[:, :, ::-1])
    draw = ImageDraw.Draw(pil)
    pad = font_size // 3
    left, top, right, bottom = draw.textbbox((pad, pad), label, font=font)
    draw.rectangle((0, 0, right + pad, bottom + pad), fill=LABEL_BG[::-1])
    draw.text((pad, pad), label, font=font, fill=(255, 255, 255))
    return np.asarray(pil)[:, :, ::-1].copy()


def encode_png(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("could not encode annotated frame")
    return buf.tobytes()
