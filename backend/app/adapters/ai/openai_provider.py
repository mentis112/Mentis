from httpx import HTTPError, HTTPStatusError

from app.adapters.ai.base import BaseAIProvider, EvaluationInput, LimitRiskEstimate
from app.core.exceptions import ExternalServiceError, ValidationError
from app.models.enums import ProviderName


class OpenAIProvider(BaseAIProvider):
    provider_name = ProviderName.OPENAI
    base_url = "https://api.openai.com/v1"
    default_max_tokens = 120_000

    async def test_connection(self, *, api_key: str, model_name: str) -> tuple[bool, str]:
        self.validate_provider_config(api_key=api_key, model_name=model_name)
        payload = {
            "model": model_name,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": "ping"}]}],
        }
        try:
            response = await self.http_client.post(
                f"{self.base_url}/responses",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            response.raise_for_status()
        except HTTPStatusError as exc:
            provider_error = self._extract_provider_error_message(exc.response)
            raise ExternalServiceError(
                f"OpenAI connection failed ({exc.response.status_code}): {provider_error}",
                {"status": exc.response.status_code, "provider_error": provider_error},
            ) from exc
        except HTTPError as exc:
            raise ExternalServiceError(f"OpenAI connection failed: {exc}") from exc
        return True, "Connection successful"

    async def evaluate_submission(self, payload: EvaluationInput):
        try:
            response = await self.http_client.post(
                f"{self.base_url}/responses",
                headers={"Authorization": f"Bearer {payload.api_key}"},
                json={
                    "model": payload.model_name,
                    "input": [
                        {
                            "role": "user",
                            "content": [{"type": "input_text", "text": payload.prompt}],
                        }
                    ],
                },
            )
            response.raise_for_status()
        except HTTPStatusError as exc:
            provider_error = self._extract_provider_error_message(exc.response)
            raise ExternalServiceError(
                f"OpenAI evaluation request failed ({exc.response.status_code}): {provider_error}",
                {"status": exc.response.status_code, "provider_error": provider_error},
            ) from exc
        except HTTPError as exc:
            raise ExternalServiceError(f"OpenAI evaluation request failed: {exc}") from exc

        response_json = response.json()
        content = response_json.get("output_text")
        if not content:
            for item in response_json.get("output", []):
                for block in item.get("content", []):
                    if block.get("text"):
                        content = block["text"]
                        break
                if content:
                    break
        if not content:
            raise ValidationError("OpenAI response did not contain parsable content")

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
            warnings.append("Prompt is approaching the OpenAI token limit.")
        if blocked:
            warnings.append("Prompt exceeds the configured OpenAI token limit.")
        return LimitRiskEstimate(blocked=blocked, warnings=warnings, estimated_tokens=estimated_tokens)

    def validate_provider_config(self, *, api_key: str, model_name: str) -> None:
        if not api_key.strip():
            raise ValidationError("OpenAI API key is required")
        if not model_name.strip():
            raise ValidationError("OpenAI model name is required")
