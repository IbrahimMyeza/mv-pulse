import os
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import current_app
from werkzeug.utils import secure_filename

try:
    import cloudinary
    import cloudinary.uploader
except Exception:  # pragma: no cover - dependency is optional in local fallback mode
    cloudinary = None


@dataclass(frozen=True)
class StoredMedia:
    public_url: str
    local_path: str
    storage_kind: str


def cloud_storage_configured() -> bool:
    return bool((os.getenv("CLOUDINARY_URL") or "").strip())


def _app_root() -> Path:
    try:
        return Path(current_app.root_path)
    except RuntimeError:
        return Path.cwd()


def configured_media_root() -> Path | None:
    if cloud_storage_configured():
        return None
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


def _configure_cloudinary() -> bool:
    if not cloud_storage_configured():
        return False
    if cloudinary is None:
        raise RuntimeError("cloudinary package is required when CLOUDINARY_URL is set")
    cloudinary.config(secure=True)
    return True


def _upload_to_cloudinary(file_storage, target_folder: str, filename: str) -> StoredMedia:
    _configure_cloudinary()
    folder = _relative_target_folder(target_folder) or "mv-pulse/uploads"
    stream = getattr(file_storage, "stream", file_storage)
    if hasattr(stream, "seek"):
        stream.seek(0)
    upload_result = cloudinary.uploader.upload(
        stream,
        resource_type="auto",
        folder=folder,
        public_id=Path(filename).stem,
        use_filename=False,
        unique_filename=True,
        overwrite=False,
    )
    return StoredMedia(
        public_url=upload_result["secure_url"],
        local_path="",
        storage_kind="cloudinary",
    )


def save_uploaded_file(file_storage, target_folder: str) -> StoredMedia:
    filename = _build_filename(file_storage)
    relative_folder = _relative_target_folder(target_folder)
    relative_path = Path(relative_folder) / filename if relative_folder else Path(filename)

    if cloud_storage_configured():
        return _upload_to_cloudinary(file_storage, target_folder, filename)

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


@contextmanager
def local_media_path(public_url: str | None):
    local_path = resolve_local_media_path(public_url)
    if local_path:
        yield local_path
        return

    if not public_url or not public_url.startswith(("http://", "https://")):
        yield None
        return

    parsed = urlparse(public_url)
    suffix = Path(parsed.path).suffix or ".bin"
    temporary_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        with requests.get(public_url, stream=True, timeout=(10, 60)) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temporary_file.write(chunk)
        temporary_file.close()
        yield temporary_file.name
    finally:
        try:
            temporary_file.close()
        except Exception:
            pass
        try:
            os.unlink(temporary_file.name)
        except OSError:
            pass
