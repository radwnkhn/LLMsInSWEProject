"""Shrinks uploaded videos before they're stored, so phone clips fit Supabase's per-file limit (50 MB on the
free plan). Pose estimation already runs on frames downscaled to 640 px, so nothing the analysis uses is lost."""
from __future__ import annotations

import subprocess
from typing import Protocol

from app.video import VideoUnreadable

MAX_LONG_SIDE = 1280
STORED_EXTENSION = ".mp4"
STORED_CONTENT_TYPE = "video/mp4"


class VideoCompressor(Protocol):
    def compress(self, src: str, dst: str) -> None: ...


class FfmpegCompressor:
    """H.264 MP4 with the longer side at most 1280 px (never upscaled), the original frames and frame rate, and no
    audio. Uses the ffmpeg binary bundled with the imageio-ffmpeg package, so the server needs no system ffmpeg."""

    MAX_BITRATE_KBPS = 4000  # 60 s stays around 30 MB
    TIMEOUT_SECONDS = 300

    def __init__(self, ffmpeg: str | None = None):
        self.ffmpeg = ffmpeg

    def _exe(self) -> str:
        if self.ffmpeg is None:
            import imageio_ffmpeg

            self.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        return self.ffmpeg

    def compress(self, src: str, dst: str) -> None:
        scale = (f"scale='min({MAX_LONG_SIDE},iw)':'min({MAX_LONG_SIDE},ih)'"
                 ":force_original_aspect_ratio=decrease:force_divisible_by=2")
        cmd = [self._exe(), "-nostdin", "-y", "-loglevel", "error", "-i", src,
               "-map", "0:v:0", "-an", "-vf", scale, "-fps_mode", "passthrough",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
               "-maxrate", f"{self.MAX_BITRATE_KBPS}k", "-bufsize", f"{2 * self.MAX_BITRATE_KBPS}k",
               "-movflags", "+faststart", dst]
        try:
            done = subprocess.run(cmd, capture_output=True, timeout=self.TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as e:
            raise VideoUnreadable("compressing the video timed out") from e
        if done.returncode != 0:
            raise VideoUnreadable(done.stderr.decode(errors="replace").strip()[-500:] or "ffmpeg failed")
