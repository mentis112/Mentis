import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequirementAuditItem:
    requirement: str
    status: str
    evidence: str
    missing_or_weak_reason: str


_COMMON_CAPITALIZED_WORDS = {
    "Defines",
    "Explains",
    "Provides",
    "Write",
    "Evaluate",
    "Criteria",
    "Criterion",
    "Requirement",
    "Requirements",
    "Coverage",
    "Scope",
    "Data",
    "Model",
    "Business",
    "Logic",
    "Testing",
    "Validation",
    "Plan",
    "Report",
    "System",
}

_ABSENCE_PATTERNS = (
    " no ",
    " no real ",
    " not ",
    " without ",
    " missing ",
    " absent ",
    " does not ",
    " do not ",
    " did not ",
    " not provided ",
    " not explain ",
    " will be tested after ",
    " لا يوجد ",
    " غير موجود ",
    " لم يتم ",
    " لا يشرح ",
    " لا يحتوي ",
)


def normalize_requirements_audit(value: Any) -> list[RequirementAuditItem]:
    if not isinstance(value, list):
        return []

    audit_items: list[RequirementAuditItem] = []
    for raw_item in value:
        if not isinstance(raw_item, dict):
            continue
        requirement = _clean_text(
            raw_item.get("requirement")
            or raw_item.get("required_item")
            or raw_item.get("criterion_requirement")
            or raw_item.get("item")
        )
        status = _normalize_status(raw_item.get("status") or raw_item.get("result"))
        evidence = _clean_text(
            raw_item.get("evidence")
            or raw_item.get("submission_evidence")
            or raw_item.get("quote")
            or raw_item.get("proof")
        )
        reason = _clean_text(
            raw_item.get("missing_or_weak_reason")
            or raw_item.get("reason")
            or raw_item.get("deduction_reason")
            or raw_item.get("comment")
        )
        if requirement or evidence or reason:
            audit_items.append(
                RequirementAuditItem(
                    requirement=requirement or "Unspecified requirement",
                    status=status,
                    evidence=evidence,
                    missing_or_weak_reason=reason,
                )
            )
    return audit_items


def audit_consistency_errors(
    *,
    criterion_name: str,
    audit_items: list[RequirementAuditItem],
    normalized_score: float | None,
    grade_scale: float,
    is_manual: bool,
) -> list[str]:
    if is_manual:
        return []

    if normalized_score is None:
        return [f"{criterion_name}: non-manual criterion is missing ai_score"]

    if not audit_items:
        return [f"{criterion_name}: missing requirements_audit checklist"]

    score_ratio = normalized_score / grade_scale if grade_scale else 0.0
    has_missing = any(item.status in {"missing", "unknown"} for item in audit_items)
    has_partial = any(item.status == "partial" for item in audit_items)
    has_met = any(item.status == "met" for item in audit_items)

    errors: list[str] = []
    if normalized_score >= grade_scale and (has_missing or has_partial):
        errors.append(
            f"{criterion_name}: full score conflicts with partial or missing audit items"
        )
    if score_ratio >= 0.85 and has_missing:
        errors.append(
            f"{criterion_name}: high score conflicts with missing required audit items"
        )
    if score_ratio >= 0.70 and not has_met:
        errors.append(
            f"{criterion_name}: high score has no audit item marked as met"
        )

    for item in audit_items:
        if item.status == "met" and not item.evidence.strip() and score_ratio >= 0.70:
            errors.append(
                f"{criterion_name}: met audit item lacks submission evidence: {item.requirement}"
            )
        if item.status == "met" and _contains_absence_language(item.evidence):
            errors.append(
                f"{criterion_name}: audit marks an absence statement as met evidence: {item.requirement}"
            )

    return errors


def append_audit_to_feedback(
    feedback: str,
    audit_items: list[RequirementAuditItem],
    *,
    response_language: str,
    max_items: int = 8,
) -> str:
    if not audit_items:
        return feedback

    is_arabic = response_language == "ar"
    status_labels = (
        {"met": "متحقق", "partial": "جزئي", "missing": "ناقص", "unknown": "غير واضح"}
        if is_arabic
        else {"met": "met", "partial": "partial", "missing": "missing", "unknown": "unknown"}
    )
    heading = "تفصيل البنود:" if is_arabic else "Requirement audit:"
    lines = [feedback.strip(), heading] if feedback.strip() else [heading]
    for item in audit_items[:max_items]:
        status = status_labels.get(item.status, item.status)
        if is_arabic:
            detail = f"- {item.requirement}: {status}"
            if item.evidence:
                detail += f"؛ الدليل: {item.evidence}"
            if item.missing_or_weak_reason:
                detail += f"؛ السبب: {item.missing_or_weak_reason}"
        else:
            detail = f"- {item.requirement}: {status}"
            if item.evidence:
                detail += f"; evidence: {item.evidence}"
            if item.missing_or_weak_reason:
                detail += f"; reason: {item.missing_or_weak_reason}"
        lines.append(detail)

    if len(audit_items) > max_items:
        lines.append("..." if not is_arabic else "...")
    return "\n".join(lines)


