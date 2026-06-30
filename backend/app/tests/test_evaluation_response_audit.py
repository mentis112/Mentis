from app.utils.evaluation_response_audit import (
    RequirementAuditItem,
    align_score_with_fully_met_audit,
    append_points_breakdown_to_feedback,
    audit_consistency_errors,
    cap_score_by_audit_consistency,
    cap_score_by_explicit_evidence,
    normalized_score_to_points,
    remove_generic_improvement_language,
    should_apply_explicit_evidence_cap,
    soften_generic_partial_audit_items,
    validate_and_correct_criterion_score,
)
from app.utils.prompt_builder import build_prompt_criterion_id, parse_explicit_penalties


CLINIC_REQUIREMENTS = (
    "Explains the clinic booking problem, target users, project scope, at least 5 clear "
    "functional requirements, and 2 measurable non-functional requirements"
)
CLINIC_DATA_MODEL = (
    "Defines the main entities/tables Users, Doctors, ClinicServices, TimeSlots, and "
    "Appointments, including primary keys, foreign keys, relationships, and "
    "booking/cancellation/capacity rules"
)
CLINIC_TESTING = (
    "Provides at least 4 test cases with expected results, covering success, failure, "
    "boundary/edge, and role/security or validation behavior"
)


def test_caps_absent_explicit_items_without_zeroing() -> None:
    submission = (
        "Campus Clinic Appointment Booking System Report Student ID: 20261010. "
        "A clinic website is useful. Students can use it. The report does not explain "
        "the problem, users, scope, or clear requirements. A database may be used to "
        "store information. No real entities, keys, relationships, or booking rules are "
        "provided. The project will be tested after it is finished."
    )

    data_score, _ = cap_score_by_explicit_evidence(
        criterion_description=CLINIC_DATA_MODEL,
        submission_text=submission,
        normalized_score=100,
        grade_scale=100,
        response_language="en",
    )
    testing_score, _ = cap_score_by_explicit_evidence(
        criterion_description=CLINIC_TESTING,
        submission_text=submission,
        normalized_score=100,
        grade_scale=100,
        response_language="en",
    )

    assert data_score == 5.0
    assert testing_score == 5.0


def test_does_not_cap_complete_requirement_text_for_missing_exact_soft_phrases() -> None:
    submission = (
        "The project solves appointment crowding by replacing phone scheduling. Students, "
        "doctors, reception staff, and administrators are supported. It includes booking, "
        "cancellation, reminders, and administrative setup. Functional requirements FR1, "
        "FR2, FR3, FR4, FR5, and FR6 are described. Non-functional requirements NFR1 and "
        "NFR2 define response time and role-based access."
    )

    score, note = cap_score_by_explicit_evidence(
        criterion_description=CLINIC_REQUIREMENTS,
        submission_text=submission,
        normalized_score=100,
        grade_scale=100,
        response_language="en",
    )

    assert score == 100
    assert note is None


def test_full_score_conflicts_with_missing_audit_item() -> None:
    errors = audit_consistency_errors(
        criterion_name="Testing and Validation Plan",
        audit_items=[
            RequirementAuditItem(
                requirement="4 test cases",
                status="missing",
                evidence="The project will be tested after it is finished.",
                missing_or_weak_reason="No actual test cases or expected results are provided.",
            )
        ],
        normalized_score=100,
        grade_scale=100,
        is_manual=False,
    )

    assert errors


def test_caps_high_score_when_missing_audit_has_no_met_items() -> None:
    score, note = cap_score_by_audit_consistency(
        criterion_name="Testing and Validation Plan",
        audit_items=[
            RequirementAuditItem(
                requirement="4 test cases",
                status="missing",
                evidence="",
                missing_or_weak_reason="No actual test cases are listed.",
            )
        ],
        normalized_score=90,
        grade_scale=100,
        is_manual=False,
        response_language="en",
    )

    assert score == 55
    assert note


def test_does_not_cap_high_score_for_single_partial_audit_item() -> None:
    score, note = cap_score_by_audit_consistency(
        criterion_name="All questions answered",
        audit_items=[
            RequirementAuditItem(
                requirement="Answer all questions",
                status="partial",
                evidence="Most questions were answered well.",
                missing_or_weak_reason="Some answers are incomplete or unclear.",
            )
        ],
        normalized_score=85,
        grade_scale=100,
        is_manual=False,
        response_language="en",
    )

    assert score == 85
    assert note is None


