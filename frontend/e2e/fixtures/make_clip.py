"""Writes set.mp4: a 12-second VP9 clip for the e2e tests. Run with the backend venv:

    ../backend/.venv/bin/python e2e/fixtures/make_clip.py
"""
from pathlib import Path

import cv2
import numpy as np

out = Path(__file__).with_name("set.mp4")
writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"vp09"), 10, (160, 96))
for i in range(120):
    frame = np.full((96, 160, 3), 40, np.uint8)
    cv2.putText(frame, f"{i / 10:4.1f}s", (40, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    writer.write(frame)
writer.release()
print(out, out.stat().st_size, "bytes")
