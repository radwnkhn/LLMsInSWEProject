"""US-21 upload deletion, shared by a user deleting their own upload and an admin removing one (US-27)."""
from __future__ import annotations


def upload_media_paths(upload, analyses) -> list[str]:
    """The video plus every analysis frame, including frames a partially failed attempt may have left."""
    paths = {upload.video_path}
    for a in analyses:
        paths.add(f"frames/{upload.user_id}/{a.id}.png")
        if a.frame_path:
            paths.add(a.frame_path)
    return sorted(paths)


def delete_upload_with_media(repo, storage, upload, analyses) -> None:
    """Deletes the media through the Storage API first, then the upload and everything cascading from it
    (analyses, measurements, AI attempts, validator errors, ratings). Raises if either step fails, so the
    caller can report it and the deletion can be retried."""
    storage.delete(upload_media_paths(upload, analyses))
    repo.delete_upload(upload.id)
