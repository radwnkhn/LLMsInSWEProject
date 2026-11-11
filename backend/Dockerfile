FROM python:3.13.7-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POSE_MODEL_PATH=models/pose_landmarker_full.task \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1

# MediaPipe loads EGL/GLES lazily when the first landmarker is created.
# These libraries must be in the runtime image, not only on the CI host.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl libegl1 libgles2 libgl1 libglib2.0-0 libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
RUN sh scripts/download_pose_model.sh \
    && python scripts/check_pose_runtime.py

RUN useradd --create-home --uid 10001 appuser
USER appuser
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn app.asgi:app --host 0.0.0.0 --port ${PORT:-10000}"]
