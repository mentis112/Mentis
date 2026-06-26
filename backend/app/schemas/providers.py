from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ProviderName, ProviderUsageStatus
from app.schemas.common import ORMModel


class ProviderConfigCreate(BaseModel):
    provider_name: ProviderName
    api_key: str = Field(default="", max_length=4096)
    model_name: str = Field(min_length=2, max_length=255)
    is_active: bool = True
    is_default: bool = False
    daily_request_limit: int | None = Field(default=None, ge=1, le=1_000_000)
    monthly_request_limit: int | None = Field(default=None, ge=1, le=10_000_000)
    max_files_per_batch: int | None = Field(default=None, ge=1, le=300)
    max_file_size_mb: int | None = Field(default=None, ge=1, le=500)
    max_tokens_per_request: int | None = Field(default=None, ge=256, le=10_000_000)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        trimmed = value.strip()
        if trimmed and len(trimmed) < 8:
            raise ValueError("API key must be at least 8 characters when provided")
        return trimmed


class ProviderConfigUpdate(BaseModel):
    api_key: str | None = Field(default=None, max_length=4096)
    model_name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None
    is_default: bool | None = None
    daily_request_limit: int | None = Field(default=None, ge=1, le=1_000_000)
    monthly_request_limit: int | None = Field(default=None, ge=1, le=10_000_000)
    max_files_per_batch: int | None = Field(default=None, ge=1, le=300)
    max_file_size_mb: int | None = Field(default=None, ge=1, le=500)
    max_tokens_per_request: int | None = Field(default=None, ge=256, le=10_000_000)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if trimmed and len(trimmed) < 8:
            raise ValueError("API key must be at least 8 characters when provided")
        return trimmed


class ProviderConfigResponse(ORMModel):
    id: str
    instructor_id: str
    provider_name: ProviderName
    model_name: str
    is_active: bool
    is_default: bool
    daily_request_limit: int | None
    monthly_request_limit: int | None
    max_files_per_batch: int | None
    max_file_size_mb: int | None
    max_tokens_per_request: int | None
    has_api_key: bool = True
    created_at: datetime
    updated_at: datetime


class ProviderConnectionTestResponse(BaseModel):
    success: bool
    provider_name: ProviderName
    model_name: str
    message: str


class ProviderUsageSummary(ORMModel):
    provider_name: ProviderName
    requests_today: int
    requests_this_month: int
    failures_this_month: int
    blocked_this_month: int
    tokens_input_this_month: int
    tokens_output_this_month: int


class ProviderUsageLogResponse(ORMModel):
    id: str
    provider_name: ProviderName
    request_type: str
    tokens_input: int | None
    tokens_output: int | None
    files_count: int
    estimated_cost: float | None
    status: ProviderUsageStatus
    error_message: str | None
    created_at: datetime
