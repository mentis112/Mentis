import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


class LocalFileStorage:
    def __init__(self) -> None:
        self.root = get_settings().storage_root

    def save_submission_content(
        self,
        *,
        instructor_id: str,
        group_id: str,
        batch_id: str,
        filename: str | None,
        content: bytes,
    ) -> tuple[str, str, int]:
        target_dir = self.root / instructor_id / group_id / batch_id
        target_dir.mkdir(parents=True, exist_ok=True)

        extension = Path(filename or "").suffix
        target_name = f"{uuid4()}{extension}"
        target_path = target_dir / target_name

        target_path.write_bytes(content)
        checksum = hashlib.sha256(content).hexdigest()
        return str(target_path.resolve()), checksum, len(content)

    async def save_submission_file(
        self,
        *,
        instructor_id: str,
        group_id: str,
        batch_id: str,
        upload_file: UploadFile,
    ) -> tuple[str, str, int]:
        content = await upload_file.read()
        return self.save_submission_content(
            instructor_id=instructor_id,
            group_id=group_id,
            batch_id=batch_id,
            filename=upload_file.filename,
            content=content,
        )
