import json
import re

from httpx import HTTPError, HTTPStatusError

from app.adapters.ai.base import BaseAIProvider, EvaluationInput, LimitRiskEstimate
from app.core.exceptions import ExternalServiceError, ValidationError
from app.models.enums import ProviderName
from app.utils.evaluation_response_audit import (
    append_audit_to_feedback,
    normalize_requirements_audit,
    remove_generic_improvement_language,
    validate_and_correct_criterion_score,
)
from app.utils.prompt_builder import (
    build_criterion_prompt_section,
    build_prompt_criterion_id,
)
from app.utils.prompt_policy import build_grading_rules


class GroqProvider(BaseAIProvider):
    provider_name = ProviderName.GROQ
    base_url = "https://api.groq.com/openai/v1"
    default_max_tokens = 128_000
    max_submission_chars = 12_000

    async def test_connection(self, *, api_key: str, model_name: str) -> tuple[bool, str]:
        self.validate_provider_config(api_key=api_key, model_name=model_name)
        try:
            response = await self.http_client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": False,
                },
            )
            response.raise_for_status()
        except HTTPStatusError as exc:
            provider_error = self._extract_provider_error_message(exc.response)
            raise ExternalServiceError(
                f"Groq connection failed ({exc.response.status_code}): {provider_error}",
                {"status": exc.response.status_code, "provider_error": provider_error},
            ) from exc
        except HTTPError as exc:
            raise ExternalServiceError(f"Groq connection failed: {exc}") from exc
        return True, "Connection successful"

    async def evaluate_submission(self, payload: EvaluationInput):
        reduction_plan = [self.max_submission_chars, 8_000, 4_000]
        last_http_error: tuple[int, str] | None = None
        response = None

        for index, max_chars in enumerate(reduction_plan):
            prompt = self._build_groq_prompt(payload, max_submission_chars=max_chars)
            try:
                response = await self.http_client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {payload.api_key}"},
                    json={
                        "model": payload.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "temperature": 0,
                    },
                )
                response.raise_for_status()
                break
            except HTTPStatusError as exc:
                provider_error = self._extract_provider_error_message(exc.response)
                last_http_error = (exc.response.status_code, provider_error)
                is_payload_too_large = exc.response.status_code == 413
                is_rate_limited = exc.response.status_code == 429
                has_more_attempts = index < len(reduction_plan) - 1
                if is_payload_too_large and has_more_attempts:
                    continue
                if is_payload_too_large:
                    raise ExternalServiceError(
                        "Groq evaluation request is too large for this model/provider. Try a smaller document, a smaller model context, or lower max tokens per request.",
                        {"status": exc.response.status_code, "provider_error": provider_error},
                    ) from exc
                if is_rate_limited:
                    retry_after_seconds = self._extract_retry_after_seconds(exc.response, provider_error)
                    raise ExternalServiceError(
                        "Groq rate limit reached (429).",
                        {
                            "status": exc.response.status_code,
                            "provider_error": provider_error,
                            "retry_after_seconds": retry_after_seconds,
                        },
                    ) from exc
                raise ExternalServiceError(
                    f"Groq evaluation request failed ({exc.response.status_code}): {provider_error}",
                    {"status": exc.response.status_code, "provider_error": provider_error},
                ) from exc
            except HTTPError as exc:
                raise ExternalServiceError(f"Groq evaluation request failed: {exc}") from exc

        if response is None:
            if last_http_error:
                status, provider_error = last_http_error
                raise ExternalServiceError(
                    f"Groq evaluation request failed ({status}): {provider_error}",
                    {"status": status, "provider_error": provider_error},
                )
            raise ExternalServiceError("Groq evaluation request failed before receiving a response")

        content = ""
        try:
            content = self._extract_response_content(response)
            parsed = self._validate_and_normalize_payload(
                self._parse_json_payload(content),
                payload,
            )
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
            retry_prompt = self._build_retry_prompt(
                payload,
                invalid_content=content,
                reason=str(exc),
                max_submission_chars=self.max_submission_chars,
            )
            try:
                response = await self.http_client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {payload.api_key}"},
                    json={
                        "model": payload.model_name,
                        "messages": [{"role": "user", "content": retry_prompt}],
                        "stream": False,
                        "temperature": 0,
                    },
                )
                response.raise_for_status()
            except HTTPStatusError as retry_exc:
                provider_error = self._extract_provider_error_message(retry_exc.response)
                raise ExternalServiceError(
                    f"Groq evaluation retry failed ({retry_exc.response.status_code}): {provider_error}",
                    {"status": retry_exc.response.status_code, "provider_error": provider_error},
                ) from retry_exc
            except HTTPError as retry_exc:
                raise ExternalServiceError(f"Groq evaluation retry failed: {retry_exc}") from retry_exc

            content = self._extract_response_content(response)
            parsed = self._validate_and_normalize_payload(self._parse_json_payload(content), payload)

        normalized = self._normalize_result(
            parsed_payload=parsed,
            raw_response=response,
            model_name=payload.model_name,
            provider_name=self.provider_name,
        )
        normalized.raw_response = json.dumps(parsed, ensure_ascii=False)
        return normalized

    def estimate_limit_risk(self, payload: EvaluationInput, estimated_tokens: int) -> LimitRiskEstimate:
        limit = payload.max_tokens_per_request or self.default_max_tokens
        warnings: list[str] = []
        blocked = estimated_tokens > limit
        if estimated_tokens > limit * 0.85 and not blocked:
            warnings.append("Prompt is approaching the Groq token limit.")
        if blocked:
            warnings.append("Prompt exceeds the configured Groq token limit.")
        return LimitRiskEstimate(blocked=blocked, warnings=warnings, estimated_tokens=estimated_tokens)

    def validate_provider_config(self, *, api_key: str, model_name: str) -> None:
        if not api_key.strip():
            raise ValidationError("Groq API key is required")
        if not model_name.strip():
            raise ValidationError("Groq model name is required")

    def _extract_response_content(self, response) -> str:
        response_json = response.json()
        for choice in response_json.get("choices", []):
            message = choice.get("message") or {}
            if message.get("content"):
                return message["content"]
        raise ValidationError("Groq response did not contain parsable content")

    def _validate_and_normalize_payload(self, parsed: dict, payload: EvaluationInput) -> dict:
        raw_scores = parsed.get("criterion_scores") if isinstance(parsed, dict) else None
        if not isinstance(raw_scores, list):
            raise ValidationError("Groq response must contain a criterion_scores array")
        if any(not isinstance(item, dict) for item in raw_scores):
            raise ValidationError("Groq criterion_scores items must be JSON objects")
        if not isinstance(parsed.get("summary_feedback"), str) or not parsed.get("summary_feedback", "").strip():
            raise ValidationError("Groq response must include a non-empty summary_feedback string")

        unused_items = list(raw_scores)
        normalized_scores: list[dict] = []
        total_score = 0.0
        has_numeric_score = False
        validation_issues: list[str] = []

        for criterion_index, criterion in enumerate(payload.criteria):
            prompt_criterion_id = build_prompt_criterion_id(criterion_index)
            match_index = next(
                (
                    index
                    for index, item in enumerate(unused_items)
                    if str(item.get("criterion_id", "")).strip() == prompt_criterion_id
                ),
                None,
            )
            if match_index is None:
                raise ValidationError(
                    f"Groq response omitted criterion_id {prompt_criterion_id} ({criterion.name})"
                )

            item = unused_items.pop(match_index)
            earned_points = self._coerce_score(item.get("earned_points", item.get("points")))
            if earned_points is None:
                normalized_score_from_ai = self._coerce_score(item.get("ai_score"))
                if normalized_score_from_ai is not None and criterion.weight > 0:
                    bounded_normalized_score = max(
                        0.0,
                        min(float(normalized_score_from_ai), float(payload.grade_scale)),
                    )
                    earned_points = (
                        bounded_normalized_score / float(payload.grade_scale)
                    ) * float(criterion.weight)
            if not criterion.is_manual and earned_points is None:
                raise ValidationError(f"Groq response omitted numeric earned_points for criterion: {criterion.name}")

            audit_items = normalize_requirements_audit(
                item.get("requirements_audit")
                or item.get("requirement_audit")
                or item.get("audit")
                or item.get("checklist")
            )

            feedback = self._coerce_feedback(item.get("feedback")) or ""
            improvement_suggestions = self._coerce_feedback(
                item.get("improvement_suggestions")
            ) or ""
            feedback, moved_improvements = remove_generic_improvement_language(feedback)
            if moved_improvements:
                improvement_suggestions = "\n".join(
                    [part for part in [improvement_suggestions, *moved_improvements] if part]
                )
            (
                earned_points,
                feedback,
                audit_items,
                needs_manual_review,
                criterion_issues,
            ) = validate_and_correct_criterion_score(
                criterion_id=prompt_criterion_id,
                criterion_name=criterion.name,
                max_points=float(criterion.weight),
                earned_points=earned_points,
                feedback=feedback,
                audit_items=audit_items,
                criterion_description=criterion.description,
            )
            validation_issues.extend(criterion_issues)

            normalized_score = None
            if earned_points is not None and criterion.weight > 0:
                normalized_score = (float(earned_points) / float(criterion.weight)) * payload.grade_scale
                normalized_score = max(0.0, min(float(normalized_score), float(payload.grade_scale)))

            if not feedback.strip():
                feedback = self._default_feedback(
                    criterion.name,
                    payload=payload,
                    missing_item=False,
                    normalized_score=normalized_score,
                )

            feedback = append_audit_to_feedback(
                feedback,
                audit_items,
                response_language=payload.response_language,
            )

            rounded_earned_points = round(earned_points, 2) if earned_points is not None else None
            max_points = round(max(0.0, float(criterion.weight)), 2)
            deducted_points = (
                round(max(0.0, max_points - rounded_earned_points), 2)
                if rounded_earned_points is not None
                else None
            )

            if rounded_earned_points is not None:
                has_numeric_score = True
                total_score += rounded_earned_points

            normalized_scores.append(
                {
                    "criterion_id": prompt_criterion_id,
                    "criterion_name": criterion.name,
                    "max_points": max_points,
                    "reasoning": self._coerce_feedback(item.get("reasoning")) or "",
                    "earned_points": rounded_earned_points,
                    "deducted_points": deducted_points,
                    "feedback": feedback,
                    "requirements_audit": [
                        {
                            "requirement": audit_item.requirement,
                            "status": audit_item.status,
                            "evidence": audit_item.evidence,
                            "missing_or_weak_reason": audit_item.missing_or_weak_reason,
                        }
                        for audit_item in audit_items
                    ],
                    "improvement_suggestions": improvement_suggestions,
                    "needs_manual_review": needs_manual_review,
                }
            )

        if unused_items:
            extra_ids = [
                str(item.get("criterion_id", "")).strip()
                or str(item.get("criterion_name", "")).strip()
                or "<missing criterion_id>"
                for item in unused_items
            ]
            raise ValidationError(
                "Groq response included unrecognized or duplicate criteria: " + ", ".join(extra_ids)
            )

        if any(not criterion.is_manual for criterion in payload.criteria) and not has_numeric_score:
            raise ValidationError("Groq response did not include any numeric scores")

        normalized_total = round(total_score, 2) if has_numeric_score else None

        normalized = dict(parsed)
        normalized["criterion_scores"] = normalized_scores
        normalized["total_score"] = normalized_total
        normalized["_validation_issues"] = validation_issues
        return normalized

    def _coerce_score(self, value) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError as exc:
                raise ValidationError("Groq returned a non-numeric score value") from exc
        raise ValidationError("Groq returned an unsupported score type")

    def _coerce_feedback(self, value) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _default_feedback(
        self,
        criterion_name: str,
        *,
        payload: EvaluationInput,
        missing_item: bool,
        normalized_score: float | None,
    ) -> str:
        if payload.response_language == "ar":
            if missing_item:
                return f"لم يرجع المزود نتيجة لهذا المعيار ({criterion_name})، لذلك تم إعطاؤه علامة منخفضة جداً ويحتاج مراجعة."
            if normalized_score is not None and normalized_score >= payload.grade_scale:
                return "تم استيفاء المعيار بالكامل ولم يتم الخصم"
            return "لم يرجع المزود شرحاً كافياً لهذا المعيار، لذلك يجب مراجعة سبب الخصم."
        if missing_item:
            return f"The provider omitted this criterion ({criterion_name}); it received a very low fallback score and needs review."
        if normalized_score is not None and normalized_score >= payload.grade_scale:
            return "Criterion fully met, no deductions"
        return "The provider did not return enough feedback for this criterion; the deduction reason needs review."

    def _build_groq_prompt(self, payload: EvaluationInput, *, max_submission_chars: int) -> str:
        language_label = "Arabic" if payload.response_language == "ar" else "English"
        grading_rules = build_grading_rules(language_label=language_label, grade_scale=payload.grade_scale)
        submission_word_count = len(payload.submission_text.split())
        criterion_ids = [
            build_prompt_criterion_id(index) for index, _ in enumerate(payload.criteria)
        ]
        criterion_id_list = ", ".join(f'"{criterion_id}"' for criterion_id in criterion_ids)
        criteria_lines = "\n\n".join(
            build_criterion_prompt_section(
                criterion_id=criterion_ids[index],
                name=criterion.name,
                max_points=float(criterion.weight),
                grade_scale=payload.grade_scale,
                description=criterion.description,
                is_manual=criterion.is_manual,
            )
            for index, criterion in enumerate(payload.criteria)
        )
        submission_excerpt = self._compress_submission_text(payload.submission_text, max_submission_chars=max_submission_chars)
        return f"""
You are a neutral, precise academic evaluator. Evaluate only the provided submission against the listed criteria.

Assignment:
- Name: {self._extract_assignment_name(payload.prompt)}
- Teacher assignment description: {self._extract_assignment_description(payload.prompt)}
- Grade scale: {payload.grade_scale}

Rules:
{grading_rules}
- summary_feedback must be a non-empty string with 2 to 4 sentences.

Evaluation method:
- Read the teacher assignment description, then evaluate EVERY criterion below.
- Treat each criterion's teacher_requirement as a checklist. A criterion receives full score only if all explicit required parts are present and correct in the submission.
- Break each criterion into atomic required items before scoring. Named items, counts, coverage categories, rules, and phrases after "including", "covering", or "with" must be checked separately.
- If teacher_requirement contains explicit deduction rules or numeric penalties such as "-5", "-10", "deduct 5", or "subtract 5", start from max_points and subtract only the listed penalties that clearly apply.
- If a criterion has EXPLICIT PENALTIES:
  Start from max_points and subtract only the listed penalties that apply.
  Do not invent any additional deductions for this criterion.
- Do not make the score lower than the teacher's explicit deduction schedule justifies. Extra suggestions for improvement are feedback only, not additional deductions.
- Do not deduct points for feedback such as "the answer is organized and clear, but it could be improved" unless you identify a concrete missing, weak, incorrect, or unsupported requirement from the teacher_requirement.
- If every requirements_audit item for a criterion is "met", earned_points must equal max_points and deducted_points must be 0.
- If earned_points is less than max_points, at least one requirements_audit item must be "partial" or "missing"; otherwise the score and feedback are inconsistent.
- Use only positive evidence from the submission. A heading, section title, criterion name, or generic sentence is not enough.
- If the submission explicitly says something is missing, not provided, not explained, or will be done later, treat that as evidence of absence.
- Give proportional partial credit for explicit required parts that are present, even if other parts of the same criterion are missing.
- Do not use all-or-nothing scoring unless the teacher explicitly says the criterion is binary/pass-fail.
- Return earned_points from 0 to that criterion's max_points. Do not return weighted percentages as earned_points.
- If one criterion completely fails, give 0 earned_points for that criterion only and continue scoring the other criteria independently.
- Use 0 earned_points for a criterion when the submission has no usable positive evidence for that criterion.
- Keep partial credit calibrated: vague mentions get low partial credit; high scores require explicit, usable details for most required parts.
- If an explicit requirement is missing, weak, incorrect, or unsupported, deduct proportionally and explain exactly what was missing.
- Do not deduct for spelling, writing style, formatting, length, or presentation unless the teacher explicitly required that in the assignment description or criterion.
- RULE F: Return EXACTLY these criterion IDs: {criterion_id_list}.
  Use the exact criterion_id as given. Do not translate or change it.
- Write improvement suggestions ONLY in the improvement_suggestions field.
- Do NOT include "could be improved", "needs more detail", "lacks depth", or any general improvement language in feedback or requirements_audit.

STEP 2 — FIND EVIDENCE
  For each required item, find the exact text from the submission that
  satisfies it. Quote it directly (or paraphrase closely).
  If nothing in the submission addresses the item, write "Not found".

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
{criteria_lines}

Submission size:
- Word count: {submission_word_count}
- Use word count only as context. Do not deduct for length itself; deduct only when the criterion's required evidence is missing or weak.

Submission excerpt:
{submission_excerpt}
        """.strip()

    def _build_retry_prompt(
        self,
        payload: EvaluationInput,
        *,
        invalid_content: str,
        reason: str,
        max_submission_chars: int,
    ) -> str:
        base_prompt = self._build_groq_prompt(payload, max_submission_chars=max_submission_chars)
        return f"""
Your previous response was invalid.

Reason:
{reason}

Return the evaluation again as JSON only.

Critical corrections:
- Use earned_points for each criterion, on the 0 to max_points scale shown for that criterion.
- Return every listed criterion_id exactly once and do not change IDs like cr_01.
- Do not put weighted percentages in earned_points.
- Include criterion_id, criterion_name, max_points, reasoning, earned_points, deducted_points, feedback, requirements_audit, and improvement_suggestions for each criterion.
- Put reasoning before earned_points in each JSON object.
- total_score may be null because the system recomputes the final total.
- If the feedback says most requirements are met, do not give a 50% score unless the criterion is only partially met.
- Give full earned_points for any criterion that fully satisfies its stated requirements.
- Do not give a high score for a criterion if one of its explicit required parts is missing.
- Do give partial credit when some required parts are present. Do not turn a partially met criterion into 0.
- Use 0 earned_points when the submission has no usable positive evidence for that criterion. This only affects that criterion.
- If a criterion is completely failed, only that criterion should lose its weighted contribution; the other criteria must still be scored normally.
- Do not give 70%+ for a criterion based on vague mentions. High scores require explicit, usable details.
- If the teacher provided explicit deduction rules, do not lower the score below what those listed penalties justify.
- Do not lower a score because an answer could be improved. Lower it only for a concrete missing, weak, incorrect, or unsupported explicit requirement.
- If all audit items are met, give full earned_points for that criterion.
- Every criterion must have specific feedback tied to the teacher assignment description or criterion.
- Every non-manual criterion must include requirements_audit with concrete evidence for met items.
- Missing audit evidence must be "Not found".
- If any requirements_audit item is partial or missing, the criterion cannot receive full score.
- Put improvement suggestions only in improvement_suggestions.
- Negative statements such as "no real entities", "not provided", or "will be tested later" prove absence, not fulfillment.

Original task:
{base_prompt}

Previous invalid response:
{invalid_content[:4000]}

Return JSON only.
""".strip()

    def _compress_submission_text(self, text: str, *, max_submission_chars: int) -> str:
        cleaned = text.strip()
        if len(cleaned) <= max_submission_chars:
            return cleaned

        head_len = int(max_submission_chars * 0.5)
        mid_len = int(max_submission_chars * 0.2)
        tail_len = max_submission_chars - head_len - mid_len
        mid_start = max((len(cleaned) - mid_len) // 2, 0)
        mid_end = mid_start + mid_len
        return "\n...\n".join(
            [
                cleaned[:head_len].strip(),
                cleaned[mid_start:mid_end].strip(),
                cleaned[-tail_len:].strip(),
            ]
        )

    def _extract_assignment_name(self, prompt: str) -> str:
        match = re.search(r"^- Name:\s*(.+)$", prompt, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return "Academic submission"

    def _extract_assignment_description(self, prompt: str) -> str:
        match = re.search(r"^- Teacher assignment description:\s*(.+)$", prompt, re.MULTILINE)
        if match:
            return match.group(1).strip()
        match = re.search(r"^- Description:\s*(.+)$", prompt, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return "No description provided."

    def _extract_retry_after_seconds(self, response, provider_error: str) -> int:
        retry_after_header = response.headers.get("retry-after")
        if retry_after_header:
            try:
                return max(int(float(retry_after_header.strip())), 1)
            except ValueError:
                pass

        match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", provider_error, re.IGNORECASE)
        if not match:
            match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)s", provider_error, re.IGNORECASE)
        if match:
            try:
                return max(int(float(match.group(1))), 1)
            except ValueError:
                return 0
        return 0
