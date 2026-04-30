import re

from httpx import HTTPError, HTTPStatusError

from app.adapters.ai.base import BaseAIProvider, EvaluationInput, LimitRiskEstimate
from app.core.exceptions import ExternalServiceError, ValidationError
from app.models.enums import ProviderName
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

        content = self._extract_response_content(response)
        parsed = self._parse_json_payload(content)
        try:
            parsed = self._validate_and_normalize_payload(parsed, payload)
        except ValidationError as exc:
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

        return self._normalize_result(
            parsed_payload=parsed,
            raw_response=response,
            model_name=payload.model_name,
            provider_name=self.provider_name,
        )

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
        if not isinstance(parsed.get("summary_feedback"), str) or not parsed.get("summary_feedback", "").strip():
            raise ValidationError("Groq response must include a non-empty summary_feedback string")

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
            normalized_score = self._coerce_score(item.get("ai_score"))
            if normalized_score is None:
                earned_points = self._coerce_score(item.get("earned_points", item.get("points")))
                if earned_points is not None and criterion.weight > 0:
                    bounded_points = max(0.0, min(float(earned_points), float(criterion.weight)))
                    normalized_score = (bounded_points / float(criterion.weight)) * payload.grade_scale
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
                    "ai_score": round(normalized_score, 2) if normalized_score is not None else None,
                    "feedback": feedback,
                }
            )

        if any(not criterion.is_manual for criterion in payload.criteria) and not has_numeric_score:
            raise ValidationError("Groq response did not include any numeric scores")

        normalized_total = round(weighted_total, 2) if has_numeric_score else None

        normalized = dict(parsed)
        normalized["criterion_scores"] = normalized_scores
        normalized["total_score"] = normalized_total
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
            return float(cleaned)
        raise ValidationError("Groq returned an unsupported score type")

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

    def _build_groq_prompt(self, payload: EvaluationInput, *, max_submission_chars: int) -> str:
        language_label = "Arabic" if payload.response_language == "ar" else "English"
        grading_rules = build_grading_rules(language_label=language_label, grade_scale=payload.grade_scale)
        submission_word_count = len(payload.submission_text.split())
        criteria_lines = "\n".join(
            [
                f'- "{criterion.name}" | weight_percent={criterion.weight:.2f} | manual_only={"yes" if criterion.is_manual else "no"} | teacher_requirement={criterion.description or "No description provided."}'
                for criterion in payload.criteria
            ]
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
- Do not output earned_points.
- Use ai_score only, on the 0 to {payload.grade_scale} scale.
- total_score must exactly equal the weighted total calculated from all criterion ai_score values.
- If the feedback says most requirements are met, do not give a 50% score unless the criterion is only partially met.
- Give 100% for any criterion that fully satisfies its stated requirements.
- Do not give a high score for a criterion if one of its explicit required parts is missing.
- Do give partial credit when some required parts are present. Do not turn a partially met criterion into 0.
- Do not use 0 unless the teacher explicitly says this missing item receives 0, or the whole submission is blank/unrelated.
- If a criterion is completely failed, only that criterion should lose its weighted contribution; the other criteria must still be scored normally.
- Do not give 70%+ for a criterion based on vague mentions. High scores require explicit, usable details.
- Every criterion must have specific feedback tied to the teacher assignment description or criterion.

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