def test_skips_explicit_evidence_cap_when_audit_items_are_all_met() -> None:
    audit_items = [
        RequirementAuditItem(
            requirement="Student ID and title",
            status="met",
            evidence="Student ID: 20262001",
            missing_or_weak_reason="",
        ),
        RequirementAuditItem(
            requirement="Clear sections",
            status="met",
            evidence="1. Problem and beneficiaries",
            missing_or_weak_reason="",
        ),
    ]

    assert should_apply_explicit_evidence_cap(audit_items) is False


def test_applies_explicit_evidence_cap_when_audit_has_partial_or_missing_items() -> None:
    audit_items = [
        RequirementAuditItem(
            requirement="Answer all questions",
            status="partial",
            evidence="Most questions were answered.",
            missing_or_weak_reason="Some answers are incomplete.",
        )
    ]

    assert should_apply_explicit_evidence_cap(audit_items) is True


def test_raises_score_to_full_when_all_audit_items_are_met_with_evidence() -> None:
    score, adjusted = align_score_with_fully_met_audit(
        audit_items=[
            RequirementAuditItem(
                requirement="Student ID and title",
                status="met",
                evidence="Student ID: 20262001, title: Pharmacy system",
                missing_or_weak_reason="",
            ),
            RequirementAuditItem(
                requirement="Clear organization",
                status="met",
                evidence="The submission uses numbered sections.",
                missing_or_weak_reason="",
            ),
        ],
        normalized_score=90,
        grade_scale=100,
        is_manual=False,
    )

    assert score == 100
    assert adjusted is True


def test_does_not_raise_score_when_met_audit_lacks_evidence() -> None:
    score, adjusted = align_score_with_fully_met_audit(
        audit_items=[
            RequirementAuditItem(
                requirement="Clear organization",
                status="met",
                evidence="",
                missing_or_weak_reason="",
            )
        ],
        normalized_score=90,
        grade_scale=100,
        is_manual=False,
    )

    assert score == 90
    assert adjusted is False


def test_softens_partial_when_reason_is_only_generic_improvement() -> None:
    softened = soften_generic_partial_audit_items(
        [
            RequirementAuditItem(
                requirement="Clarity and flow",
                status="partial",
                evidence="The answer is organized and clear.",
                missing_or_weak_reason="يمكن تحسين بعض الجوانب مثل وضوح اللغة وتسلسل الأفكار",
            )
        ]
    )

    assert softened[0].status == "met"
    assert softened[0].missing_or_weak_reason == ""


def test_does_not_soften_partial_when_reason_has_concrete_missing_item() -> None:
    softened = soften_generic_partial_audit_items(
        [
            RequirementAuditItem(
                requirement="Test cases",
                status="partial",
                evidence="Two test cases are listed.",
                missing_or_weak_reason="Two required test cases are missing.",
            )
        ]
    )

    assert softened[0].status == "partial"


def test_allows_high_score_when_most_audit_items_are_met() -> None:
    audit_items = [
        RequirementAuditItem(
            requirement="Reliable recent sources",
            status="met",
            evidence="The submission cites current medical AI studies.",
            missing_or_weak_reason="",
        ),
        RequirementAuditItem(
            requirement="One tool comparison",
            status="missing",
            evidence="",
            missing_or_weak_reason="The comparison is not explicit.",
        ),
    ]

    errors = audit_consistency_errors(
        criterion_name="Critical comparison",
        audit_items=audit_items,
        normalized_score=86,
        grade_scale=100,
        is_manual=False,
    )
    score, note = cap_score_by_audit_consistency(
        criterion_name="Critical comparison",
        audit_items=audit_items,
        normalized_score=86,
        grade_scale=100,
        is_manual=False,
        response_language="en",
    )

    assert errors == []
    assert score == 86
    assert note is None


def test_normalized_score_converts_to_criterion_points() -> None:
    assert (
        normalized_score_to_points(
            normalized_score=50,
            criterion_weight=20,
            grade_scale=100,
        )
        == 10
    )


def test_feedback_includes_deducted_points() -> None:
    feedback = append_points_breakdown_to_feedback(
        "Missing expected results for two test cases.",
        normalized_score=75,
        criterion_weight=20,
        grade_scale=100,
        response_language="en",
        is_manual=False,
    )

    assert "Points: 15 out of 20" in feedback
    assert "Deducted: 5 out of 20" in feedback
    assert "Missing expected results" in feedback


