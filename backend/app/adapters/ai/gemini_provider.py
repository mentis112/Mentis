from httpx import HTTPError, HTTPStatusError

from app.adapters.ai.base import BaseAIProvider, EvaluationInput, LimitRiskEstimate
from app.core.exceptions import ExternalServiceError, ValidationError
from app.models.enums import ProviderName


class GeminiProvider(BaseAIProvider):
    provider_name = ProviderName.GEMINI
    base_url = "https://generativelanguage.googleapis.com/v1beta"
    default_max_tokens = 1_000_000

    async def test_connection(self, *, api_key: str, model_name: str) -> tuple[bool, str]:
        self.validate_provider_config(api_key=api_key, model_name=model_name)
        try:
            response = await self.http_client.post(
                f"{self.base_url}/models/{model_name}:generateContent",
                params={"key": api_key},
                json={"contents": [{"parts": [{"text": "ping"}]}]},
            )
            response.raise_for_status()
        except HTTPStatusError as exc:
            provider_error = self._extract_provider_error_message(exc.response)
            raise ExternalServiceError(
                f"Gemini connection failed ({exc.response.status_code}): {provider_error}",
                {"status": exc.response.status_code, "provider_error": provider_error},
            ) from exc
        except HTTPError as exc:
            raise ExternalServiceError(f"Gemini connection failed: {exc}") from exc
        return True, "Connection successful"

    async def evaluate_submission(self, payload: EvaluationInput):
        try:
            response = await self.http_client.post(
                f"{self.base_url}/models/{payload.model_name}:generateContent",
                params={"key": payload.api_key},
                json={"contents": [{"parts": [{"text": payload.prompt}]}]},
            )
            response.raise_for_status()
        except HTTPStatusError as exc:
            provider_error = self._extract_provider_error_message(exc.response)
            raise ExternalServiceError(
                f"Gemini evaluation request failed ({exc.response.status_code}): {provider_error}",
                {"status": exc.response.status_code, "provider_error": provider_error},
            ) from exc
        except HTTPError as exc:
            raise ExternalServiceError(f"Gemini evaluation request failed: {exc}") from exc

        response_json = response.json()
        content = None
        for candidate in response_json.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if part.get("text"):
                    content = part["text"]
                    break
            if content:
                break
        if not content:
            raise ValidationError("Gemini response did not contain parsable content")

        parsed = self._parse_json_payload(content)
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
        if estimated_tokens > limit * 0.9 and not blocked:
            warnings.append("Prompt is approaching the Gemini request size limit.")
        if blocked:
            warnings.append("Prompt exceeds the configured Gemini request size limit.")
        return LimitRiskEstimate(blocked=blocked, warnings=warnings, estimated_tokens=estimated_tokens)

    def validate_provider_config(self, *, api_key: str, model_name: str) -> None:
        if not api_key.strip():
            raise ValidationError("Gemini API key is required")
        if not model_name.strip():
            raise ValidationError("Gemini model name is required")
