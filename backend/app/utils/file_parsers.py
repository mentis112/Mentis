from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from docx import Document
from pypdf import PdfReader

from app.core.exceptions import ValidationError


class FileParserService:
    def parse(self, file_path: str) -> str:
        path = Path(file_path)
        extension = path.suffix.lower().lstrip(".")
        return self.parse_bytes(path.read_bytes(), extension)

    async def parse_upload_file(self, upload_file: UploadFile) -> str:
        extension = Path(upload_file.filename or "").suffix.lower().lstrip(".")
        content = await upload_file.read()
        await upload_file.seek(0)
        return self.parse_bytes(content, extension)

    def parse_bytes(self, content: bytes, extension: str) -> str:
        if extension == "txt":
            return content.decode("utf-8", errors="ignore")
        if extension == "pdf":
            return self._parse_pdf_bytes(content)
        if extension == "docx":
            return self._parse_docx_bytes(content)
        raise ValidationError("Unsupported file parser", {"extension": extension})

    def _parse_pdf(self, path: Path) -> str:
        return self._parse_pdf_bytes(path.read_bytes())

    def _parse_pdf_bytes(self, content: bytes) -> str:
        reader = PdfReader(BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()

    def _parse_docx(self, path: Path) -> str:
        return self._parse_docx_bytes(path.read_bytes())

    def _parse_docx_bytes(self, content: bytes) -> str:
        document = Document(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