def test_prompt_criterion_ids_are_zero_padded() -> None:
    assert build_prompt_criterion_id(0) == "cr_01"
    assert build_prompt_criterion_id(9) == "cr_10"


def test_parses_explicit_penalties_from_criterion_description() -> None:
    penalties = parse_explicit_penalties(
        "ERD quality -5 لكل جدول مفقود، -10 points when relationships are absent."
    )

    assert penalties == [(5, "جدول مفقود"), (10, "relationships are absent")]


def test_validation_corrects_full_score_with_partial_audit() -> None:
    earned, feedback, audit_items, needs_review, issues = validate_and_correct_criterion_score(
        criterion_id="cr_01",
        criterion_name="Data model",
        max_points=40,
        earned_points=40,
        feedback="Good work.",
        audit_items=[
            RequirementAuditItem(
                requirement="relationships",
                status="partial",
                evidence="Two relationships are described.",
                missing_or_weak_reason="found 2, required 4",
            )
        ],
        criterion_description="Requires 4 relationships.",
    )

    assert earned == 24
    assert "[Auto-corrected: score aligned to audit coverage.]" in feedback
    assert audit_items[-1].status == "partial"
    assert needs_review is False
    assert issues


def test_removes_generic_improvement_clause_from_feedback() -> None:
    cleaned, removed = remove_generic_improvement_language(
        "تم استيفاء معظم المتطلبات المطلوبة، ولكن هناك بعض النقاط التي يمكن تحسينها."
    )

    assert cleaned == "تم استيفاء معظم المتطلبات المطلوبة"
    assert removed == ["هناك بعض النقاط التي يمكن تحسينها."]


def test_keeps_specific_missing_reason_in_feedback() -> None:
    cleaned, removed = remove_generic_improvement_language(
        "The answer needs more detail because only 2 tables were found and 4 were required."
    )

    assert cleaned == "The answer needs more detail because only 2 tables were found and 4 were required."
    assert removed == []


def test_validation_removes_unsupported_generic_deduction() -> None:
    earned, feedback, audit_items, needs_review, issues = validate_and_correct_criterion_score(
        criterion_id="cr_01",
        criterion_name="System analysis",
        max_points=20,
        earned_points=17,
        feedback="تم استيفاء معظم المتطلبات المطلوبة",
        audit_items=[
            RequirementAuditItem(
                requirement="Analysis requirements",
                status="partial",
                evidence="The submission includes analysis content.",
                missing_or_weak_reason="يمكن تحسينها",
            )
        ],
        criterion_description="Analyze and design a university pharmacy management system.",
    )

    assert earned == 20
    assert audit_items[0].status == "met"
    assert needs_review is False
    assert "all requirements met" in feedback
    assert issues


def test_validation_removes_unsupported_deduction_without_audit() -> None:
    earned, feedback, audit_items, needs_review, issues = validate_and_correct_criterion_score(
        criterion_id="cr_01",
        criterion_name="System analysis",
        max_points=20,
        earned_points=17,
        feedback="تم استيفاء معظم المتطلبات المطلوبة",
        audit_items=[],
        criterion_description="Analyze and design a university pharmacy management system.",
    )

    assert earned == 20
    assert audit_items == []
    assert needs_review is False
    assert "no specific unmet requirement" in feedback
    assert issues


