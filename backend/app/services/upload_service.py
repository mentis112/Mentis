from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import ParserStatus, SubmissionStatus, UploadBatchStatus
from app.models.submission import Submission, SubmissionContentCache, UploadBatch
from app.repositories.group_repository import GroupRepository
from app.repositories.submission_repository import SubmissionRepository
from app.services.audit_service import AuditService
from app.utils.file_parsers import FileParserService
from app.utils.file_validation import validate_upload_file
from app.utils.storage import LocalFileStorage
from app.utils.student_id_extractor import extract_student_id, extract_student_id_from_filename


@dataclass
class UploadCandidate:
    source_upload_index: int
    source_upload_filename: str
    provided_student_id: str | None
    filename: str
    extension: str
    content: bytes
    from_archive: bool


class UploadService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.group_repository = GroupRepository(session)
        self.submission_repository = SubmissionRepository(session)
        self.audit_service = AuditService(session)
        self.storage = LocalFileStorage()
        self.parser = FileParserService()
        self.settings = get_settings()

    async def upload_files(
        self,
        *,
        instructor_id: str,
        group_id: str,
        student_ids: list[str],
        student_id_overrides: dict[str, str] | None = None,
        files: list[UploadFile],
        excluded_archive_entries: list[str] | None = None,
        allowed_existing_duplicates: list[str] | None = None,
    ) -> tuple[UploadBatch, list[dict]]:
        if not files:
            raise ValidationError("At least one file is required")
        if len(files) > self.settings.max_upload_batch_files:
            raise ValidationError(
                "Upload batch exceeds the configured file limit",
                {"max_files": self.settings.max_upload_batch_files},
            )

        normalized_student_ids = self._normalize_student_ids(student_ids, files_count=len(files))
        normalized_student_id_overrides = self._normalize_student_id_overrides(student_id_overrides or {})
        max_size_bytes = self.settings.max_upload_file_size_mb * 1024 * 1024
        candidates, pre_results = await self._expand_upload_candidates(
            files=files,
            normalized_student_ids=normalized_student_ids,
            max_size_bytes=max_size_bytes,
            excluded_archive_entries=set(excluded_archive_entries or []),
        )
        if len(candidates) + len(pre_results) > self.settings.max_upload_batch_files:
            raise ValidationError(
                "Upload batch exceeds the configured file limit",
                {"max_files": self.settings.max_upload_batch_files},
            )

        group = await self.group_repository.get_by_id_for_instructor(group_id, instructor_id)
        if not group:
            raise NotFoundError("Assignment group not found")
        if not group.is_active:
            raise ValidationError("Cannot upload submissions to an inactive assignment group")

        existing_submissions = await self.submission_repository.list_for_group(group_id)
        existing_indexes = self._build_existing_duplicate_indexes(existing_submissions)
        allowed_existing_duplicates_set = {item.strip() for item in (allowed_existing_duplicates or []) if item.strip()}
        batch = UploadBatch(
            instructor_id=instructor_id,
            group_id=group_id,
            total_files=len(candidates) + len(pre_results),
            accepted_files=0,
            rejected_files=len(pre_results),
            status=UploadBatchStatus.PENDING,
        )
        await self.submission_repository.create_batch(batch)

        results: list[dict] = list(pre_results)
        seen_checksums: dict[str, str] = {}
        seen_filenames: dict[str, str] = {}
        seen_student_ids: dict[str, str] = {}

        for candidate in candidates:
            stored_path: str | None = None
            filename = candidate.filename
            try:
                checksum = self._calculate_checksum(candidate.content)
                extracted_text: str | None = None
                parser_status = ParserStatus.NOT_STARTED
                parser_error: str | None = None

                try:
                    extracted_text = self.parser.parse_bytes(candidate.content, candidate.extension)
                    if not extracted_text.strip():
                        raise ValidationError("The uploaded file did not produce readable content")
                    parser_status = ParserStatus.SUCCESS
                except Exception as exc:
                    parser_status = ParserStatus.FAILED
                    parser_error = str(exc)

                resolved_student_id = self._resolve_student_id(
                    provided_student_id=(
                        normalized_student_id_overrides.get(candidate.filename.strip())
                        or candidate.provided_student_id
                    ),
                    extracted_text=extracted_text,
                    filename=filename,
                )
                duplicate_reasons = self._detect_duplicate_reasons(
                    filename=filename,
                    checksum=checksum,
                    student_id=resolved_student_id,
                    seen_checksums=seen_checksums,
                    seen_filenames=seen_filenames,
                    seen_student_ids=seen_student_ids,
                    existing_indexes=existing_indexes,
                    include_existing=False,
                )
                existing_match = self._detect_existing_duplicate_match(
                    filename=filename,
                    checksum=checksum,
                    student_id=resolved_student_id,
                    existing_indexes=existing_indexes,
                )
                existing_duplicate_reasons = existing_match["reasons"]
                allow_existing_duplicate = filename in allowed_existing_duplicates_set
                if duplicate_reasons or (existing_duplicate_reasons and not allow_existing_duplicate):
                    raise ValidationError(
                        "Duplicate submission detected",
                        {
                            "duplicate_reasons": duplicate_reasons,
                            "existing_duplicate_reasons": existing_duplicate_reasons,
                            "has_existing_match": bool(existing_duplicate_reasons),
                            "existing_submission_id": existing_match["submission_id"],
                            "existing_submission_evaluated": existing_match["is_evaluated"],
                        },
                    )

                stored_path, _, _ = self.storage.save_submission_content(
                    instructor_id=instructor_id,
                    group_id=group_id,
                    batch_id=batch.id,
                    filename=filename,
                    content=candidate.content,
                )

                submission = await self.submission_repository.create_submission(
                    Submission(
                        group_id=group_id,
                        upload_batch_id=batch.id,
                        file_path=stored_path,
                        original_filename=filename,
                        student_id=resolved_student_id or "",
                        status=SubmissionStatus.PENDING if parser_status == ParserStatus.SUCCESS else SubmissionStatus.FAILED,
                        error_message=parser_error,
                    )
                )
                await self.submission_repository.create_content_cache(
                    SubmissionContentCache(
                        submission_id=submission.id,
                        extracted_text=extracted_text,
                        parser_status=parser_status,
                        parser_error=parser_error,
                        content_sha256=checksum,
                    )
                )

                seen_checksums[checksum] = filename
                seen_filenames[filename.strip().casefold()] = filename
                if resolved_student_id:
                    seen_student_ids[resolved_student_id.strip().casefold()] = filename

                batch.accepted_files += 1
                results.append(
                    {
                        "original_filename": filename,
                        "student_id": resolved_student_id,
                        "accepted": True,
                        "reason": submission.error_message or self._build_student_id_reason(resolved_student_id),
                        "submission_id": submission.id,
                        "status": submission.status,
                        "needs_student_id": resolved_student_id is None,
                        "is_duplicate": False,
                        "duplicate_reasons": [],
                        "has_existing_match": bool(existing_duplicate_reasons),
                        "existing_duplicate_reasons": existing_duplicate_reasons,
                        "existing_submission_id": existing_match["submission_id"],
                        "existing_submission_evaluated": existing_match["is_evaluated"],
                        "source_upload_index": candidate.source_upload_index,
                        "source_upload_filename": candidate.source_upload_filename,
                        "from_archive": candidate.from_archive,
                    }
                )
            except Exception as exc:
                batch.rejected_files += 1
                if stored_path:
                    Path(stored_path).unlink(missing_ok=True)
                duplicate_reasons = self._extract_duplicate_reasons(exc)
                existing_duplicate_reasons = self._extract_existing_duplicate_reasons(exc)
                results.append(
                    {
                        "original_filename": filename,
                        "student_id": candidate.provided_student_id,
                        "accepted": False,
                        "reason": duplicate_reasons[0] if duplicate_reasons else str(exc),
                        "submission_id": None,
                        "status": None,
                        "needs_student_id": False,
                        "is_duplicate": bool(duplicate_reasons),
                        "duplicate_reasons": duplicate_reasons,
                        "has_existing_match": bool(existing_duplicate_reasons),
                        "existing_duplicate_reasons": existing_duplicate_reasons,
                        "existing_submission_id": self._extract_existing_submission_id(exc),
                        "existing_submission_evaluated": self._extract_existing_submission_evaluated(exc),
                        "source_upload_index": candidate.source_upload_index,
                        "source_upload_filename": candidate.source_upload_filename,
                        "from_archive": candidate.from_archive,
                    }
                )

        if batch.accepted_files == batch.total_files:
            batch.status = UploadBatchStatus.COMPLETED
        elif batch.accepted_files > 0:
            batch.status = UploadBatchStatus.PARTIAL
        else:
            batch.status = UploadBatchStatus.FAILED
        await self.submission_repository.save_batch(batch)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="upload.batch_created",
            entity_type="upload_batch",
            entity_id=batch.id,
            metadata_json={
                "accepted_files": batch.accepted_files,
                "rejected_files": batch.rejected_files,
            },
        )
        await self.session.commit()
        return batch, results

    async def preview_student_ids(
        self,
        *,
        instructor_id: str,
        group_id: str | None,
        files: list[UploadFile],
        excluded_archive_entries: list[str] | None = None,
    ) -> list[dict]:
        if not files:
            raise ValidationError("At least one file is required")
        if len(files) > self.settings.max_upload_batch_files:
            raise ValidationError(
                "Upload batch exceeds the configured file limit",
                {"max_files": self.settings.max_upload_batch_files},
            )
        max_size_bytes = self.settings.max_upload_file_size_mb * 1024 * 1024
        normalized_student_ids = [None] * len(files)
        candidates, pre_results = await self._expand_upload_candidates(
            files=files,
            normalized_student_ids=normalized_student_ids,
            max_size_bytes=max_size_bytes,
            excluded_archive_entries=set(excluded_archive_entries or []),
        )
        if len(candidates) + len(pre_results) > self.settings.max_upload_batch_files:
            raise ValidationError(
                "Upload batch exceeds the configured file limit",
                {"max_files": self.settings.max_upload_batch_files},
            )

        existing_indexes = {
            "by_checksum": {},
            "by_filename": {},
            "by_student_id": {},
        }
        if group_id:
            group = await self.group_repository.get_by_id_for_instructor(group_id, instructor_id)
            if not group:
                raise NotFoundError("Assignment group not found")
            existing_submissions = await self.submission_repository.list_for_group(group_id)
            existing_indexes = self._build_existing_duplicate_indexes(existing_submissions)

        results: list[dict] = list(pre_results)
        seen_checksums: dict[str, str] = {}
        seen_filenames: dict[str, str] = {}
        seen_student_ids: dict[str, str] = {}

        for candidate in candidates:
            filename = candidate.filename
            try:
                checksum = self._calculate_checksum(candidate.content)
                extracted_text: str | None = None
                parser_error: str | None = None
                try:
                    extracted_text = self.parser.parse_bytes(candidate.content, candidate.extension)
                    if not extracted_text.strip():
                        raise ValidationError("The uploaded file did not produce readable content")
                except Exception as exc:
                    parser_error = str(exc)

                student_id = self._resolve_student_id(
                    provided_student_id=None,
                    extracted_text=extracted_text,
                    filename=filename,
                )
                duplicate_reasons = self._detect_duplicate_reasons(
                    filename=filename,
                    checksum=checksum,
                    student_id=student_id,
                    seen_checksums=seen_checksums,
                    seen_filenames=seen_filenames,
                    seen_student_ids=seen_student_ids,
                    existing_indexes=existing_indexes,
                    include_existing=False,
                )
                existing_match = self._detect_existing_duplicate_match(
                    filename=filename,
                    checksum=checksum,
                    student_id=student_id,
                    existing_indexes=existing_indexes,
                )
                existing_duplicate_reasons = existing_match["reasons"]

                seen_checksums[checksum] = filename
                seen_filenames[filename.strip().casefold()] = filename
                if student_id:
                    seen_student_ids[student_id.strip().casefold()] = filename

                reason = None
                if duplicate_reasons:
                    reason = duplicate_reasons[0]
                elif existing_duplicate_reasons:
                    reason = existing_duplicate_reasons[0]
                elif parser_error:
                    reason = parser_error
                else:
                    reason = self._build_student_id_reason(student_id)

                results.append(
                    {
                        "original_filename": filename,
                        "student_id": student_id,
                        "accepted": not duplicate_reasons and not existing_duplicate_reasons,
                        "reason": reason,
                        "needs_student_id": student_id is None,
                        "is_duplicate": bool(duplicate_reasons),
                        "duplicate_reasons": duplicate_reasons,
                        "has_existing_match": bool(existing_duplicate_reasons),
                        "existing_duplicate_reasons": existing_duplicate_reasons,
                        "existing_submission_id": existing_match["submission_id"],
                        "existing_submission_evaluated": existing_match["is_evaluated"],
                        "source_upload_index": candidate.source_upload_index,
                        "source_upload_filename": candidate.source_upload_filename,
                        "from_archive": candidate.from_archive,
                    }
                )
            except Exception as exc:
                duplicate_reasons = self._extract_duplicate_reasons(exc)
                existing_duplicate_reasons = self._extract_existing_duplicate_reasons(exc)
                results.append(
                    {
                        "original_filename": filename,
                        "student_id": None,
                        "accepted": False,
                        "reason": duplicate_reasons[0] if duplicate_reasons else str(exc),
                        "needs_student_id": True,
                        "is_duplicate": bool(duplicate_reasons),
                        "duplicate_reasons": duplicate_reasons,
                        "has_existing_match": bool(existing_duplicate_reasons),
                        "existing_duplicate_reasons": existing_duplicate_reasons,
                        "existing_submission_id": self._extract_existing_submission_id(exc),
                        "existing_submission_evaluated": self._extract_existing_submission_evaluated(exc),
                        "source_upload_index": candidate.source_upload_index,
                        "source_upload_filename": candidate.source_upload_filename,
                        "from_archive": candidate.from_archive,
                    }
                )
        return results

    async def _expand_upload_candidates(
        self,
        *,
        files: list[UploadFile],
        normalized_student_ids: list[str | None],
        max_size_bytes: int,
        excluded_archive_entries: set[str],
    ) -> tuple[list[UploadCandidate], list[dict]]:
        candidates: list[UploadCandidate] = []
        pre_results: list[dict] = []

        for source_upload_index, (upload_file, provided_student_id) in enumerate(
            zip(files, normalized_student_ids, strict=True)
        ):
            source_upload_filename = upload_file.filename or "unknown"
            try:
                extension = validate_upload_file(upload_file)
                content = await upload_file.read()
                await upload_file.seek(0)
                if len(content) > max_size_bytes:
                    raise ValidationError(
                        "File exceeds the configured size limit",
                        {"max_file_size_mb": self.settings.max_upload_file_size_mb},
                    )

                if extension == "zip":
                    archive_candidates, archive_pre_results = self._extract_zip_candidates(
                        archive_content=content,
                        archive_filename=source_upload_filename,
                        source_upload_index=source_upload_index,
                        provided_student_id=provided_student_id,
                        max_size_bytes=max_size_bytes,
                        excluded_archive_entries=excluded_archive_entries,
                    )
                    candidates.extend(archive_candidates)
                    pre_results.extend(archive_pre_results)
                    continue

                candidates.append(
                    UploadCandidate(
                        source_upload_index=source_upload_index,
                        source_upload_filename=source_upload_filename,
                        provided_student_id=provided_student_id,
                        filename=source_upload_filename,
                        extension=extension,
                        content=content,
                        from_archive=False,
                    )
                )
            except Exception as exc:
                duplicate_reasons = self._extract_duplicate_reasons(exc)
                pre_results.append(
                    {
                        "original_filename": source_upload_filename,
                        "student_id": provided_student_id,
                        "accepted": False,
                        "reason": duplicate_reasons[0] if duplicate_reasons else str(exc),
                        "submission_id": None,
                        "status": None,
                        "needs_student_id": False,
                        "is_duplicate": bool(duplicate_reasons),
                        "duplicate_reasons": duplicate_reasons,
                        "source_upload_index": source_upload_index,
                        "source_upload_filename": source_upload_filename,
                        "from_archive": False,
                    }
                )

        return candidates, pre_results

    def _extract_zip_candidates(
        self,
        *,
        archive_content: bytes,
        archive_filename: str,
        source_upload_index: int,
        provided_student_id: str | None,
        max_size_bytes: int,
        excluded_archive_entries: set[str],
    ) -> tuple[list[UploadCandidate], list[dict]]:
        candidates: list[UploadCandidate] = []
        pre_results: list[dict] = []
        allowed_content_extensions = set(self.settings.allowed_file_extensions)
        allowed_content_extensions.discard("zip")

        try:
            with ZipFile(BytesIO(archive_content)) as archive:
                members = [member for member in archive.infolist() if not member.is_dir()]
                if not members:
                    pre_results.append(
                        {
                            "original_filename": archive_filename,
                            "student_id": provided_student_id,
                            "accepted": False,
                            "reason": "ZIP archive is empty",
                            "submission_id": None,
                            "status": None,
                            "needs_student_id": False,
                            "is_duplicate": False,
                            "duplicate_reasons": [],
                            "source_upload_index": source_upload_index,
                            "source_upload_filename": archive_filename,
                            "from_archive": True,
                        }
                    )
                    return candidates, pre_results

                if len(members) > self.settings.max_archive_entries:
                    raise ValidationError(
                        "ZIP archive contains too many files",
                        {"max_archive_entries": self.settings.max_archive_entries},
                    )

                for member in members:
                    member_name = member.filename.strip() or "unknown"
                    if self._is_ignorable_archive_member(member_name):
                        continue
                    display_filename = f"{archive_filename}::{member_name}"
                    if display_filename in excluded_archive_entries:
                        continue
                    member_extension = Path(member_name).suffix.lower().lstrip(".")

                    if not member_extension or member_extension not in allowed_content_extensions:
                        pre_results.append(
                            {
                                "original_filename": display_filename,
                                "student_id": provided_student_id,
                                "accepted": False,
                                "reason": "Unsupported file inside ZIP archive",
                                "submission_id": None,
                                "status": None,
                                "needs_student_id": False,
                                "is_duplicate": False,
                                "duplicate_reasons": [],
                                "source_upload_index": source_upload_index,
                                "source_upload_filename": archive_filename,
                                "from_archive": True,
                            }
                        )
                        continue

                    if member.file_size > max_size_bytes:
                        pre_results.append(
                            {
                                "original_filename": display_filename,
                                "student_id": provided_student_id,
                                "accepted": False,
                                "reason": (
                                    f"File inside ZIP exceeds the configured size limit ({self.settings.max_upload_file_size_mb} MB)"
                                ),
                                "submission_id": None,
                                "status": None,
                                "needs_student_id": False,
                                "is_duplicate": False,
                                "duplicate_reasons": [],
                                "source_upload_index": source_upload_index,
                                "source_upload_filename": archive_filename,
                                "from_archive": True,
                            }
                        )
                        continue

                    member_content = archive.read(member)
                    if len(member_content) > max_size_bytes:
                        pre_results.append(
                            {
                                "original_filename": display_filename,
                                "student_id": provided_student_id,
                                "accepted": False,
                                "reason": (
                                    f"File inside ZIP exceeds the configured size limit ({self.settings.max_upload_file_size_mb} MB)"
                                ),
                                "submission_id": None,
                                "status": None,
                                "needs_student_id": False,
                                "is_duplicate": False,
                                "duplicate_reasons": [],
                                "source_upload_index": source_upload_index,
                                "source_upload_filename": archive_filename,
                                "from_archive": True,
                            }
                        )
                        continue

                    candidates.append(
                        UploadCandidate(
                            source_upload_index=source_upload_index,
                            source_upload_filename=archive_filename,
                            provided_student_id=provided_student_id,
                            filename=display_filename,
                            extension=member_extension,
                            content=member_content,
                            from_archive=True,
                        )
                    )
                if not candidates and not pre_results:
                    pre_results.append(
                        {
                            "original_filename": archive_filename,
                            "student_id": provided_student_id,
                            "accepted": False,
                            "reason": "ZIP archive does not contain supported files",
                            "submission_id": None,
                            "status": None,
                            "needs_student_id": False,
                            "is_duplicate": False,
                            "duplicate_reasons": [],
                            "source_upload_index": source_upload_index,
                            "source_upload_filename": archive_filename,
                            "from_archive": True,
                        }
                    )

        except BadZipFile as exc:
            raise ValidationError("Corrupted or unsupported ZIP archive") from exc
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError("Failed to read ZIP archive", {"error": str(exc)}) from exc

        return candidates, pre_results

    def _is_ignorable_archive_member(self, member_name: str) -> bool:
        normalized = member_name.replace("\\", "/").strip("/")
        if not normalized:
            return True
        parts = [part for part in normalized.split("/") if part]
        if not parts:
            return True
        basename = parts[-1]
        if "__MACOSX" in parts:
            return True
        if basename.startswith("._"):
            return True
        if basename in {".DS_Store", "Thumbs.db"}:
            return True
        return False

    def _normalize_student_ids(self, student_ids: list[str], *, files_count: int) -> list[str | None]:
        if not student_ids:
            return [None] * files_count
        if len(student_ids) != files_count:
            raise ValidationError(
                "Student IDs must either be omitted entirely or provided for every uploaded file",
                {"files_count": files_count, "student_ids_count": len(student_ids)},
            )
        return [self._normalize_manual_student_id(item) for item in student_ids]

    def _normalize_student_id_overrides(self, overrides: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in overrides.items():
            normalized_key = str(key).strip()
            normalized_value = self._normalize_manual_student_id(str(value))
            if normalized_key and normalized_value:
                normalized[normalized_key] = normalized_value
        return normalized

    def _normalize_manual_student_id(self, value: str) -> str | None:
        normalized = value.strip()
        if not normalized:
            return None
        if not normalized.isdigit() or len(normalized) < 5:
            raise ValidationError("Student ID must contain digits only and be at least 5 digits long")
        return normalized

    def _resolve_student_id(
        self,
        *,
        provided_student_id: str | None,
        extracted_text: str | None,
        filename: str | None,
    ) -> str | None:
        if provided_student_id:
            return provided_student_id
        from_text = extract_student_id(extracted_text)
        if from_text:
            return from_text
        return extract_student_id_from_filename(filename)

    def _build_student_id_reason(self, student_id: str | None) -> str | None:
        if student_id:
            return None
        return "Student ID was not found in the uploaded file. This submission will not be evaluated until a student ID is saved."

    def _calculate_checksum(self, content: bytes) -> str:
        import hashlib

        return hashlib.sha256(content).hexdigest()

    def _build_existing_duplicate_indexes(self, submissions: list[Submission]) -> dict[str, dict[str, dict[str, str | bool]]]:
        by_checksum: dict[str, dict[str, str | bool]] = {}
        by_filename: dict[str, dict[str, str | bool]] = {}
        by_student_id: dict[str, dict[str, str | bool]] = {}
        for submission in submissions:
            filename = submission.original_filename
            reference = self._build_submission_reference(submission)
            info = {
                "reference": reference,
                "submission_id": submission.id,
                "is_evaluated": bool(submission.evaluations),
            }
            by_filename.setdefault(filename.strip().casefold(), info)
            if submission.student_id.strip():
                by_student_id.setdefault(submission.student_id.strip().casefold(), info)
            checksum = submission.content_cache.content_sha256 if submission.content_cache else None
            if checksum:
                by_checksum.setdefault(checksum, info)
        return {
            "by_checksum": by_checksum,
            "by_filename": by_filename,
            "by_student_id": by_student_id,
        }

    def _build_submission_reference(self, submission: Submission) -> str:
        student_part = submission.student_id.strip() or "unknown student"
        return f"{submission.original_filename} ({student_part})"

    def _detect_duplicate_reasons(
        self,
        *,
        filename: str,
        checksum: str,
        student_id: str | None,
        seen_checksums: dict[str, str],
        seen_filenames: dict[str, str],
        seen_student_ids: dict[str, str],
        existing_indexes: dict[str, dict[str, dict[str, str | bool]]],
        include_existing: bool,
    ) -> list[str]:
        reasons: list[str] = []
        normalized_filename = filename.strip().casefold()
        normalized_student_id = student_id.strip().casefold() if student_id else None

        if checksum in seen_checksums:
            reasons.append(
                f"Duplicate file content in this upload batch. It matches '{seen_checksums[checksum]}'."
            )
        if normalized_filename and normalized_filename in seen_filenames:
            reasons.append(
                f"Duplicate filename in this upload batch. It matches '{seen_filenames[normalized_filename]}'."
            )
        if normalized_student_id and normalized_student_id in seen_student_ids:
            reasons.append(
                f"Duplicate student ID {student_id} in this upload batch. It also appears in '{seen_student_ids[normalized_student_id]}'."
            )

        if include_existing:
            existing_checksum_match = existing_indexes["by_checksum"].get(checksum)
            if existing_checksum_match:
                reasons.append(
                    f"Duplicate file content with an existing submission in this group: {existing_checksum_match['reference']}."
                )
            existing_filename_match = existing_indexes["by_filename"].get(normalized_filename)
            if existing_filename_match:
                reasons.append(
                    f"Duplicate filename with an existing submission in this group: {existing_filename_match['reference']}."
                )
            if normalized_student_id:
                existing_student_match = existing_indexes["by_student_id"].get(normalized_student_id)
                if existing_student_match:
                    reasons.append(
                        f"Duplicate student ID {student_id} with an existing submission in this group: {existing_student_match['reference']}."
                    )

        return reasons

    def _detect_existing_duplicate_match(
        self,
        *,
        filename: str,
        checksum: str,
        student_id: str | None,
        existing_indexes: dict[str, dict[str, dict[str, str | bool]]],
    ) -> dict[str, str | bool | list[str] | None]:
        normalized_filename = filename.strip().casefold()
        normalized_student_id = student_id.strip().casefold() if student_id else None
        reasons: list[str] = []
        matched_submission_id: str | None = None
        matched_is_evaluated = False

        existing_checksum_match = existing_indexes["by_checksum"].get(checksum)
        if existing_checksum_match:
            reasons.append(
                f"Duplicate file content with an existing submission in this group: {existing_checksum_match['reference']}."
            )
            matched_submission_id = str(existing_checksum_match["submission_id"])
            matched_is_evaluated = bool(existing_checksum_match["is_evaluated"])

        existing_filename_match = existing_indexes["by_filename"].get(normalized_filename)
        if existing_filename_match:
            reasons.append(
                f"Duplicate filename with an existing submission in this group: {existing_filename_match['reference']}."
            )
            matched_submission_id = matched_submission_id or str(existing_filename_match["submission_id"])
            matched_is_evaluated = matched_is_evaluated or bool(existing_filename_match["is_evaluated"])

        if normalized_student_id:
            existing_student_match = existing_indexes["by_student_id"].get(normalized_student_id)
            if existing_student_match:
                reasons.append(
                    f"Duplicate student ID {student_id} with an existing submission in this group: {existing_student_match['reference']}."
                )
                matched_submission_id = matched_submission_id or str(existing_student_match["submission_id"])
                matched_is_evaluated = matched_is_evaluated or bool(existing_student_match["is_evaluated"])

        return {
            "reasons": list(dict.fromkeys(reasons)),
            "submission_id": matched_submission_id,
            "is_evaluated": matched_is_evaluated,
        }

    def _extract_duplicate_reasons(self, exc: Exception) -> list[str]:
        details = getattr(exc, "details", None)
        if isinstance(details, dict):
            duplicate_reasons = details.get("duplicate_reasons")
            if isinstance(duplicate_reasons, list):
                return [str(item) for item in duplicate_reasons]
        return []

    def _extract_existing_duplicate_reasons(self, exc: Exception) -> list[str]:
        details = getattr(exc, "details", None)
        if isinstance(details, dict):
            duplicate_reasons = details.get("existing_duplicate_reasons")
            if isinstance(duplicate_reasons, list):
                return [str(item) for item in duplicate_reasons]
        return []

    def _extract_existing_submission_id(self, exc: Exception) -> str | None:
        details = getattr(exc, "details", None)
        if isinstance(details, dict):
            submission_id = details.get("existing_submission_id")
            return str(submission_id) if submission_id else None
        return None

    def _extract_existing_submission_evaluated(self, exc: Exception) -> bool:
        details = getattr(exc, "details", None)
        if isinstance(details, dict):
            return bool(details.get("existing_submission_evaluated"))
        return False
