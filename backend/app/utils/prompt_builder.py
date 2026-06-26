from app.models.assignment import AssignmentGroup, EvaluationCriterion
from app.utils.prompt_policy import build_grading_rules


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
    for criterion in criteria:
        criteria_lines.append(
            "\n".join(
                [
                    f"- Criterion: {criterion.name}",
                    f"  Weight in final grade: {float(criterion.weight):.2f}%",
                    f"  Manual only: {'yes' if criterion.is_manual else 'no'}",
                    f"  Teacher requirement: {criterion.description or 'No description provided.'}",
                ]
            )
        )

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
- Use only positive evidence from the submission. A heading, section title, criterion name, or generic sentence is not enough.
- If the submission explicitly says something is missing, not provided, not explained, or will be done later, treat that as evidence of absence.
- Award the full criterion score only when all explicit requirements for that criterion are met.
- Award partial credit for the explicit requirements that are present, even if other parts of the same criterion are missing.
- Do not use all-or-nothing scoring unless the teacher explicitly says the criterion is binary/pass-fail.
- If one criterion completely fails, deduct only that criterion's weighted contribution and continue scoring the other criteria independently.
- Do not use 0 for an ordinary criterion unless the teacher explicitly says that a missing item receives 0, or the whole submission is blank/unrelated.
- Keep partial credit calibrated: vague mentions get low partial credit; high scores require explicit, usable details for most required parts.
- Deduct only for missing, weak, incorrect, or unsupported requirements from the assignment description or criteria.
- Do not deduct for spelling, style, formatting, length, or other side issues unless the teacher explicitly included them in the assignment description or criteria.

JSON shape:
{{
  "total_score": number | null,
  "summary_feedback": "string",
  "criterion_scores": [
    {{
      "criterion_name": "string",
      "ai_score": number | null,
      "feedback": "string",
      "requirements_audit": [
        {{
          "requirement": "string",
          "status": "met | partial | missing",
          "evidence": "string",
          "missing_or_weak_reason": "string"
        }}
      ]
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
