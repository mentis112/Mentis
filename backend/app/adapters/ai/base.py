import json
from abc import ABC, abstractmethod

from httpx import AsyncClient, Response
from pydantic import BaseModel, Field

from app.models.enums import ProviderName


class CriterionDefinition(BaseModel):
    id: str
    name: str
    weight: float
    description: str | None = None
    is_manual: bool = False


class EvaluationInput(BaseModel):
    provider_name: ProviderName
    model_name: str
    api_key: str
    prompt: str
    submission_text: str
    criteria: list[CriterionDefinition]
    grade_scale: int
    max_tokens_per_request: int | None = None
    response_language: str = "en"


class LimitRiskEstimate(BaseModel):
    blocked: bool = False
    warnings: list[str] = Field(default_factory=list)
    estimated_tokens: int


class NormalizedCriterionScore(BaseModel):
    criterion_name: str
    earned_points: float | None = None
    ai_score: float | None = None
    feedback: str | None = None


class NormalizedProviderResult(BaseModel):
    total_score: float | None = None
    summary_feedback: str | None = None
    criterion_scores: list[NormalizedCriterionScore]
    raw_response: str
    provider_name: ProviderName
    model_name: str
    tokens_input: int | None = None
    tokens_output: int | None = None


class BaseAIProvider(ABC):
    provider_name: ProviderName

    def __init__(self, http_client: AsyncClient | None = None) -> None:
        self.http_client = http_client or AsyncClient(timeout=60)

    @abstractmethod
    async def test_connection(self, *, api_key: str, model_name: str) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    async def evaluate_submission(self, payload: EvaluationInput) -> NormalizedProviderResult:
        raise NotImplementedError

    @abstractmethod
    def estimate_limit_risk(self, payload: EvaluationInput, estimated_tokens: int) -> LimitRiskEstimate:
        raise NotImplementedError

    @abstractmethod
    def validate_provider_config(self, *, api_key: str, model_name: str) -> None:
        raise NotImplementedError

    def _extract_usage_tokens(self, response: dict) -> tuple[int | None, int | None]:
        usage = response.get("usage") or {}
        return usage.get("input_tokens") or usage.get("prompt_tokens"), usage.get(
            "output_tokens"
        ) or usage.get("completion_tokens")

    def _parse_json_payload(self, content: str) -> dict:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)

    def _normalize_result(
        self,
        *,
        parsed_payload: dict,
        raw_response: Response,
        model_name: str,
        provider_name: ProviderName,
    ) -> NormalizedProviderResult:
        response_json = raw_response.json()
        tokens_input, tokens_output = self._extract_usage_tokens(response_json)
        return NormalizedProviderResult(
            total_score=parsed_payload.get("total_score"),
            summary_feedback=parsed_payload.get("summary_feedback"),
            criterion_scores=[
                NormalizedCriterionScore(
                    criterion_name=item.get("criterion_name", ""),
                    earned_points=item.get("earned_points", item.get("points")),
                    ai_score=item.get("ai_score"),
                    feedback=item.get("feedback"),
                )
                for item in parsed_payload.get("criterion_scores", [])
            ],
            raw_response=raw_response.text,
            provider_name=provider_name,
            model_name=model_name,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
        )

    def _extract_provider_error_message(self, response: Response) -> str:
        try:
            payload = response.json()
        except Exception:
            return response.text.strip() or "Unknown provider error"

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if isinstance(error, str) and error:
                return error
            if payload.get("message"):
                return str(payload["message"])

        text = response.text.strip()
        return text or "Unknown provider error"
