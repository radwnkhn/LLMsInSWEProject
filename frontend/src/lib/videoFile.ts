export const MAX_DURATION_SECONDS = 60;
export const MAX_SIZE_BYTES = 200 * 1024 * 1024;
export const TYPE_MESSAGE = "Please upload an MP4 or MOV video";
export const DURATION_MESSAGE = "Videos must be 60 seconds or shorter";
export const SIZE_MESSAGE = "Videos must be 200 MB or smaller";
export const ACCEPT = "video/mp4,video/quicktime,.mp4,.mov";

/** MP4 and MOV only, judged by extension (phones often send MOV files with a generic type). */
export function checkVideoType(file: File): string | null {
  return /\.(mp4|mov)$/i.test(file.name) ? null : TYPE_MESSAGE;
}

/** The first problem with the file, or null. `duration` is null when the browser couldn't read it. */
export function validateVideoFile(file: File, duration: number | null): string | null {
  const typeError = checkVideoType(file);
  if (typeError) return typeError;
  if (file.size > MAX_SIZE_BYTES) return SIZE_MESSAGE;
  if (duration !== null && Number.isFinite(duration) && duration > MAX_DURATION_SECONDS) return DURATION_MESSAGE;
  return null;
}

/** Reads a video's length in the browser without uploading it. */
export function getVideoDuration(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      resolve(video.duration);
    };
    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not read video metadata"));
    };
    video.src = url;
  });
}
