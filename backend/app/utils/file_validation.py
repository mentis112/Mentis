from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import ValidationError

ALLOWED_MIME_TYPES = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    "txt": {"text/plain"},
    "zip": {"application/zip", "application/x-zip-compressed", "multipart/x-zip"},
}


def validate_upload_file(file: UploadFile) -> str:
    settings = get_settings()
    extension = Path(file.filename or "").suffix.lower().lstrip(".")
    allowed_extensions = set(settings.allowed_file_extensions) | set(settings.allowed_archive_extensions)
    if not extension or extension not in allowed_extensions:
        raise ValidationError(
            "Unsupported file format",
            {"allowed_extensions": sorted(allowed_extensions)},
        )

    allowed_mimes = ALLOWED_MIME_TYPES.get(extension, set())
    content_type = (file.content_type or "").lower()
    if allowed_mimes and content_type and content_type not in allowed_mimes:
        raise ValidationError(
            "Uploaded file MIME type does not match the allowed format",
            {"filename": file.filename, "content_type": content_type},
        )

    return extension
