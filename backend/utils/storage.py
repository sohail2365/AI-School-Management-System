"""
Thin wrapper around Supabase Storage's REST API, used because Vercel's
serverless filesystem is ephemeral — uploaded files can't be saved to local
disk and expected to still be there on the next request/deployment.

Uses `requests` (already a dependency) instead of the supabase-py SDK to
avoid adding a new package and its own version/compatibility surface.

Files are kept in a PRIVATE bucket (not public), because some of what gets
uploaded here — B-forms, CNIC copies — is sensitive government ID data.
Instead of permanent public URLs, callers get back a *storage path*, and
generate a short-lived signed URL only when the file actually needs to be
viewed (see get_signed_url below).
"""
import time
import uuid

import requests
from fastapi import HTTPException, UploadFile, status

from backend.config import settings

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/pdf"}
MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB — generous for a phone photo of a document


def _require_configured():
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "File uploads are not configured yet. Set SUPABASE_URL and "
                "SUPABASE_SERVICE_KEY in the backend environment."
            ),
        )


def upload_school_file(file: UploadFile, school_id: int, subfolder: str) -> str:
    """
    Same as upload_student_file but for school-level assets (e.g. background
    image) that aren't tied to a specific student.
    """
    _require_configured()

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Only JPG, PNG, WEBP images or PDF files are allowed.",
        )

    file_bytes = file.file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=422, detail="File too large (max 8 MB).")
    if len(file_bytes) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    unique_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
    path = f"school_{school_id}/{subfolder}/{unique_name}"

    upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_BUCKET}/{path}"
    resp = requests.post(
        upload_url,
        headers={
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        data=file_bytes,
        timeout=20,
    )

    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=502,
            detail=f"Upload to storage failed: {resp.status_code} {resp.text[:200]}",
        )

    return path


def upload_student_file(file: UploadFile, school_id: int, student_id: int, subfolder: str) -> str:
    """
    Uploads a single file and returns the storage PATH (not a public URL).
    Raises HTTPException on invalid file type/size or upload failure.
    """
    _require_configured()

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Only JPG, PNG, WEBP images or PDF files are allowed.",
        )

    file_bytes = file.file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=422, detail="File too large (max 8 MB).")
    if len(file_bytes) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    unique_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
    path = f"school_{school_id}/student_{student_id}/{subfolder}/{unique_name}"

    upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_BUCKET}/{path}"
    resp = requests.post(
        upload_url,
        headers={
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        data=file_bytes,
        timeout=20,
    )

    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=502,
            detail=f"Upload to storage failed: {resp.status_code} {resp.text[:200]}",
        )

    return path


def get_signed_url(path: str, expires_in: int = 3600) -> str:
    """Generates a temporary signed URL (default 1 hour) to view a private file."""
    _require_configured()

    sign_url = f"{settings.SUPABASE_URL}/storage/v1/object/sign/{settings.SUPABASE_BUCKET}/{path}"
    resp = requests.post(
        sign_url,
        headers={
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Content-Type": "application/json",
        },
        json={"expiresIn": expires_in},
        timeout=15,
    )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Could not generate file link: {resp.status_code} {resp.text[:200]}",
        )
    signed_path = resp.json().get("signedURL")
    if not signed_path:
        raise HTTPException(status_code=502, detail="Storage did not return a signed URL.")
    return f"{settings.SUPABASE_URL}/storage/v1{signed_path}"


def delete_file(path: str) -> None:
    _require_configured()
    delete_url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_BUCKET}"
    requests.delete(
        delete_url,
        headers={
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Content-Type": "application/json",
        },
        json={"prefixes": [path]},
        timeout=15,
    )
