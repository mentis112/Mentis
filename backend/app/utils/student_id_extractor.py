import re


ARABIC_NUMERAL_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)

LABELED_PATTERNS = [
    re.compile(r"(?im)(?:رقم\s*الطالب|الرقم\s*الجامعي)\s*[:：\-#]?\s*(\d{4,20})"),
    re.compile(r"(?im)(?:student\s*id|student\s*number)\s*[:：\-#]?\s*(\d{4,20})"),
    re.compile(r"(?im)(\d{4,20})\s*(?:رقم\s*الطالب|الرقم\s*الجامعي)"),
    re.compile(r"(?im)(\d{4,20})\s*(?:student\s*id|student\s*number)"),
]

FALLBACK_PATTERNS = [
    re.compile(r"(?m)^\s*(\d{6,20})\s*$"),
]


def extract_student_id(text: str | None) -> str | None:
    if not text:
        return None

    normalized_text = text.translate(ARABIC_NUMERAL_TRANSLATION)

    for pattern in LABELED_PATTERNS:
        match = pattern.search(normalized_text)
        if match:
            return match.group(1).strip()

    top_lines = "\n".join(normalized_text.splitlines()[:12])
    for pattern in FALLBACK_PATTERNS:
        match = pattern.search(top_lines)
        if match:
            return match.group(1).strip()

    return None


def extract_student_id_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    normalized_name = filename.translate(ARABIC_NUMERAL_TRANSLATION)
    match = re.search(r"(?<!\d)(\d{6,20})(?!\d)", normalized_name)
    if match:
        return match.group(1).strip()
    return None
