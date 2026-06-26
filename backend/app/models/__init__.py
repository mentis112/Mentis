from app.models.assignment import AssignmentGroup, EvaluationCriterion
from app.models.base import Base
from app.models.evaluation import CriterionScore, EvaluationResult, ManualAdjustmentHistory
from app.models.instructor import AuthSession, Instructor
from app.models.preferences import AppPreference, AuditLog
from app.models.provider import AIProviderConfig, ProviderUsageLog
from app.models.submission import Submission, SubmissionContentCache, UploadBatch

ai_provider_config = AIProviderConfig
app_preference = AppPreference
assignment_group = AssignmentGroup
audit_log = AuditLog
auth_session = AuthSession
criterion_score = CriterionScore
evaluation_criterion = EvaluationCriterion
evaluation_result = EvaluationResult
instructor = Instructor
manual_adjustment_history = ManualAdjustmentHistory
provider_usage_log = ProviderUsageLog
submission = Submission
submission_content_cache = SubmissionContentCache
upload_batch = UploadBatch

__all__ = [
    "AIProviderConfig",
    "AppPreference",
    "AssignmentGroup",
    "AuditLog",
    "AuthSession",
    "Base",
    "CriterionScore",
    "EvaluationCriterion",
    "EvaluationResult",
    "Instructor",
    "ManualAdjustmentHistory",
    "ProviderUsageLog",
    "Submission",
    "SubmissionContentCache",
    "UploadBatch",
]

