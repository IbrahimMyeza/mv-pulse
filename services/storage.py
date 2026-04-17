import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


@dataclass(frozen=True)
class StoredMedia:
    public_url: str
    local_path: str
    storage_kind: str


def _app_root() -> Path:
    try:
        return Path(current_app.root_path)
    except RuntimeError:
        return Path.cwd()


def configured_media_root() -> Path | None:
    configured = os.getenv("MEDIA_STORAGE_ROOT") or os.getenv("RENDER_DISK_MOUNT_PATH")
    if not configured:
        return None
    return Path(configured) / "media"


def _static_root() -> Path:
    return _app_root() / "static"


def _relative_target_folder(target_folder: str) -> str:
    folder = (target_folder or "").replace("\\", "/").strip("/")
    if folder.startswith("static/"):
        folder = folder[len("static/"):]
    return folder


def _build_filename(file_storage) -> str:
    original_name = secure_filename(file_storage.filename or "upload.bin")
    if not original_name:
        original_name = "upload.bin"
    name, extension = os.path.splitext(original_name)
    unique_prefix = uuid4().hex
    return f"{name[:80] or 'upload'}-{unique_prefix}{extension[:12]}"


def save_uploaded_file(file_storage, target_folder: str) -> StoredMedia:
    filename = _build_filename(file_storage)
    relative_folder = _relative_target_folder(target_folder)
    relative_path = Path(relative_folder) / filename if relative_folder else Path(filename)

    media_root = configured_media_root()
    if media_root:
        destination = media_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_storage.save(destination)
        return StoredMedia(
            public_url=f"/media/{relative_path.as_posix()}",
            local_path=str(destination),
            storage_kind="persistent-disk",
        )

    destination = _static_root() / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_storage.save(destination)
    return StoredMedia(
        public_url=f"/static/{relative_path.as_posix()}",
        local_path=str(destination),
        storage_kind="local-static",
    )


def resolve_local_media_path(public_url: str | None) -> str | None:
    if not public_url:
        return None

    if public_url.startswith("/media/"):
        media_root = configured_media_root()
        if not media_root:
            return None
        return str(media_root / public_url[len("/media/"):])

    if public_url.startswith("/static/"):
        return str(_app_root() / public_url.lstrip("/"))

    return None
