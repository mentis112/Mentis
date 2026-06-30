import json
import re

from httpx import AsyncClient, HTTPError, HTTPStatusError, ReadTimeout

from app.adapters.ai.base import (
    BaseAIProvider,
    EvaluationInput,
    LimitRiskEstimate,
    NormalizedCriterionScore,
    NormalizedProviderResult,
)
from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.models.enums import ProviderName
from app.utils.evaluation_response_audit import (
    append_audit_to_feedback,
    append_cap_note,
    align_score_with_fully_met_audit,
    audit_consistency_errors,
    cap_score_by_audit_consistency,
    cap_score_by_explicit_evidence,
    normalize_requirements_audit,
    should_apply_explicit_evidence_cap,
    soften_generic_partial_audit_items,
)
from app.utils.prompt_policy import build_grading_rules


class OllamaProvider(BaseAIProvider):
    provider_name = ProviderName.OLLAMA
    default_max_tokens = 32_000
    max_attempts = 3
    max_submission_chars = 8_000

    def __init__(self) -> None:
        super().__init__(http_client=AsyncClient(timeout=300))
        self.base_url = get_settings().ollama_base_url.rstrip("/")

    async def test_connection(self, *, api_key: str, model_name: str) -> tuple[bool, str]:
        self.validate_provider_config(api_key=api_key, model_name=model_name)
        try:
            response = await self.http_client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
        except HTTPStatusError as exc:
            provider_error = self._extract_provider_error_message(exc.response)
            raise ExternalServiceError(
                f"Ollama connection failed ({exc.response.status_code}): {provider_error}",
                {"status": exc.response.status_code, "provider_error": provider_error},
            ) from exc
        except HTTPError as exc:
            raise ExternalServiceError(
                f"Ollama connection failed: {exc}. Make sure Ollama is running at {self.base_url}.",
            ) from exc

        response_json = response.json()
        available_models = {
            item.get("model", "").strip() or item.get("name", "").strip()
            for item in response_json.get("models", [])
        }
        matches_model = any(
            available_model == model_name or available_model.startswith(f"{model_name}:")
            for available_model in available_models
        )
        if not matches_model:
            raise ValidationError(
                f"Ollama is reachable, but model '{model_name}' is not available locally. Run `ollama pull {model_name}` first."
            )
        return True, "Connection successful"

    async def evaluate_submission(self, payload: EvaluationInput):
        prompt = self._build_ollama_prompt(payload)
        last_error = "Unknown validation error"

        for attempt in range(1, self.max_attempts + 1):
            response_json, raw_response = await self._request_structured_response(
                model_name=payload.model_name,
                prompt=prompt,
            )
            message = response_json.get("message") or {}
            content = message.get("content")
            if not content:
                last_error = "Ollama response did not contain parsable content"
            else:
                try:
                    parsed = self._salvage_payload(content, payload)
                    normalized_payload = self._validate_and_normalize_payload(parsed, payload)
                    return NormalizedProviderResult(
                        total_score=normalized_payload.get("total_score"),
                        summary_feedback=normalized_payload.get("summary_feedback"),
                        criterion_scores=[
                            NormalizedCriterionScore(
                                criterion_name=item.get("criterion_name", ""),
                                earned_points=item.get("earned_points"),
                                ai_score=item.get("ai_score"),
                                feedback=item.get("feedback"),
                            )
                            for item in normalized_payload.get("criterion_scores", [])
                        ],
                        raw_response=raw_response,
                        provider_name=self.provider_name,
                        model_name=payload.model_name,
                        tokens_input=response_json.get("prompt_eval_count"),
                        tokens_output=response_json.get("eval_count"),
                    )
                except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
                    last_error = str(exc)

            if attempt < self.max_attempts:
                prompt = self._build_retry_prompt(payload, invalid_content=content or raw_response, reason=last_error)

        raise ValidationError(
            f"Ollama returned feedback without numeric scores after {self.max_attempts} attempts. {last_error}",
            {"provider": "ollama"},
        )

    def estimate_limit_risk(self, payload: EvaluationInput, estimated_tokens: int) -> LimitRiskEstimate:
        limit = payload.max_tokens_per_request or self.default_max_tokens
        warnings: list[str] = []
        blocked = estimated_tokens > limit
        if estimated_tokens > limit * 0.85 and not blocked:
            warnings.append("Prompt is approaching the configured Ollama token limit.")
        if blocked:
            warnings.append("Prompt exceeds the configured Ollama token limit.")
        return LimitRiskEstimate(blocked=blocked, warnings=warnings, estimated_tokens=estimated_tokens)

    def validate_provider_config(self, *, api_key: str, model_name: str) -> None:
        if not model_name.strip():
            raise ValidationError("Ollama model name is required")

    async def _request_structured_response(self, *, model_name: str, prompt: str) -> tuple[dict, str]:
        try:
            response = await self.http_client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0, "num_ctx": 8192},
                },
            )
            response.raise_for_status()
        except HTTPStatusError as exc:
            provider_error = self._extract_provider_error_message(exc.response)
            raise ExternalServiceError(
                f"Ollama evaluation request failed ({exc.response.status_code}): {provider_error}",
                {"status": exc.response.status_code, "provider_error": provider_error},
            ) from exc
        except ReadTimeout as exc:
            raise ExternalServiceError(
                "Ollama evaluation timed out. The local model is responding too slowly for the current submission; try again or use a smaller document/model.",
            ) from exc
        except HTTPError as exc:
            raise ExternalServiceError(
                f"Ollama evaluation request failed: {exc}. Make sure Ollama is running at {self.base_url}.",
            ) from exc
        return response.json(), response.text

    def _validate_and_normalize_payload(self, parsed: dict, payload: EvaluationInput) -> dict:
        raw_scores = parsed.get("criterion_scores")
        if not isinstance(raw_scores, list):
            raise ValidationError("Ollama response must contain a criterion_scores array")
        if any(not isinstance(item, dict) for item in raw_scores):
            raise ValidationError("Ollama criterion_scores items must be JSON objects")
        if not isinstance(parsed.get("summary_feedback"), str) or not parsed.get("summary_feedback", "").strip():
            raise ValidationError("Ollama response must include a non-empty summary_feedback string")

        unused_items = list(raw_scores)
        normalized_scores: list[dict] = []
        weighted_total = 0.0
        has_numeric_score = False

        for criterion in payload.criteria:
            match_index = next(
                (
                    index
                    for index, item in enumerate(unused_items)
                    if str(item.get("criterion_name", "")).strip().casefold()
                    == criterion.name.strip().casefold()
                ),
                None,
            )
            if match_index is None:
                raise ValidationError(f"Ollama response omitted criterion: {criterion.name}")

            item = unused_items.pop(match_index)
            earned_points = self._coerce_score(item.get("earned_points", item.get("points")))
            normalized_score = None
            if earned_points is not None and criterion.weight > 0:
                earned_points = max(0.0, min(float(earned_points), float(criterion.weight)))
                normalized_score = (earned_points / float(criterion.weight)) * payload.grade_scale
            if normalized_score is None:
                normalized_score = self._coerce_score(item.get("ai_score"))
            if not criterion.is_manual and normalized_score is None:
                raise ValidationError(f"Ollama response omitted numeric earned_points for criterion: {criterion.name}")
            if normalized_score is not None:
                normalized_score = max(0.0, min(float(normalized_score), float(payload.grade_scale)))

            audit_items = normalize_requirements_audit(
                item.get("requirements_audit")
                or item.get("requirement_audit")
                or item.get("audit")
                or item.get("checklist")
            )
            audit_items = soften_generic_partial_audit_items(audit_items)
            audit_cap_note = None
            if payload.enable_auto_score_adjustment:
                normalized_score, audit_cap_note = cap_score_by_audit_consistency(
                    criterion_name=criterion.name,
                    audit_items=audit_items,
                    normalized_score=normalized_score,
                    grade_scale=float(payload.grade_scale),
                    is_manual=criterion.is_manual,
                    response_language=payload.response_language,
                )
                consistency_errors = audit_consistency_errors(
                    criterion_name=criterion.name,
                    audit_items=audit_items,
                    normalized_score=normalized_score,
                    grade_scale=float(payload.grade_scale),
                    is_manual=criterion.is_manual,
                )
                if consistency_errors:
                    raise ValidationError("; ".join(consistency_errors))
                normalized_score, fully_met_adjusted = align_score_with_fully_met_audit(
                    audit_items=audit_items,
                    normalized_score=normalized_score,
                    grade_scale=float(payload.grade_scale),
                    is_manual=criterion.is_manual,
                )
            else:
                fully_met_adjusted = False

            feedback = (
                self._default_feedback(
                    criterion.name,
                    payload=payload,
                    missing_item=False,
                    normalized_score=normalized_score,
                )
                if fully_met_adjusted
                else self._coerce_feedback(item.get("feedback"))
                or self._default_feedback(
                    criterion.name,
                    payload=payload,
                    missing_item=False,
                    normalized_score=normalized_score,
                )
            )
            feedback = append_audit_to_feedback(
                feedback,
                audit_items,
                response_language=payload.response_language,
            )
            feedback = append_cap_note(feedback, audit_cap_note)
            if payload.enable_auto_score_adjustment and should_apply_explicit_evidence_cap(audit_items):
                normalized_score, cap_note = cap_score_by_explicit_evidence(
                    criterion_description=criterion.description,
                    submission_text=payload.submission_text,
                    normalized_score=normalized_score,
                    grade_scale=float(payload.grade_scale),
                    response_language=payload.response_language,
                )
                feedback = append_cap_note(feedback, cap_note)
            if normalized_score is not None and criterion.weight > 0:
                earned_points = (normalized_score / float(payload.grade_scale)) * float(criterion.weight)

            if normalized_score is not None:
                has_numeric_score = True
                weighted_total += (criterion.weight / payload.grade_scale) * normalized_score

            normalized_scores.append(
                {
                    "criterion_name": criterion.name,
                    "earned_points": round(earned_points, 2) if earned_points is not None else None,
                    "ai_score": round(normalized_score, 2) if normalized_score is not None else None,
                    "feedback": feedback,
                    "requirements_audit": audit_items,
                }
            )

        if unused_items:
            extra_names = [
                str(item.get("criterion_name", "")).strip() or "<missing criterion_name>"
                for item in unused_items
            ]
            raise ValidationError(
                "Ollama response included unrecognized or duplicate criteria: " + ", ".join(extra_names)
            )

        if any(not criterion.is_manual for criterion in payload.criteria) and not has_numeric_score:
            raise ValidationError("Ollama response did not include any numeric scores")

        parsed["criterion_scores"] = normalized_scores
        parsed["total_score"] = round(weighted_total, 2) if has_numeric_score else None
        return parsed

    def _salvage_payload(self, content: str, payload: EvaluationInput) -> dict:
        parsed = self._parse_json_payload(content)
        if isinstance(parsed, dict):
            parsed = self._normalize_payload_shape(parsed, payload)
            if isinstance(parsed.get("criterion_scores"), list):
                return parsed

        extracted_json = self._extract_json_object(content)
        if extracted_json is not None:
            parsed = self._normalize_payload_shape(extracted_json, payload)
            if isinstance(parsed.get("criterion_scores"), list):
                return parsed

        raise ValidationError("Ollama response must contain a criterion_scores array")

    def _normalize_payload_shape(self, parsed: dict, payload: EvaluationInput) -> dict:
        normalized = dict(parsed)
        if not normalized.get("summary_feedback"):
            normalized["summary_feedback"] = (
                normalized.get("feedback")
                or normalized.get("summary")
                or normalized.get("overall_feedback")
                or normalized.get("overall")
            )

        criterion_scores = normalized.get("criterion_scores")
        if isinstance(criterion_scores, list):
            return normalized

        alt_scores = normalized.get("scores") or normalized.get("criteria") or normalized.get("results")
        if isinstance(alt_scores, list):
            normalized["criterion_scores"] = alt_scores
            return normalized

        if isinstance(alt_scores, dict):
            normalized["criterion_scores"] = [
                {
                    "criterion_name": name,
                    "earned_points": value.get("earned_points") if isinstance(value, dict) else None,
                    "ai_score": value.get("ai_score") if isinstance(value, dict) else value,
                    "feedback": value.get("feedback") if isinstance(value, dict) else None,
                    "requirements_audit": (
                        value.get("requirements_audit")
                        or value.get("requirement_audit")
                        or value.get("audit")
                        or value.get("checklist")
                        if isinstance(value, dict)
                        else None
                    ),
                }
                for name, value in alt_scores.items()
            ]
            return normalized

        if all(criterion.name in normalized for criterion in payload.criteria):
            normalized["criterion_scores"] = [
                self._coerce_named_score_item(criterion.name, normalized.get(criterion.name))
                for criterion in payload.criteria
            ]
            return normalized

        return normalized

    def _coerce_named_score_item(self, criterion_name: str, value) -> dict:
        if isinstance(value, dict):
            return {
                "criterion_name": criterion_name,
                "earned_points": value.get("earned_points"),
                "ai_score": value.get("ai_score", value.get("score")),
                "feedback": value.get("feedback"),
                "requirements_audit": (
                    value.get("requirements_audit")
                    or value.get("requirement_audit")
                    or value.get("audit")
                    or value.get("checklist")
                ),
            }
        return {
            "criterion_name": criterion_name,
            "ai_score": value,
            "feedback": None,
        }

    def _extract_json_object(self, content: str) -> dict | None:
        cleaned = content.strip()
        json_candidate = None

        object_match = re.search(r"\{[\s\S]*\}", cleaned)
        if object_match:
            json_candidate = object_match.group(0)
        else:
            array_match = re.search(r"\[[\s\S]*\]", cleaned)
            if array_match:
                json_candidate = array_match.group(0)

        if not json_candidate:
            return None

        try:
            parsed = json.loads(json_candidate)
        except json.JSONDecodeError:
            return None

        if isinstance(parsed, list):
            return {"criterion_scores": parsed}
        if isinstance(parsed, dict):
            return parsed
        return None

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
                raise ValidationError("Ollama returned a non-numeric score value") from exc
        raise ValidationError("Ollama returned an unsupported ai_score type")

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

    def _build_retry_prompt(
        self,
        payload: EvaluationInput,
        *,
        invalid_content: str,
        reason: str,
    ) -> str:
        language_label = "Arabic" if payload.response_language == "ar" else "English"
        grading_rules = build_grading_rules(language_label=language_label, grade_scale=payload.grade_scale)
        submission_word_count = len(payload.submission_text.split())
        criteria_lines = "\n".join(
            [
                f'- criterion_name="{criterion.name}" | manual_only={"yes" if criterion.is_manual else "no"} | max_points={criterion.weight:.2f} | teacher_requirement={criterion.description or "No description provided."}'
                for criterion in payload.criteria
            ]
        )
        submission_excerpt = self._compress_submission_text(payload.submission_text)
        return f"""
Your previous response was invalid.

Reason:
{reason}

You must try again and return JSON only.

Hard requirements:
{grading_rules}
- Do not use null for earned_points on any non-manual criterion.
- Use earned_points for each criterion, on the 0 to max_points scale shown for that criterion.
- Do not put weighted percentages in earned_points.
- summary_feedback must be a non-empty string with 2 to 4 sentences.
- Use the exact key name criterion_scores as an array.
- Use the exact criterion_name values from the Criteria section. Return every listed criterion exactly once.
- Every non-manual criterion must include requirements_audit with concrete evidence for met items.
- If any requirements_audit item is partial or missing, the criterion cannot receive full score.
- Negative statements such as "no real entities", "not provided", or "will be tested later" prove absence, not fulfillment.
- Do not include markdown fences, explanations, or extra text.

Criteria:
{criteria_lines}

Submission size:
- Word count: {submission_word_count}
- Use word count only as context. Do not deduct for length itself; deduct only when the criterion's required evidence is missing or weak.

Submission excerpt:
{submission_excerpt}

Previous invalid response:
{invalid_content[:4000]}

Return JSON only.
""".strip()

    def _build_ollama_prompt(self, payload: EvaluationInput) -> str:
        language_label = "Arabic" if payload.response_language == "ar" else "English"
        grading_rules = build_grading_rules(language_label=language_label, grade_scale=payload.grade_scale)
        submission_word_count = len(payload.submission_text.split())
        criteria_lines = "\n".join(
            [
                f'- criterion_name="{criterion.name}" | max_points={criterion.weight:.2f} | manual_only={"yes" if criterion.is_manual else "no"} | teacher_requirement={criterion.description or "No description provided."}'
                for criterion in payload.criteria
            ]
        )
        submission_excerpt = self._compress_submission_text(payload.submission_text)
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
- Use the exact criterion_name values from the Criteria section. Return every listed criterion exactly once.

JSON shape:
{{
  "total_score": number | null,
  "summary_feedback": "string",
  "criterion_scores": [
    {{
      "criterion_name": "string",
      "earned_points": number | null,
      "deducted_points": number | null,
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
{criteria_lines}

Submission size:
- Word count: {submission_word_count}
- Use word count only as context. Do not deduct for length itself; deduct only when the criterion's required evidence is missing or weak.

Submission excerpt:
{submission_excerpt}
        """.strip()

    def _compress_submission_text(self, text: str) -> str:
        cleaned = text.strip()
        if len(cleaned) <= self.max_submission_chars:
            return cleaned

        head_len = int(self.max_submission_chars * 0.5)
        mid_len = int(self.max_submission_chars * 0.2)
        tail_len = self.max_submission_chars - head_len - mid_len
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
