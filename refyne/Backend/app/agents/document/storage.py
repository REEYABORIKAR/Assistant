import hashlib
import os

import magic
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.storage.object_store import get_object_store


def validate_and_store_file(file: UploadFile, user_id: str, project_id: str) -> tuple[str, str, int, str, str]:
    """
    Validates the uploaded file, computes its checksum, and stores it in object storage.
    Returns (file_path, file_type, file_size, checksum, storage_key).
    """
    file_bytes = file.file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE} bytes")

    checksum = hashlib.sha256(file_bytes).hexdigest()

    mime_type = magic.from_buffer(file_bytes, mime=True)

    _, ext = os.path.splitext(file.filename)
    ext = ext.lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Extension {ext} not allowed. Supported: {', '.join(settings.ALLOWED_EXTENSIONS)}")

    storage_key = f"documents/{user_id}/{project_id}/{checksum}{ext}"

    store = get_object_store()
    store.upload(key=storage_key, data=file_bytes, content_type=mime_type)

    file.file.seek(0)

    return storage_key, mime_type, file_size, checksum, storage_key
