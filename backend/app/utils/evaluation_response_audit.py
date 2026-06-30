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

_GENERIC_IMPROVEMENT_PATTERNS = (
    "can be improved",
    "could be improved",
    "could improve",
    "needs improvement",
    "more detail",
    "more details",
    "more detailed",
    "more clarity",
    "clearer",
    "better organized",
    "\u064a\u0645\u0643\u0646 \u062a\u062d\u0633\u064a\u0646",
    "\u0642\u0627\u0628\u0644 \u0644\u0644\u062a\u062d\u0633\u064a\u0646",
    "\u0645\u0632\u064a\u062f \u0645\u0646 \u0627\u0644\u062a\u0641\u0627\u0635\u064a\u0644",
    "\u0645\u0632\u064a\u062f\u0627\u064b \u0645\u0646 \u0627\u0644\u062a\u0641\u0627\u0635\u064a\u0644",
    "\u0623\u0643\u062b\u0631 \u062a\u0641\u0635\u064a\u0644",
    "\u0623\u0643\u062b\u0631 \u0648\u0636\u0648\u062d",
    "\u0628\u0634\u0643\u0644 \u0623\u0648\u0636\u062d",
)

_AUDIT_STATUS_COVERAGE_WEIGHTS = {
    "met": 1.0,
    "partial": 0.6,
    "missing": 0.2,
    "unknown": 0.2,
}

