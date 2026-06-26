from app.utils.evaluation_response_audit import (
    RequirementAuditItem,
    audit_consistency_errors,
    cap_score_by_explicit_evidence,
)


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
