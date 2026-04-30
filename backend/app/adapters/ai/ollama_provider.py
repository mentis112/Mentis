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
                item = {}
                missing_item = True
            else:
                item = unused_items.pop(match_index)
                missing_item = False
            earned_points = self._coerce_score(item.get("earned_points", item.get("points")))
            normalized_score = self._coerce_score(item.get("ai_score"))
            if normalized_score is None and earned_points is not None and criterion.weight > 0:
                earned_points = max(0.0, min(float(earned_points), float(criterion.weight)))
                normalized_score = (earned_points / float(criterion.weight)) * payload.grade_scale
            if not criterion.is_manual and normalized_score is None:
                normalized_score = self._minimum_unscored_value(payload)
            if normalized_score is not None:
                normalized_score = max(0.0, min(float(normalized_score), float(payload.grade_scale)))

            if normalized_score is not None:
                has_numeric_score = True
                weighted_total += (criterion.weight / 100.0) * normalized_score

            feedback = self._coerce_feedback(item.get("feedback")) or self._default_feedback(
                criterion.name,
                payload=payload,
                missing_item=missing_item,
                normalized_score=normalized_score,
            )

            normalized_scores.append(
                {
                    "criterion_name": criterion.name,
                    "earned_points": earned_points,
                    "ai_score": normalized_score,
                    "feedback": feedback,
                }
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
            return float(cleaned)
        raise ValidationError("Ollama returned an unsupported ai_score type")

    def _coerce_feedback(self, value) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _minimum_unscored_value(self, payload: EvaluationInput) -> float:
        return round(max(float(payload.grade_scale) * 0.01, 0.01), 2)

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
                f'- "{criterion.name}" | manual_only={"yes" if criterion.is_manual else "no"} | weight_percent={criterion.weight:.2f} | teacher_requirement={criterion.description or "No description provided."}'
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
- Do not use null for any non-manual criterion.
- summary_feedback must be a non-empty string with 2 to 4 sentences.
- Use the exact key name criterion_scores as an array.
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
                f'- "{criterion.name}" | weight_percent={criterion.weight:.2f} | manual_only={"yes" if criterion.is_manual else "no"} | teacher_requirement={criterion.description or "No description provided."}'
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
- Give proportional partial credit for explicit required parts that are present, even if other parts of the same criterion are missing.
- Do not use all-or-nothing scoring unless the teacher explicitly says the criterion is binary/pass-fail.
- If one criterion completely fails, deduct only that criterion's weighted contribution and continue scoring the other criteria independently.
- Do not use 0 for an ordinary criterion unless the teacher explicitly says that a missing item receives 0, or the whole submission is blank/unrelated.
- Keep partial credit calibrated: vague mentions get low partial credit; high scores require explicit, usable details for most required parts.
- If an explicit requirement is missing, weak, incorrect, or unsupported, deduct proportionally and explain exactly what was missing.
- Do not deduct for spelling, writing style, formatting, length, or presentation unless the teacher explicitly required that in the assignment description or criterion.

JSON shape:
{{
  "total_score": number | null,
  "summary_feedback": "string",
  "criterion_scores": [
    {{
      "criterion_name": "string",
      "ai_score": number | null,
      "feedback": "string"
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
