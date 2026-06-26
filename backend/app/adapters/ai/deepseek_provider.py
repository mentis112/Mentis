from httpx import HTTPError, HTTPStatusError

from app.adapters.ai.base import BaseAIProvider, EvaluationInput, LimitRiskEstimate
from app.core.exceptions import ExternalServiceError, ValidationError
from app.models.enums import ProviderName


class DeepSeekProvider(BaseAIProvider):
    provider_name = ProviderName.DEEPSEEK
    base_url = "https://api.deepseek.com"
    default_max_tokens = 64_000

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
                f"DeepSeek connection failed ({exc.response.status_code}): {provider_error}",
                {"status": exc.response.status_code, "provider_error": provider_error},
            ) from exc
        except HTTPError as exc:
            raise ExternalServiceError(f"DeepSeek connection failed: {exc}") from exc
        return True, "Connection successful"

    async def evaluate_submission(self, payload: EvaluationInput):
        try:
            response = await self.http_client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {payload.api_key}"},
                json={
                    "model": payload.model_name,
                    "messages": [{"role": "user", "content": payload.prompt}],
                    "stream": False,
                },
            )
            response.raise_for_status()
        except HTTPStatusError as exc:
            provider_error = self._extract_provider_error_message(exc.response)
            raise ExternalServiceError(
                f"DeepSeek evaluation request failed ({exc.response.status_code}): {provider_error}",
                {"status": exc.response.status_code, "provider_error": provider_error},
            ) from exc
        except HTTPError as exc:
            raise ExternalServiceError(f"DeepSeek evaluation request failed: {exc}") from exc

        response_json = response.json()
        content = None
        for choice in response_json.get("choices", []):
            message = choice.get("message") or {}
            if message.get("content"):
                content = message["content"]
                break
        if not content:
            raise ValidationError("DeepSeek response did not contain parsable content")

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
        if estimated_tokens > limit * 0.85 and not blocked:
            warnings.append("Prompt is approaching the DeepSeek token limit.")
        if blocked:
            warnings.append("Prompt exceeds the configured DeepSeek token limit.")
        return LimitRiskEstimate(blocked=blocked, warnings=warnings, estimated_tokens=estimated_tokens)

    def validate_provider_config(self, *, api_key: str, model_name: str) -> None:
        if not api_key.strip():
            raise ValidationError("DeepSeek API key is required")
        if not model_name.strip():
            raise ValidationError("DeepSeek model name is required")
        if model_name.strip() not in {"deepseek-chat", "deepseek-reasoner"}:
            raise ValidationError(
                "DeepSeek model name must be 'deepseek-chat' or 'deepseek-reasoner'"
            )
