"""Fail the image build if real MediaPipe inference cannot run. No credentials needed."""
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pose import MediaPipePoseEstimator


def main() -> None:
    model = Path(__file__).resolve().parents[1] / "models" / "pose_landmarker_full.task"
    estimator = MediaPipePoseEstimator(model_path=str(model))
    try:
        frames = estimator.estimate([np.zeros((256, 256, 3), dtype=np.uint8)], fps=30)
        if len(frames) != 1 or frames[0].landmarks is not None:
            raise RuntimeError("Blank-frame pose inference returned an unexpected result")
        print("Pose runtime inference verified")
    finally:
        if estimator._landmarker is not None:
            estimator._landmarker.close()


if __name__ == "__main__":
    main()