def test_validation_keeps_partial_audit_deduction_when_checklist_still_has_unmet_items() -> None:
    earned, feedback, audit_items, needs_review, issues = validate_and_correct_criterion_score(
        criterion_id="cr_01",
        criterion_name="تحليل المشكلة والمتطلبات",
        max_points=30,
        earned_points=28,
        feedback="تم استيفاء معظم المتطلبات المطلوبة",
        audit_items=[
            RequirementAuditItem(
                requirement="تحليل المشكلة",
                status="met",
                evidence="يوجد شرح للمشكلة الحالية في المستودع.",
                missing_or_weak_reason="",
            ),
            RequirementAuditItem(
                requirement="تحديد المستخدمين المستهدفين",
                status="met",
                evidence="المستخدمون: أمين المستودع، موظف المشتريات",
                missing_or_weak_reason="",
            ),
            RequirementAuditItem(
                requirement="تحديد نطاق المشروع",
                status="met",
                evidence="نطاق المشروع: الأصناف، الصرف والاستلام، الطلبات",
                missing_or_weak_reason="",
            ),
            RequirementAuditItem(
                requirement="6 متطلبات وظيفية واضحة على الأقل",
                status="met",
                evidence="FR1..FR6 مذكورة بوضوح.",
                missing_or_weak_reason="",
            ),
            RequirementAuditItem(
                requirement="3 متطلبات غير وظيفية قابلة للقياس",
                status="partial",
                evidence="NFR1: تحديث الرصيد خلال أقل من ثانية، NFR2: 80 مستخدمًا متزامنًا خلال أقل من 3 ثوان.",
                missing_or_weak_reason="يوجد فقط متطلبان غير وظيفيين قابلان للقياس بينما المعيار يطلب 3.",
            )
        ],
        criterion_description="يشرح المشكلة ويتضمن 6 متطلبات وظيفية واضحة على الأقل و3 متطلبات غير وظيفية قابلة للقياس.",
    )

    assert earned == 27.6
    assert audit_items[-1].status == "partial"
    assert needs_review is False
    assert "no specific unmet requirement" not in feedback
    assert any("audit coverage ratio" in issue for issue in issues)


def test_validation_keeps_deduction_with_specific_gap() -> None:
    earned, feedback, audit_items, needs_review, issues = validate_and_correct_criterion_score(
        criterion_id="cr_01",
        criterion_name="Tables",
        max_points=20,
        earned_points=15,
        feedback="Missing required tables.",
        audit_items=[
            RequirementAuditItem(
                requirement="4 tables",
                status="partial",
                evidence="Two tables are listed.",
                missing_or_weak_reason="found 2, required 4",
            )
        ],
        criterion_description="Requires 4 tables.",
    )

    assert earned == 12
    assert audit_items[0].status == "partial"
    assert needs_review is False
    assert "Missing required tables" in feedback
    assert not any("no specific unmet requirement" in issue for issue in issues)
    assert any("audit coverage ratio" in issue for issue in issues)


def test_validation_caps_score_by_partial_and_missing_coverage() -> None:
    earned, feedback, audit_items, needs_review, issues = validate_and_correct_criterion_score(
        criterion_id="cr_02",
        criterion_name="Testing plan",
        max_points=25,
        earned_points=25,
        feedback="Good work.",
        audit_items=[
            RequirementAuditItem(
                requirement="success case",
                status="met",
                evidence="TC1 success case is listed.",
                missing_or_weak_reason="",
            ),
            RequirementAuditItem(
                requirement="failure case",
                status="met",
                evidence="TC2 failure case is listed.",
                missing_or_weak_reason="",
            ),
            RequirementAuditItem(
                requirement="boundary case",
                status="partial",
                evidence="A low-stock case is mentioned without expected result.",
                missing_or_weak_reason="Boundary scenario is incomplete.",
            ),
            RequirementAuditItem(
                requirement="permission case",
                status="missing",
                evidence="Not found",
                missing_or_weak_reason="Permission validation case is missing.",
            ),
        ],
        criterion_description="Requires success, failure, boundary, and permission test cases.",
    )

    assert earned == 17.5
    assert needs_review is False
    assert "[Auto-corrected: score aligned to audit coverage.]" in feedback
    assert any("audit coverage ratio" in issue for issue in issues)


def test_validation_does_not_raise_full_marks_when_met_audit_lacks_evidence() -> None:
    earned, feedback, audit_items, needs_review, issues = validate_and_correct_criterion_score(
        criterion_id="cr_01",
        criterion_name="System analysis",
        max_points=20,
        earned_points=17,
        feedback="Well structured response.",
        audit_items=[
            RequirementAuditItem(
                requirement="Clear organization",
                status="met",
                evidence="",
                missing_or_weak_reason="",
            )
        ],
        criterion_description="Analyze and design a university pharmacy management system.",
    )

    assert earned == 17
    assert audit_items[0].status == "met"
    assert needs_review is False
    assert not any("all audit items are met" in issue for issue in issues)


def test_arabic_feedback_includes_deducted_points() -> None:
    feedback = append_points_breakdown_to_feedback(
        "ينقص الملف شرح العلاقات.",
        normalized_score=50,
        criterion_weight=10,
        grade_scale=100,
        response_language="ar",
        is_manual=False,
    )

    assert "النقاط: 5 من 10" in feedback
    assert "مقدار الخصم: 5 من 10" in feedback
