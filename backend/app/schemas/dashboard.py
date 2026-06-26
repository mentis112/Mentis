from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    total_groups: int
    total_submissions: int
    pending_submissions: int
    completed_submissions: int
    failed_submissions: int
    completed_evaluations: int
    average_adjusted_score: float | None
    evaluations_by_provider: dict[str, int]
    provider_failures_this_month: int
    usage_today: int
    usage_this_month: int
