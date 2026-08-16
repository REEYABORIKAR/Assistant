import os
import hashlib
import magic
from fastapi import UploadFile, HTTPException
from app.core.config import settings

def validate_and_store_file(file: UploadFile, user_id: str, project_id: str) -> tuple[str, str, int, str]:
    """
    Validates the uploaded file, computes its checksum, and saves it to disk.
    Returns (file_path, file_type, file_size, checksum).
    """
    # 1. Read file into memory (we need size, checksum, and magic bytes anyway)
    file_bytes = file.file.read()
    file_size = len(file_bytes)
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE} bytes")
        
    # 2. Checksum
    checksum = hashlib.sha256(file_bytes).hexdigest()
    
    # 3. MIME type validation
    # Use python-magic to get actual mime type
    mime_type = magic.from_buffer(file_bytes, mime=True)
    
    # 4. Extension validation
    _, ext = os.path.splitext(file.filename)
    ext = ext.lower()
    
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Extension {ext} not allowed. Supported: {', '.join(settings.ALLOWED_EXTENSIONS)}")
        
    # 5. Store file
    # Format: Backend/data/documents/{user_id}/{project_id}/{filename}
    # To prevent collisions, we can prefix with checksum or just keep filename since DB has a UUID
    # Let's save as {checksum}{ext} to avoid naming conflicts on disk
    storage_dir = os.path.join("data", "documents", user_id, project_id)
    os.makedirs(storage_dir, exist_ok=True)
    
    safe_filename = f"{checksum}{ext}"
    file_path = os.path.join(storage_dir, safe_filename)
    
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    # Reset file cursor just in case it's used again, though we saved it to disk
    file.file.seek(0)
    
    return file_path, mime_type, file_size, checksum
