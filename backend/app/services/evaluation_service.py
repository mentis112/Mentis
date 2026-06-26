from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ai.base import CriterionDefinition, EvaluationInput
from app.adapters.ai.factory import ProviderAdapterFactory
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import decrypt_secret
from app.models.enums import ProviderName, ProviderRequestType, ProviderUsageStatus, SubmissionStatus
from app.models.evaluation import CriterionScore, EvaluationResult, ManualAdjustmentHistory
from app.models.provider import ProviderUsageLog
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.submission_repository import SubmissionRepository
from app.schemas.evaluations import EvaluateSubmissionRequest, ManualAdjustmentRequest
from app.services.audit_service import AuditService
from app.services.evaluation_batch_runner import EvaluationBatchRunner
from app.services.group_service import GroupService
from app.services.provider_service import ProviderService
from app.services.usage_limit_service import UsageLimitService
from app.utils.prompt_builder import build_evaluation_prompt
from app.utils.token_estimator import estimate_tokens


class EvaluationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.submission_repository = SubmissionRepository(session)
        self.evaluation_repository = EvaluationRepository(session)
        self.provider_service = ProviderService(session)
        self.group_service = GroupService(session)
        self.usage_limit_service = UsageLimitService(session)
        self.audit_service = AuditService(session)

    async def evaluate_submission(
        self,
        *,
        instructor_id: str,
        submission_id: str,
        payload: EvaluateSubmissionRequest,
        response_language: str = "en",
        request_type: ProviderRequestType = ProviderRequestType.EVALUATION,
    ) -> EvaluationResult:
        submission = await self.submission_repository.get_by_id_for_instructor(submission_id, instructor_id)
        if not submission:
            raise NotFoundError("Submission not found")
        if not submission.student_id or not submission.student_id.strip():
            raise ValidationError("Submission must have a student ID before evaluation")
        if not submission.content_cache or submission.content_cache.parser_status.value != "success":
            raise ValidationError("Submission content is not ready for evaluation")

        group = submission.group
        self.group_service.ensure_group_ready_for_evaluation(group)
        provider_config = await self.provider_service.resolve_config(
            instructor_id,
            provider_config_id=payload.provider_config_id,
            provider_name=payload.provider_name,
        )

        prompt = build_evaluation_prompt(
            group=group,
            criteria=list(group.criteria),
            submission_text=submission.content_cache.extracted_text or "",
            response_language=response_language,
        )
        estimated_tokens = estimate_tokens(prompt, submission.content_cache.extracted_text or "")
        adapter = ProviderAdapterFactory.create(provider_config.provider_name)
        adapter_risk = adapter.estimate_limit_risk(
            EvaluationInput(
                provider_name=provider_config.provider_name,
                model_name=provider_config.model_name,
                api_key="***",
                prompt=prompt,
                submission_text=submission.content_cache.extracted_text or "",
                criteria=[
                    CriterionDefinition(
                        id=criterion.id,
                        name=criterion.name,
                        weight=float(criterion.weight),
                        description=criterion.description,
                        is_manual=criterion.is_manual,
                    )
                    for criterion in group.criteria
                ],
                grade_scale=group.grade_scale,
                max_tokens_per_request=provider_config.max_tokens_per_request,
                response_language=response_language,
            ),
            estimated_tokens,
        )
        await self.usage_limit_service.enforce_evaluation_limits(
            instructor_id=instructor_id,
            provider_config=provider_config,
            estimated_tokens=estimated_tokens,
            files_count=1,
            file_size_mb=(len(submission.content_cache.extracted_text or "") / (1024 * 1024)),
        )
        if adapter_risk.blocked:
            raise ValidationError("Prompt exceeds provider limits", {"warnings": adapter_risk.warnings})

        evaluation_input = EvaluationInput(
            provider_name=provider_config.provider_name,
            model_name=provider_config.model_name,
            api_key=decrypt_secret(provider_config.encrypted_api_key),
            prompt=prompt,
            submission_text=submission.content_cache.extracted_text or "",
            criteria=[
                CriterionDefinition(
                    id=criterion.id,
                    name=criterion.name,
                    weight=float(criterion.weight),
                    description=criterion.description,
                    is_manual=criterion.is_manual,
                )
                for criterion in group.criteria
            ],
            grade_scale=group.grade_scale,
            max_tokens_per_request=provider_config.max_tokens_per_request,
            response_language=response_language,
        )

        submission.status = SubmissionStatus.PROCESSING
        submission.error_message = None
        submission.processed_at = None
        await self.submission_repository.save_submission(submission)
        try:
            normalized = await adapter.evaluate_submission(evaluation_input)
            await self.evaluation_repository.clear_latest_flags(submission.id)
            evaluation_number = await self.evaluation_repository.next_evaluation_number(submission.id)
            evaluation_result = await self.evaluation_repository.create_result(
                EvaluationResult(
                    submission_id=submission.id,
                    provider_config_id=provider_config.id,
                    provider_name=provider_config.provider_name,
                    model_name=provider_config.model_name,
                    evaluation_number=evaluation_number,
                    is_latest=True,
                    total_ai_score=0,
                    final_adjusted_score=0,
                    ai_feedback=normalized.summary_feedback,
                    raw_ai_response=normalized.raw_response,
                )
            )

            normalized_by_name = {
                item.criterion_name.strip().casefold(): item for item in normalized.criterion_scores
            }
            criteria_by_order = list(group.criteria)
            created_scores: list[CriterionScore] = []
            order_fallback = iter(normalized.criterion_scores)
            for criterion in criteria_by_order:
                item = normalized_by_name.get(criterion.name.strip().casefold())
                if item is None:
                    item = next(order_fallback, None)
                ai_score = self._normalize_provider_score(
                    score=None if item is None else item.ai_score,
                    earned_points=None if item is None else item.earned_points,
                    criterion_weight=float(criterion.weight),
                    grade_scale=group.grade_scale,
                    is_manual=criterion.is_manual,
                )
                feedback = self._normalize_feedback_for_score(
                    feedback=None if item is None else item.feedback,
                    ai_score=ai_score,
                    grade_scale=group.grade_scale,
                    is_manual=criterion.is_manual,
                    response_language=response_language,
                    missing_provider_item=item is None,
                )
                created_score = await self.evaluation_repository.create_criterion_score(
                    CriterionScore(
                        result_id=evaluation_result.id,
                        criterion_id=criterion.id,
                        ai_score=ai_score,
                        manual_score=None,
                        feedback=feedback,
                    )
                )
                created_scores.append(created_score)

            evaluation_result.total_ai_score = self._calculate_total_ai_score(
                evaluation_result,
                score_items=created_scores,
            )
            evaluation_result.final_adjusted_score = self._calculate_final_adjusted_score(
                evaluation_result,
                score_items=created_scores,
            )
            await self.evaluation_repository.save_result(evaluation_result)

            submission.status = SubmissionStatus.COMPLETED
            submission.error_message = None
            submission.processed_at = datetime.now(timezone.utc)
            await self.submission_repository.save_submission(submission)
            await self.submission_repository.mark_processed(submission)

            await self._log_usage(
                instructor_id=instructor_id,
                provider_config_id=provider_config.id,
                provider_name=provider_config.provider_name,
                submission_id=submission.id,
                evaluation_result_id=evaluation_result.id,
                request_type=request_type,
                status=ProviderUsageStatus.SUCCESS,
                tokens_input=normalized.tokens_input or estimated_tokens,
                tokens_output=normalized.tokens_output,
            )
            await self.audit_service.log(
                instructor_id=instructor_id,
                action="evaluation.completed",
                entity_type="evaluation_result",
                entity_id=evaluation_result.id,
                metadata_json={"provider_name": provider_config.provider_name.value},
            )
            await self.session.commit()
            return await self.evaluation_repository.get_by_id_for_instructor(
                evaluation_result.id,
                instructor_id,
            )
        except Exception as exc:
            submission.status = SubmissionStatus.FAILED
            submission.error_message = str(exc)
            await self.submission_repository.save_submission(submission)
            await self._log_usage(
                instructor_id=instructor_id,
                provider_config_id=provider_config.id,
                provider_name=provider_config.provider_name,
                submission_id=submission.id,
                evaluation_result_id=None,
                request_type=request_type,
                status=ProviderUsageStatus.FAILED,
                error_message=str(exc),
                tokens_input=estimated_tokens,
                tokens_output=None,
            )
            await self.session.commit()
            raise

    @staticmethod
    def normalize_response_language(accept_language: str | None) -> str:
        if not accept_language:
            return "en"
        normalized = accept_language.strip().lower()
        if normalized.startswith("ar"):
            return "ar"
        return "en"

    async def list_for_submission(self, instructor_id: str, submission_id: str):
        return await self.evaluation_repository.list_for_submission(submission_id, instructor_id)

    async def list_for_instructor(self, instructor_id: str):
        return await self.evaluation_repository.list_for_instructor(instructor_id)

    async def get_by_id(self, instructor_id: str, evaluation_id: str):
        evaluation = await self.evaluation_repository.get_by_id_for_instructor(evaluation_id, instructor_id)
        if not evaluation:
            raise NotFoundError("Evaluation result not found")
        return evaluation

    async def start_batch_evaluations(
        self,
        *,
        instructor_id: str,
        submission_ids: list[str],
        response_language: str,
    ) -> tuple[int, bool]:
        unique_ids = [item for item in dict.fromkeys(submission_ids) if item]
        if not unique_ids:
            raise ValidationError("At least one submission is required")

        provider_config = await self.provider_service.resolve_config(instructor_id)

        queued_submissions = []
        for submission_id in unique_ids:
            submission = await self.submission_repository.get_by_id_for_instructor(submission_id, instructor_id)
            if not submission:
                continue
            if not submission.student_id or not submission.student_id.strip():
                continue
            if submission.status not in {
                SubmissionStatus.PENDING,
                SubmissionStatus.FAILED,
                SubmissionStatus.QUEUED,
            }:
                continue
            if not submission.content_cache or submission.content_cache.parser_status.value != "success":
                continue
            try:
                self.group_service.ensure_group_ready_for_evaluation(submission.group)
            except ValidationError:
                continue
            queued_submissions.append(submission)

        if not queued_submissions:
            raise ValidationError("No evaluatable submissions were found")

        settings = get_settings()
        retry_delays = [
            settings.batch_rate_limit_retry_base_seconds * (2**index)
            for index in range(settings.batch_rate_limit_retry_attempts)
        ]
        max_parallel = settings.batch_max_parallel_evaluations
        if provider_config.provider_name == ProviderName.GROQ:
            max_parallel = min(max_parallel, settings.batch_max_parallel_evaluations_groq)
        started = EvaluationBatchRunner.start(
            instructor_id=instructor_id,
            submission_ids=[submission.id for submission in queued_submissions],
            response_language=response_language,
            max_parallel=max_parallel,
            rate_limit_retry_delays=retry_delays,
        )
        if not started:
            return 0, True
        for submission in queued_submissions:
            submission.status = SubmissionStatus.QUEUED
            submission.error_message = None
            submission.processed_at = None
            await self.submission_repository.save_submission(submission)
        await self.session.commit()
        return len(queued_submissions), False

    async def apply_manual_adjustments(
        self,
        *,
        instructor_id: str,
        evaluation_id: str,
        payload: ManualAdjustmentRequest,
    ) -> EvaluationResult:
        evaluation = await self.get_by_id(instructor_id, evaluation_id)
        score_map = {score.id: score for score in evaluation.criterion_scores}
        for item in payload.items:
            score = score_map.get(item.criterion_score_id)
            if not score:
                raise ValidationError(
                    "Manual adjustment references an invalid criterion score",
                    {"criterion_score_id": item.criterion_score_id},
                )
            if item.manual_score is not None and not 0 <= item.manual_score <= evaluation.submission.group.grade_scale:
                raise ValidationError(
                    "Manual score exceeds the allowed grade scale",
                    {
                        "criterion_score_id": item.criterion_score_id,
                        "grade_scale": evaluation.submission.group.grade_scale,
                    },
                )
            previous_manual_score = float(score.manual_score) if score.manual_score is not None else None
            previous_feedback = score.feedback
            score.manual_score = item.manual_score
            score.feedback = item.feedback or score.feedback
            await self.evaluation_repository.save_criterion_score(score)
            await self.evaluation_repository.create_adjustment_history(
                ManualAdjustmentHistory(
                    criterion_score_id=score.id,
                    instructor_id=instructor_id,
                    previous_manual_score=previous_manual_score,
                    new_manual_score=item.manual_score,
                    previous_feedback=previous_feedback,
                    new_feedback=score.feedback,
                )
            )

        evaluation.final_adjusted_score = self._calculate_final_adjusted_score(evaluation)
        await self.evaluation_repository.save_result(evaluation)
        await self.audit_service.log(
            instructor_id=instructor_id,
            action="evaluation.manual_adjustment",
            entity_type="evaluation_result",
            entity_id=evaluation.id,
            metadata_json={"items": [item.model_dump() for item in payload.items]},
        )
        await self.session.commit()
        return await self.get_by_id(instructor_id, evaluation_id)

    def _normalize_score(
        self,
        *,
        score: float | None,
        grade_scale: int,
        is_manual: bool,
    ) -> float | None:
        if score is None:
            return None if is_manual else 0.0
        normalized = max(0.0, min(float(score), float(grade_scale)))
        return round(normalized, 2)

    def _normalize_provider_score(
        self,
        *,
        score: float | None,
        earned_points: float | None,
        criterion_weight: float,
        grade_scale: int,
        is_manual: bool,
    ) -> float | None:
        if score is None and earned_points is not None and criterion_weight > 0:
            bounded_points = max(0.0, min(float(earned_points), criterion_weight))
            score = (bounded_points / criterion_weight) * float(grade_scale)
        return self._normalize_score(score=score, grade_scale=grade_scale, is_manual=is_manual)

    def _calculate_total_ai_score(
        self,
        evaluation: EvaluationResult,
        *,
        score_items: list[CriterionScore] | None = None,
    ) -> float:
        criteria = {criterion.id: criterion for criterion in evaluation.submission.group.criteria}
        total = 0.0
        for score in score_items or evaluation.criterion_scores:
            criterion = criteria[score.criterion_id]
            total += (float(criterion.weight) / 100.0) * float(score.ai_score or 0)
        return round(total, 2)

    def _calculate_final_adjusted_score(
        self,
        evaluation: EvaluationResult,
        *,
        score_items: list[CriterionScore] | None = None,
    ) -> float:
        criteria = {criterion.id: criterion for criterion in evaluation.submission.group.criteria}
        total = 0.0
        for score in score_items or evaluation.criterion_scores:
            criterion = criteria[score.criterion_id]
            effective_score = score.manual_score if score.manual_score is not None else score.ai_score or 0
            total += (float(criterion.weight) / 100.0) * float(effective_score)
        return round(total, 2)

    def _normalize_feedback_for_score(
        self,
        *,
        feedback: str | None,
        ai_score: float | None,
        grade_scale: int,
        is_manual: bool,
        response_language: str,
        missing_provider_item: bool,
    ) -> str:
        cleaned = (feedback or "").strip()
        if cleaned:
            return cleaned

        is_arabic = response_language == "ar"
        if missing_provider_item:
            return (
                "لم يرجع مزود الذكاء الاصطناعي نتيجة لهذا المعيار، لذلك تم التعامل معه كغير مستوفى ويحتاج مراجعة."
                if is_arabic
                else "The AI provider did not return a result for this criterion, so it was treated as unmet and needs review."
            )
        if is_manual:
            return (
                "هذا معيار يدوي ويحتاج إدخال علامة من المدرّس."
                if is_arabic
                else "This is a manual-only criterion and needs an instructor-entered score."
            )
        if ai_score is not None and ai_score >= float(grade_scale):
            return (
                "تم استيفاء المعيار بالكامل ولم يتم الخصم"
                if is_arabic
                else "Criterion fully met, no deductions"
            )
        return (
            "تم الخصم لأن نتيجة المزود أشارت إلى أن هذا المعيار غير مستوفى بالكامل، لكن لم يرجع سبباً تفصيلياً كافياً."
            if is_arabic
            else "Points were deducted because the provider result marked this criterion as not fully met, but did not return enough detailed reasoning."
        )

    async def _log_usage(
        self,
        *,
        instructor_id: str,
        provider_config_id: str,
        provider_name,
        submission_id: str,
        evaluation_result_id: str | None,
        request_type: ProviderRequestType,
        status: ProviderUsageStatus,
        tokens_input: int | None,
        tokens_output: int | None,
        error_message: str | None = None,
    ) -> None:
        usage = ProviderUsageLog(
            instructor_id=instructor_id,
            provider_config_id=provider_config_id,
            provider_name=provider_name,
            submission_id=submission_id,
            evaluation_result_id=evaluation_result_id,
            request_type=request_type,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            files_count=1,
            status=status,
            error_message=error_message,
        )
        self.session.add(usage)
        await self.session.flush()