_CONCRETE_DEFICIENCY_PATTERNS = (
    "missing",
    "absent",
    "not provided",
    "not included",
    "not answered",
    "incorrect",
    "wrong",
    "unsupported",
    "incomplete",
    "no evidence",
    "lacks",
    "does not",
    "did not",
    "\u0646\u0627\u0642\u0635",
    "\u063a\u0627\u0626\u0628",
    "\u063a\u064a\u0631 \u0645\u0648\u062c\u0648\u062f",
    "\u0644\u0627 \u064a\u0648\u062c\u062f",
    "\u0644\u0645 \u064a\u062a\u0645",
    "\u0644\u0645 \u064a\u0630\u0643\u0631",
    "\u0644\u0645 \u064a\u062c\u0628",
    "\u063a\u064a\u0631 \u0635\u062d\u064a\u062d",
    "\u062e\u0627\u0637\u0626",
    "\u063a\u064a\u0631 \u0645\u062f\u0639\u0648\u0645",
    "\u063a\u064a\u0631 \u0645\u0643\u062a\u0645\u0644",
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


def remove_generic_improvement_language(feedback: str) -> tuple[str, list[str]]:
    if not feedback.strip():
        return "", []

    kept_parts: list[str] = []
    removed_parts: list[str] = []
    for part in re.split(r"(?<=[.!?؟])\s+|\n+", feedback.strip()):
        cleaned_part = part.strip()
        if not cleaned_part:
            continue

        split_part = re.split(
            r"\s*(?:,|،)?\s*(?:but|however|لكن|ولكن)\s+",
            cleaned_part,
            maxsplit=1,
            flags=re.IGNORECASE,
        )
        if len(split_part) == 2 and _is_generic_improvement_only(split_part[1]):
            prefix = split_part[0].strip()
            if prefix:
                kept_parts.append(prefix)
            removed_parts.append(split_part[1].strip())
            continue

        if _is_generic_improvement_only(cleaned_part):
            removed_parts.append(cleaned_part)
            continue

        kept_parts.append(cleaned_part)

    cleaned_feedback = " ".join(kept_parts).strip()
    return cleaned_feedback, removed_parts


def validate_and_correct_criterion_score(
    *,
    criterion_id: str,
    criterion_name: str,
    max_points: float,
    earned_points: float | None,
    feedback: str,
    audit_items: list[RequirementAuditItem],
    criterion_description: str | None,
) -> tuple[float | None, str, list[RequirementAuditItem], bool, list[str]]:
    issues: list[str] = []
    needs_manual_review = False

    if earned_points is None:
        return earned_points, feedback, audit_items, needs_manual_review, issues

    max_points = max(0.0, float(max_points))

    original_points = float(earned_points)
    earned_points = max(0.0, min(float(earned_points), max_points))
    if earned_points != original_points:
        issues.append(
            f"{criterion_id}: capped earned_points from {_format_points(original_points)} "
            f"to {_format_points(earned_points)}"
        )

    earned_points, feedback = _apply_rule_a_full_marks(
        criterion_id=criterion_id,
        max_points=max_points,
        earned_points=earned_points,
        feedback=feedback,
        audit_items=audit_items,
        issues=issues,
    )

    softened_items: list[RequirementAuditItem] = []
    criterion_text = " ".join(
        part for part in (criterion_name, criterion_description or "") if part
    )
    for item in audit_items:
        if _is_softenable_generic_partial(item, criterion_text):
            issues.append(
                f"{criterion_id}: softened generic partial audit item to met: {item.requirement}"
            )
            softened_items.append(
                RequirementAuditItem(
                    requirement=item.requirement,
                    status="met",
                    evidence=item.evidence,
                    missing_or_weak_reason="",
                )
            )
        else:
            softened_items.append(item)
    audit_items = softened_items

    earned_points, feedback = _apply_rule_a_full_marks(
        criterion_id=criterion_id,
        max_points=max_points,
        earned_points=earned_points,
        feedback=feedback,
        audit_items=audit_items,
        issues=issues,
    )

    earned_points, feedback = _cap_points_by_audit_coverage(
        criterion_id=criterion_id,
        max_points=max_points,
        earned_points=earned_points,
        feedback=feedback,
        audit_items=audit_items,
        issues=issues,
    )

    # Only forgive an unsupported deduction when the provider gave no checklist at all.
    # If any partial/missing audit item still remains after normalization, keep the
    # non-full score instead of silently restoring full marks.
    if (
        0 < earned_points < max_points
        and not audit_items
        and not _has_specific_unmet_audit_item(audit_items, criterion_text)
        and not _contains_concrete_deficiency_text(feedback)
    ):
        issues.append(
            f"{criterion_id}: raised earned_points from {_format_points(earned_points)} "
            "to full marks because the deduction had no specific unmet requirement"
        )
        earned_points = max_points
        feedback = _append_auto_correction(
            feedback,
            "[Auto-corrected: no specific unmet requirement supported the deduction.]",
        )

    if not audit_items and 0 < earned_points < max_points:
        needs_manual_review = True
        issues.append(f"{criterion_id}: marked needs_manual_review because audit is empty")

    return earned_points, feedback, audit_items, needs_manual_review, issues


def _apply_rule_a_full_marks(
    *,
    criterion_id: str,
    max_points: float,
    earned_points: float,
    feedback: str,
    audit_items: list[RequirementAuditItem],
    issues: list[str],
) -> tuple[float, str]:
    all_items_met_with_evidence = audit_items and all(
        item.status == "met"
        and item.evidence.strip()
        and not _contains_absence_language(item.evidence)
        for item in audit_items
    )
    if all_items_met_with_evidence and earned_points < max_points:
        issues.append(
            f"{criterion_id}: raised earned_points from {_format_points(earned_points)} "
            f"to {_format_points(max_points)} because all audit items are met"
        )
        earned_points = max_points
        feedback = _append_auto_correction(
            feedback,
            "[Auto-corrected: all requirements met \u2192 full marks.]",
        )
    return earned_points, feedback


def _cap_points_by_audit_coverage(
    *,
    criterion_id: str,
    max_points: float,
    earned_points: float,
    feedback: str,
    audit_items: list[RequirementAuditItem],
    issues: list[str],
) -> tuple[float, str]:
    if not audit_items:
        return earned_points, feedback

    has_unmet_items = any(item.status in {"partial", "missing", "unknown"} for item in audit_items)
    if not has_unmet_items:
        return earned_points, feedback

    weighted_coverage = sum(
        _AUDIT_STATUS_COVERAGE_WEIGHTS.get(item.status, 0.2) for item in audit_items
    )
    coverage_ratio = max(0.0, min(weighted_coverage / len(audit_items), 1.0))
    capped_points = round(max_points * coverage_ratio, 2)
    if capped_points >= earned_points:
        return earned_points, feedback

    issues.append(
        f"{criterion_id}: reduced earned_points from {_format_points(earned_points)} "
        f"to {_format_points(capped_points)} based on audit coverage ratio {_format_points(coverage_ratio * 100)}%"
    )
    feedback = _append_auto_correction(
        feedback,
        "[Auto-corrected: score aligned to audit coverage.]",
    )
    return capped_points, feedback


def _append_auto_correction(feedback: str, note: str) -> str:
    cleaned = feedback.strip()
    return f"{cleaned} {note}".strip() if cleaned else note


def soften_generic_partial_audit_items(
    audit_items: list[RequirementAuditItem],
) -> list[RequirementAuditItem]:
    softened: list[RequirementAuditItem] = []
    for item in audit_items:
        if _is_generic_improvement_partial(item):
            softened.append(
                RequirementAuditItem(
                    requirement=item.requirement,
                    status="met",
                    evidence=item.evidence,
                    missing_or_weak_reason="",
                )
            )
        else:
            softened.append(item)
    return softened


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
    if score_ratio >= 0.70 and has_missing and not has_met:
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


def should_apply_explicit_evidence_cap(audit_items: list[RequirementAuditItem]) -> bool:
    if not audit_items:
        return True
    return any(item.status in {"partial", "missing", "unknown"} for item in audit_items)


def align_score_with_fully_met_audit(
    *,
    audit_items: list[RequirementAuditItem],
    normalized_score: float | None,
    grade_scale: float,
    is_manual: bool,
) -> tuple[float | None, bool]:
    if is_manual or normalized_score is None or not audit_items or grade_scale <= 0:
        return normalized_score, False

    all_items_met_with_evidence = all(
        item.status == "met" and item.evidence.strip() for item in audit_items
    )
    if not all_items_met_with_evidence or normalized_score >= grade_scale:
        return normalized_score, False

    return float(grade_scale), True


def cap_score_by_audit_consistency(
    *,
    criterion_name: str,
    audit_items: list[RequirementAuditItem],
    normalized_score: float | None,
    grade_scale: float,
    is_manual: bool,
    response_language: str,
) -> tuple[float | None, str | None]:
    if is_manual or normalized_score is None or not audit_items or grade_scale <= 0:
        return normalized_score, None

    has_missing = any(item.status in {"missing", "unknown"} for item in audit_items)
    has_partial = any(item.status == "partial" for item in audit_items)
    has_met = any(item.status == "met" for item in audit_items)
    score_ratio = normalized_score / grade_scale
    cap_ratio: float | None = None

    if score_ratio >= 0.70 and has_missing and not has_met:
        cap_ratio = 0.55
    elif normalized_score >= grade_scale and (has_missing or has_partial):
        cap_ratio = 0.84

    if cap_ratio is None:
        return normalized_score, None

    capped_score = round(min(normalized_score, grade_scale * cap_ratio), 2)
    if capped_score >= normalized_score:
        return normalized_score, None

    if response_language == "ar":
        note = (
            f"تم تخفيض علامة معيار \"{criterion_name}\" لأن قائمة التدقيق في رد المزود "
            "لا تدعم العلامة العالية المعطاة."
        )
    else:
        note = (
            f"The score for \"{criterion_name}\" was capped because the provider's "
            "checklist did not support the high score it returned."
        )
    return capped_score, note


def append_cap_note(feedback: str, cap_note: str | None) -> str:
    if not cap_note:
        return feedback
    return f"{feedback.strip()}\n{cap_note}" if feedback.strip() else cap_note


def normalized_score_to_points(
    *,
    normalized_score: float | None,
    criterion_weight: float,
    grade_scale: float,
) -> float | None:
    if normalized_score is None or grade_scale <= 0:
        return None
    bounded_score = max(0.0, min(float(normalized_score), float(grade_scale)))
    bounded_weight = max(0.0, float(criterion_weight))
    return round((bounded_score / float(grade_scale)) * bounded_weight, 2)


def append_points_breakdown_to_feedback(
    feedback: str,
    *,
    normalized_score: float | None,
    criterion_weight: float,
    grade_scale: float,
    response_language: str,
    is_manual: bool,
) -> str:
    if is_manual or normalized_score is None:
        return feedback

    earned_points = normalized_score_to_points(
        normalized_score=normalized_score,
        criterion_weight=criterion_weight,
        grade_scale=grade_scale,
    )
    if earned_points is None:
        return feedback

    max_points = round(max(0.0, float(criterion_weight)), 2)
    deducted_points = round(max(0.0, max_points - earned_points), 2)
    if response_language == "ar":
        if deducted_points <= 0:
            breakdown = (
                f"النقاط: {_format_points(earned_points)} من {_format_points(max_points)}. "
                "لم يتم الخصم."
            )
        else:
            breakdown = (
                f"النقاط: {_format_points(earned_points)} من {_format_points(max_points)}. "
                f"مقدار الخصم: {_format_points(deducted_points)} من {_format_points(max_points)}."
            )
    elif deducted_points <= 0:
        breakdown = (
            f"Points: {_format_points(earned_points)} out of {_format_points(max_points)}. "
            "No deductions."
        )
    else:
        breakdown = (
            f"Points: {_format_points(earned_points)} out of {_format_points(max_points)}. "
            f"Deducted: {_format_points(deducted_points)} out of {_format_points(max_points)}."
        )

    cleaned_feedback = feedback.strip()
    return f"{breakdown}\n{cleaned_feedback}" if cleaned_feedback else breakdown


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


def _is_generic_improvement_partial(item: RequirementAuditItem) -> bool:
    if item.status != "partial" or not item.evidence.strip():
        return False
    if _contains_absence_language(item.evidence):
        return False

    reason = item.missing_or_weak_reason.strip()
    if not reason:
        return False

    reason_normalized = _normalize_for_search(reason)
    has_generic_improvement = any(
        _normalize_for_search(pattern) in reason_normalized
        for pattern in _GENERIC_IMPROVEMENT_PATTERNS
    )
    has_concrete_deficiency = any(
        _normalize_for_search(pattern) in reason_normalized
        for pattern in _CONCRETE_DEFICIENCY_PATTERNS
    )
    return has_generic_improvement and not has_concrete_deficiency


def _is_generic_improvement_only(text: str) -> bool:
    normalized = _normalize_for_search(text)
    if not normalized:
        return False

    generic_patterns = (
        *_GENERIC_IMPROVEMENT_PATTERNS,
        "could be clearer",
        "needs more detail",
        "lacks depth",
        "\u064a\u0645\u0643\u0646 \u062a\u062d\u0633\u064a\u0646\u0647",
        "\u064a\u0645\u0643\u0646 \u062a\u062d\u0633\u064a\u0646\u0647\u0627",
        "\u0646\u0642\u0627\u0637 \u064a\u0645\u0643\u0646 \u062a\u062d\u0633\u064a\u0646\u0647\u0627",
        "\u064a\u062d\u062a\u0627\u062c \u062a\u0641\u0627\u0635\u064a\u0644 \u0623\u0643\u062b\u0631",
        "\u064a\u0645\u0643\u0646 \u0623\u0646 \u064a\u0643\u0648\u0646 \u0623\u0639\u0645\u0642",
    )
    has_generic_improvement = any(
        _normalize_for_search(pattern) in normalized
        for pattern in generic_patterns
    )
    if not has_generic_improvement:
        return False

    specific_patterns = (
        r"\d",
        r"\bmissing\b",
        r"\bnot found\b",
        r"\brequired\b",
        r"\bonly\s+\d+\b",
        "\u0646\u0627\u0642\u0635",
        "\u0644\u0645 \u064a\u0630\u0643\u0631",
        "\u0637\u064f\u0644\u0628",
        "\u0641\u0642\u0637\\s+\\d+",
    )
    return not any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in specific_patterns)


def _has_specific_unmet_audit_item(
    audit_items: list[RequirementAuditItem],
    criterion_text: str,
) -> bool:
    for item in audit_items:
        if item.status not in {"partial", "missing", "unknown"}:
            continue
        if item.status == "missing":
            return True
        reason = item.missing_or_weak_reason.strip()
        if not reason:
            continue
        if _is_generic_improvement_only(reason):
            continue
        if _contains_concrete_deficiency_text(reason):
            return True
        if re.search(r"\d", reason):
            return True
        reason_normalized = _normalize_for_search(reason)
        for term in extract_explicit_requirement_terms(criterion_text):
            term_normalized = _normalize_for_search(term)
            if term_normalized and term_normalized in reason_normalized:
                return True
    return False


def _contains_concrete_deficiency_text(text: str) -> bool:
    normalized = _normalize_for_search(text)
    if not normalized:
        return False
    if re.search(r"\d", text):
        return True
    return any(
        _normalize_for_search(pattern) in normalized
        for pattern in _CONCRETE_DEFICIENCY_PATTERNS
    )


def _is_softenable_generic_partial(item: RequirementAuditItem, criterion_text: str) -> bool:
    if item.status != "partial":
        return False

    evidence = item.evidence.strip()
    if not evidence or evidence.casefold() == "not found":
        return False
    if _contains_absence_language(evidence):
        return False

    reason = item.missing_or_weak_reason.strip()
    if not reason:
        return False

    reason_normalized = _normalize_for_search(reason)
    generic_patterns = (
        "could be improved",
        "needs more detail",
        "could be clearer",
        "lacks depth",
        "\u064a\u0645\u0643\u0646 \u062a\u062d\u0633\u064a\u0646\u0647",
        "\u064a\u062d\u062a\u0627\u062c \u062a\u0641\u0627\u0635\u064a\u0644 \u0623\u0643\u062b\u0631",
        "\u064a\u0645\u0643\u0646 \u0623\u0646 \u064a\u0643\u0648\u0646 \u0623\u0639\u0645\u0642",
    )
    if not any(_normalize_for_search(pattern) in reason_normalized for pattern in generic_patterns):
        return False

    if re.search(r"\d", reason):
        return False

    specific_patterns = (
        r"\bmissing\b",
        r"\bnot found\b",
        r"\brequired\b",
        r"\bonly\s+\d+\b",
        "\u0646\u0627\u0642\u0635",
        "\u0644\u0645 \u064a\u0630\u0643\u0631",
        "\u0637\u064f\u0644\u0628",
        "\u0641\u0642\u0637\\s+\\d+",
    )
    for pattern in specific_patterns:
        if re.search(pattern, reason_normalized, flags=re.IGNORECASE):
            return False

    for term in extract_explicit_requirement_terms(criterion_text):
        term_normalized = _normalize_for_search(term)
        if term_normalized and term_normalized in reason_normalized:
            return False

    return True


def _looks_like_title_or_metadata(window: str) -> bool:
    return (
        " report " in window
        and (" student id " in window or " campus " in window or " system " in window)
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _format_points(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


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
