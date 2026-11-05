#!/bin/sh
# Downloads MediaPipe's pose landmarker model (Apache 2.0, ~9 MB) into backend/models/.
set -e
cd "$(dirname "$0")/.."
mkdir -p models
curl -fL -o models/pose_landmarker_full.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task
echo "Saved models/pose_landmarker_full.task"