def cap_score_by_explicit_evidence(
    *,
    criterion_description: str | None,
    submission_text: str,
    normalized_score: float | None,
    grade_scale: float,
    response_language: str,
) -> tuple[float | None, str | None]:
    if normalized_score is None or not criterion_description:
        return normalized_score, None

    terms = extract_explicit_requirement_terms(criterion_description)
    if len(terms) < 2:
        return normalized_score, None

    present_terms = [
        term for term in terms if _term_has_positive_evidence(term, submission_text)
    ]
    coverage_ratio = len(present_terms) / len(terms)
    score_ratio = normalized_score / grade_scale if grade_scale else 0.0

    if coverage_ratio >= 0.95:
        return normalized_score, None

    cap_ratio: float | None = None
    if coverage_ratio == 0 and score_ratio > 0.05:
        cap_ratio = 0.05
    elif coverage_ratio < 0.25 and score_ratio > 0.25:
        cap_ratio = 0.25
    elif coverage_ratio < 0.50 and score_ratio > 0.55:
        cap_ratio = 0.55

    if cap_ratio is None:
        return normalized_score, None

    capped_score = round(max(0.0, min(normalized_score, grade_scale * cap_ratio)), 2)
    missing_terms = [term for term in terms if term not in present_terms]
    if response_language == "ar":
        note = (
            "تم تخفيض علامة هذا المعيار آلياً لأن بنوداً صريحة في المعيار لم يظهر لها "
            f"دليل إيجابي واضح داخل الملف: {', '.join(missing_terms[:6])}."
        )
    else:
        note = (
            "This criterion score was capped because explicit required items did not have "
            f"clear positive evidence in the submission: {', '.join(missing_terms[:6])}."
        )
    return capped_score, note


def append_cap_note(feedback: str, cap_note: str | None) -> str:
    if not cap_note:
        return feedback
    return f"{feedback.strip()}\n{cap_note}" if feedback.strip() else cap_note


def extract_explicit_requirement_terms(description: str) -> list[str]:
    terms: list[str] = []

    for token in re.findall(r"\b[A-Z][A-Za-z0-9]{2,}\b", description):
        if token not in _COMMON_CAPITALIZED_WORDS:
            terms.append(token)

    for match in re.finditer(
        r"(?:at least|minimum of)?\s*\d+\s+([^,.;]+?)(?=\s+(?:and|with|covering)|[,.;]|$)",
        description,
        flags=re.IGNORECASE,
    ):
        cleaned = _normalize_requirement_term(match.group(1))
        if cleaned:
            terms.append(cleaned)

    for marker in ("including", "covering", "with"):
        for segment in _segments_after_marker(description, marker):
            for part in _split_requirement_segment(segment):
                cleaned = _normalize_requirement_term(part)
                if cleaned and cleaned.lower() not in {"the", "and", "or"}:
                    terms.append(cleaned)

    return _dedupe_preserving_order(terms)


def _segments_after_marker(text: str, marker: str) -> list[str]:
    pattern = re.compile(rf"\b{re.escape(marker)}\b\s+([^.;:]+)", re.IGNORECASE)
    return [match.group(1) for match in pattern.finditer(text)]


def _split_requirement_segment(segment: str) -> list[str]:
    normalized = re.sub(r"\band\b|\bor\b", ",", segment, flags=re.IGNORECASE)
    return [part.strip() for part in normalized.split(",")]


def _normalize_requirement_term(term: str) -> str:
    cleaned = re.sub(r"\s+", " ", term.strip(" .;:-"))
    cleaned = re.sub(
        r"^(at least|clear|measurable|main|including|covering|with)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^\d+\s+", "", cleaned)
    cleaned = re.sub(r"^(clear|measurable)\s+", "", cleaned, flags=re.IGNORECASE)
    if re.match(r"^the\s+main\s+entities/tables\b", cleaned, flags=re.IGNORECASE):
        return ""
    if len(cleaned) < 3:
        return ""
    if len(cleaned.split()) > 5:
        return ""
    return cleaned


def _term_has_positive_evidence(term: str, text: str) -> bool:
    variants = _term_variants(term)
    text_lower = f" {_normalize_for_search(text)} "
    for variant in variants:
        variant_lower = _normalize_for_search(variant)
        if not variant_lower:
            continue
        for match in re.finditer(re.escape(variant_lower), text_lower):
            window = text_lower[max(match.start() - 80, 0) : match.end() + 80]
            if _looks_like_title_or_metadata(window):
                continue
            if not _contains_absence_language(window):
                return True
    return False


def _term_variants(term: str) -> set[str]:
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", term)
    variants = {term, spaced}
    if "/" in term:
        variants.update(part.strip() for part in term.split("/") if part.strip())
    for variant in list(variants):
        words = variant.split()
        if words:
            singular_words = [word[:-1] if word.lower().endswith("s") else word for word in words]
            variants.add(" ".join(singular_words))
    return variants


def _normalize_for_search(text: str) -> str:
    lowered = text.casefold()
    lowered = re.sub(r"[^0-9a-z\u0600-\u06ff/]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _normalize_status(value: Any) -> str:
    status = str(value or "").strip().casefold()
    if not status:
        return "unknown"
    if any(token in status for token in ("missing", "unmet", "absent", "not met", "no evidence", "ناقص")):
        return "missing"
    if any(token in status for token in ("partial", "partially", "weak", "جزئي")):
        return "partial"
    if any(token in status for token in ("met", "satisfied", "complete", "present", "متحقق", "مكتمل")):
        return "met"
    return "unknown"


def _contains_absence_language(text: str) -> bool:
    normalized = f" {_normalize_for_search(text)} "
    return any(pattern in normalized for pattern in _ABSENCE_PATTERNS)


def _looks_like_title_or_metadata(window: str) -> bool:
    return (
        " report " in window
        and (" student id " in window or " campus " in window or " system " in window)
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped
