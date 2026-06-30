import re

from app.models.assignment import AssignmentGroup, EvaluationCriterion
from app.utils.prompt_policy import build_grading_rules


EXPLICIT_PENALTY_PATTERN = re.compile(
    r"[-−]\s*(\d+)(?:\s*(?:درجة|نقطة|points?))?\s+"
    r"(?:إذا|لكل|if|for each|when|عند)\s+(.+?)(?=[.\n،,]|$)",
    flags=re.IGNORECASE,
)


def build_prompt_criterion_id(index: int) -> str:
    return f"cr_{index + 1:02d}"


def parse_explicit_penalties(description: str | None) -> list[tuple[int, str]]:
    if not description:
        return []
    penalties: list[tuple[int, str]] = []
    for match in EXPLICIT_PENALTY_PATTERN.finditer(description):
        condition = re.sub(r"\s+", " ", match.group(2)).strip()
        if condition:
            penalties.append((int(match.group(1)), condition))
    return penalties


def build_criterion_prompt_section(
    *,
    criterion_id: str,
    name: str,
    max_points: float,
    grade_scale: float,
    description: str | None,
    is_manual: bool,
) -> str:
    requirement = description or "No description provided."
    lines = [
        f"Criterion ID : {criterion_id}",
        f"Name         : {name}",
        f"Max points   : {float(max_points):.2f} / {grade_scale}",
        f"Requirements : {requirement}",
        f"Manual only  : {'yes' if is_manual else 'no'}",
    ]
    penalties = parse_explicit_penalties(description)
    if penalties:
        lines.append(
            "EXPLICIT PENALTIES (apply exactly — no other deductions allowed for this criterion):"
        )
        lines.extend(
            f"  - Deduct {points} points when: {condition}"
            for points, condition in penalties
        )
    return "\n".join(lines)


def build_evaluation_prompt(
    *,
    group: AssignmentGroup,
    criteria: list[EvaluationCriterion],
    submission_text: str,
    response_language: str = "en",
) -> str:
    language_label = "Arabic" if response_language == "ar" else "English"
    grading_rules = build_grading_rules(language_label=language_label, grade_scale=group.grade_scale)
    submission_word_count = len(submission_text.split())
    criteria_lines = []
    criterion_ids = [build_prompt_criterion_id(index) for index, _ in enumerate(criteria)]
    for index, criterion in enumerate(criteria):
        criteria_lines.append(
            build_criterion_prompt_section(
                criterion_id=criterion_ids[index],
                name=criterion.name,
                max_points=float(criterion.weight),
                grade_scale=group.grade_scale,
                description=criterion.description,
                is_manual=criterion.is_manual,
            )
        )
    criterion_id_list = ", ".join(f'"{criterion_id}"' for criterion_id in criterion_ids)

    return f"""
You are a neutral, precise academic evaluator. Evaluate only the provided submission against the listed criteria.

Assignment group:
- Name: {group.name}
- Teacher assignment description: {group.description or 'No description provided.'}
- Grade scale: {group.grade_scale}

Scoring requirements:
{grading_rules}

Evaluation method:
- First, read the teacher assignment description.
- Then evaluate the submission against EVERY listed criterion.
- Treat each criterion description as a checklist of required evidence.
- Break each criterion into atomic required items before scoring. Named items, counts, coverage categories, rules, and phrases after "including", "covering", or "with" must be checked separately.
- For count-based requirements, DO NOT collapse the whole count into one vague item. If a criterion asks for 6 functional requirements, 3 non-functional requirements, 5 relationships, 5 test cases, or 6 rules, create separate audit items for the count-bearing parts and for the named coverage items whenever the submission makes them identifiable.
- If the criterion asks for a specific minimum count and the submission provides fewer than required, explicitly say `found X, required Y` in `missing_or_weak_reason`.
- If a criterion asks for named entities, named tables, named rules, named scenarios, or named test categories, create separate audit items for each named item instead of one bundled summary item.
- Never treat "functional requirements", "non-functional requirements", "relationships", "rules", or "test cases" as fully met from a generic heading alone. High scores require itemized usable evidence.
- If a criterion contains explicit deduction rules or numeric penalties such as "-5", "-10", "deduct 5", or "subtract 5", start from the criterion's max points and subtract only the listed penalties that clearly apply.
- If a criterion has EXPLICIT PENALTIES:
  Start from max_points and subtract only the listed penalties that apply.
  Do not invent any additional deductions for this criterion.
- Do not make the score lower than the teacher's explicit deduction schedule justifies. Extra suggestions for improvement are feedback only, not additional deductions.
- Do not deduct points for comments such as "the answer is organized and clear, but it could be improved" unless a concrete explicit requirement is missing, weak, incorrect, or unsupported.
- If all checked items for a criterion are met, give full points for that criterion.
- Use only positive evidence from the submission. A heading, section title, criterion name, or generic sentence is not enough.
- If the submission explicitly says something is missing, not provided, not explained, or will be done later, treat that as evidence of absence.
- Award the full criterion points only when all explicit requirements for that criterion are met.
- If ANY audit item for a criterion is partial or missing, that criterion MUST NOT receive full points.
- Award partial credit for the explicit requirements that are present, even if other parts of the same criterion are missing.
- Do not use all-or-nothing scoring unless the teacher explicitly says the criterion is binary/pass-fail.
- If one criterion completely fails, give 0 for that criterion only and continue scoring the other criteria independently.
- Use 0 for a criterion when the submission has no usable positive evidence for that criterion.
- Keep partial credit calibrated: vague mentions get low partial credit; high scores require explicit, usable details for most required parts.
- Deduct only for missing, weak, incorrect, or unsupported requirements from the assignment description or criteria.
- Do not deduct for spelling, style, formatting, length, or other side issues unless the teacher explicitly included them in the assignment description or criteria.
- RULE F: Return EXACTLY these criterion IDs: {criterion_id_list}.
  Use the exact criterion_id as given. Do not translate or change it.

STEP 2 — FIND EVIDENCE
  For each required item, find the exact text from the submission that
  satisfies it. Quote it directly (or paraphrase closely).
  If nothing in the submission addresses the item, write "Not found".

STEP 3 — COUNT AND COVERAGE CHECKS
  For every count-based requirement, explicitly count what is present.
  Examples:
  - "found 4, required 6 functional requirements"
  - "found 2, required 3 non-functional requirements"
  - "found 3, required 5 relationships"
  - "found 4, required 5 test cases"
  Put this exact gap in `missing_or_weak_reason` whenever the count is short.

STEP 4 — REASONING (required, 1–3 sentences):
Write what the student did and did not do for this criterion.
Reference specific audit items. This reasoning must justify earned_points.

JSON shape:
{{
  "total_score": number | null,
  "summary_feedback": "string",
  "criterion_scores": [
    {{
      "criterion_id": "cr_01",
      "criterion_name": "string",
      "max_points": number,
      "reasoning": "string",
      "earned_points": number | null,
      "deducted_points": number | null,
      "feedback": "string",
      "requirements_audit": [
        {{
          "requirement": "string",
          "status": "met | partial | missing",
          "evidence": "string",
          "missing_or_weak_reason": "string"
        }}
      ],
      "improvement_suggestions": "string"
    }}
  ]
}}

Criteria:
{chr(10).join(criteria_lines)}

Submission size:
- Word count: {submission_word_count}
- Use word count only as context. Do not deduct for length itself; deduct only when the criterion's required evidence is missing or weak.

Submission content:
{submission_text}
""".strip()
