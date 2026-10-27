import pytest
from httpx import AsyncClient

from app.auth.dependencies import get_current_user
from app.main import app
from app.models.document import Document
from app.models.finding import Finding
from tests.conftest import FakeUser, TestSessionLocal


async def create_application(client: AsyncClient) -> str:
    response = await client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic Review Lifecycle College",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def add_required_documents(application_id: str) -> None:
    required_types = (
        "fire_safety_certificate",
        "building_completion_certificate",
        "affidavit_2",
    )
    async with TestSessionLocal() as db:
        for index, document_type in enumerate(required_types):
            db.add(
                Document(
                    id=f"doc-lifecycle-{index}",
                    application_id=application_id,
                    document_type=document_type,
                    original_filename=f"synthetic-{document_type}.pdf",
                    stored_filename=f"synthetic-{document_type}.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=100,
                    processing_status="processed",
                )
            )
        await db.commit()


@pytest.mark.asyncio
async def test_institution_submission_requires_all_required_document_types(
    institution_client: AsyncClient,
):
    application_id = await create_application(institution_client)

    response = await institution_client.post(f"/api/applications/{application_id}/submit")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUIRED_DOCUMENTS_MISSING"
    assert set(response.json()["error"]["details"]["missing_document_types"]) == {
        "fire_safety_certificate",
        "building_completion_certificate",
        "affidavit_2",
    }
    application = await institution_client.get(f"/api/applications/{application_id}")
    assert application.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_report_is_available_to_institution_only_after_reviewer_finalizes(
    institution_client: AsyncClient,
):
    institution_user = FakeUser("INSTITUTION", "inst-test-1", "principal@test-college.edu")
    reviewer_user = FakeUser("REVIEWER", "rev-test-1", "reviewer@aicte-india.org")
    app.dependency_overrides[get_current_user] = lambda: institution_user

    application_id = await create_application(institution_client)
    await add_required_documents(application_id)

    submitted = await institution_client.post(f"/api/applications/{application_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    duplicate_submit = await institution_client.post(f"/api/applications/{application_id}/submit")
    assert duplicate_submit.status_code == 409
    assert duplicate_submit.json()["error"]["code"] == "APPLICATION_ALREADY_SUBMITTED"

    premature_report = await institution_client.get(f"/api/applications/{application_id}/report")
    assert premature_report.status_code == 409
    assert premature_report.json()["error"]["code"] == "SCRUTINY_PENDING"

    app.dependency_overrides[get_current_user] = lambda: reviewer_user
    reviewer_application = await institution_client.get(f"/api/applications/{application_id}")
    assert reviewer_application.status_code == 200
    assert reviewer_application.json()["status"] == "submitted"

    no_checks_finalize = await institution_client.post(
        f"/api/applications/{application_id}/finalize-review"
    )
    assert no_checks_finalize.status_code == 409
    assert no_checks_finalize.json()["error"]["code"] == "SCRUTINY_NOT_RUN"

    report_response = await institution_client.post(f"/api/applications/{application_id}/validate")
    assert report_response.status_code == 200
    finding_ids = [finding["id"] for finding in report_response.json()["findings"] if finding["requires_reviewer_decision"]]
    assert finding_ids

    institution_detail_access = await institution_client.get(
        f"/api/applications/{application_id}"
    )
    assert institution_detail_access.status_code == 200
    assert institution_detail_access.json()["findings"] == []

    pending_finalize = await institution_client.post(
        f"/api/applications/{application_id}/finalize-review"
    )
    assert pending_finalize.status_code == 409
    assert pending_finalize.json()["error"]["code"] == "FINDINGS_PENDING_REVIEW"

    invalid_review = await institution_client.patch(
        f"/api/applications/{application_id}/findings/not-a-finding",
        json={"reviewer_decision": "verified", "reviewer_notes": "Synthetic test review."},
    )
    assert invalid_review.status_code == 404

    for finding_id in finding_ids:
        decision = await institution_client.patch(
            f"/api/applications/{application_id}/findings/{finding_id}",
            json={
                "reviewer_decision": "verified",
                "reviewer_notes": "Reviewed against the supplied synthetic document.",
            },
        )
        assert decision.status_code == 200

    finalized = await institution_client.post(
        f"/api/applications/{application_id}/finalize-review"
    )
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "review_completed"

    finalized_rerun = await institution_client.post(f"/api/applications/{application_id}/validate")
    assert finalized_rerun.status_code == 409
    assert finalized_rerun.json()["error"]["code"] == "REVIEW_FINALIZED"

    app.dependency_overrides[get_current_user] = lambda: institution_user
    final_report = await institution_client.get(f"/api/applications/{application_id}/report")
    assert final_report.status_code == 200
    assert final_report.json()["application_id"] == application_id
    assert final_report.json()["findings"]

    completed_application = await institution_client.get(
        f"/api/applications/{application_id}"
    )
    assert completed_application.json()["status"] == "review_completed"
    assert completed_application.json()["findings"]


async def seed_findings(application_id: str, statuses: list[str]) -> list[str]:
    ids = []
    async with TestSessionLocal() as db:
        for index, finding_status in enumerate(statuses):
            finding_id = f"finding-review-policy-{index}"
            ids.append(finding_id)
            db.add(Finding(
                id=finding_id,
                application_id=application_id,
                rule_id=f"POLICY_{index:03d}",
                status=finding_status,
                title=f"Synthetic {finding_status} finding {index}",
                reason="Synthetic reviewer workflow test.",
            ))
        await db.commit()
    return ids


async def create_submitted_application(client: AsyncClient) -> str:
    application_id = await create_application(client)
    await add_required_documents(application_id)
    submitted = await client.post(f"/api/applications/{application_id}/submit")
    assert submitted.status_code == 200
    return application_id


@pytest.mark.asyncio
async def test_only_open_findings_require_review_and_actions_keep_distinct_outcomes(
    institution_client: AsyncClient,
):
    application_id = await create_submitted_application(institution_client)
    pass_id, not_applicable_id, resubmission_id, escalation_id = await seed_findings(
        application_id, ["pass", "not_applicable", "missing", "flagged"]
    )
    reviewer = FakeUser("REVIEWER", "rev-test-1", "reviewer@test-aicte.org")
    app.dependency_overrides[get_current_user] = lambda: reviewer

    report = await institution_client.get(f"/api/applications/{application_id}/report")
    assert report.status_code == 200
    requirements = {finding["id"]: finding["requires_reviewer_decision"] for finding in report.json()["findings"]}
    assert requirements == {
        pass_id: False,
        not_applicable_id: False,
        resubmission_id: True,
        escalation_id: True,
    }

    incomplete = await institution_client.post(f"/api/applications/{application_id}/finalize-review")
    assert incomplete.status_code == 409
    assert set(incomplete.json()["error"]["details"]["pending_finding_ids"]) == {resubmission_id, escalation_id}

    missing_request_details = await institution_client.patch(
        f"/api/applications/{application_id}/findings/{resubmission_id}",
        json={"reviewer_decision": "requested_resubmission", "reviewer_notes": "  "},
    )
    assert missing_request_details.status_code == 422
    assert missing_request_details.json()["error"]["code"] == "VALIDATION_FAILED"
    unchanged_after_failed_request = await institution_client.get(f"/api/applications/{application_id}/report")
    unchanged_finding = next(f for f in unchanged_after_failed_request.json()["findings"] if f["id"] == resubmission_id)
    assert unchanged_finding["reviewer_decision"] is None
    assert unchanged_finding["reviewed_at"] is None

    resubmission = await institution_client.patch(
        f"/api/applications/{application_id}/findings/{resubmission_id}",
        json={
            "reviewer_decision": "requested_resubmission",
            "reviewer_notes": "Upload a current occupancy certificate.",
            "reviewed_by": "Client supplied identity must be ignored",
        },
    )
    assert resubmission.status_code == 200
    assert resubmission.json()["status"] == "missing"
    assert resubmission.json()["reviewed_by"] == reviewer.email
    assert resubmission.json()["reviewer_notes"] == "Upload a current occupancy certificate."
    application_after_request = await institution_client.get(f"/api/applications/{application_id}")
    assert application_after_request.json()["overall_status"] == "missing_documents"

    rerun_after_decision = await institution_client.post(f"/api/applications/{application_id}/validate")
    assert rerun_after_decision.status_code == 409
    assert rerun_after_decision.json()["error"]["code"] == "SCRUTINY_HAS_REVIEW_DECISIONS"

    overwrite_attempt = await institution_client.patch(
        f"/api/applications/{application_id}/findings/{resubmission_id}",
        json={
            "reviewer_decision": "escalated",
            "reviewer_notes": "Attempt to replace the recorded request.",
        },
    )
    assert overwrite_attempt.status_code == 409
    assert overwrite_attempt.json()["error"]["code"] == "REVIEW_DECISION_ALREADY_RECORDED"
    stored_request = await institution_client.get(f"/api/applications/{application_id}/report")
    saved_resubmission = next(f for f in stored_request.json()["findings"] if f["id"] == resubmission_id)
    assert saved_resubmission["reviewer_decision"] == "requested_resubmission"
    assert saved_resubmission["reviewer_notes"] == "Upload a current occupancy certificate."

    missing_escalation_reason = await institution_client.patch(
        f"/api/applications/{application_id}/findings/{escalation_id}",
        json={"reviewer_decision": "escalated"},
    )
    assert missing_escalation_reason.status_code == 422

    escalation = await institution_client.patch(
        f"/api/applications/{application_id}/findings/{escalation_id}",
        json={
            "reviewer_decision": "escalated",
            "reviewer_notes": "Refer the building age discrepancy to the regional technical authority.",
        },
    )
    assert escalation.status_code == 200
    assert escalation.json()["status"] == "flagged"
    assert escalation.json()["reviewed_by"] == reviewer.email

    application = await institution_client.get(f"/api/applications/{application_id}")
    assert application.json()["overall_status"] == "missing_documents"
    finalized = await institution_client.post(f"/api/applications/{application_id}/finalize-review")
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "review_completed"
    assert finalized.json()["overall_status"] == "missing_documents"


@pytest.mark.asyncio
async def test_pass_and_not_applicable_findings_do_not_block_finalization(
    institution_client: AsyncClient,
):
    application_id = await create_submitted_application(institution_client)
    pass_id, _ = await seed_findings(application_id, ["pass", "not_applicable"])
    app.dependency_overrides[get_current_user] = lambda: FakeUser("REVIEWER", "rev-test-1", "reviewer@test-aicte.org")

    forbidden_decision = await institution_client.patch(
        f"/api/applications/{application_id}/findings/{pass_id}",
        json={"reviewer_decision": "verified"},
    )
    assert forbidden_decision.status_code == 409
    assert forbidden_decision.json()["error"]["code"] == "REVIEW_NOT_REQUIRED"

    finalized = await institution_client.post(f"/api/applications/{application_id}/finalize-review")
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "review_completed"


@pytest.mark.asyncio
async def test_verified_action_needs_no_follow_up_text_and_keeps_rule_status_separate(
    institution_client: AsyncClient,
):
    application_id = await create_submitted_application(institution_client)
    finding_id = (await seed_findings(application_id, ["flagged"]))[0]
    reviewer = FakeUser("REVIEWER", "rev-test-1", "reviewer@test-aicte.org")
    app.dependency_overrides[get_current_user] = lambda: reviewer

    verified = await institution_client.patch(
        f"/api/applications/{application_id}/findings/{finding_id}",
        json={"reviewer_decision": "verified"},
    )
    assert verified.status_code == 200
    assert verified.json()["status"] == "flagged"
    assert verified.json()["reviewer_decision"] == "verified"
    assert verified.json()["reviewer_notes"] is None
    assert verified.json()["reviewed_by"] == reviewer.email
    assert verified.json()["reviewed_at"] is not None

    application = await institution_client.get(f"/api/applications/{application_id}")
    assert application.json()["overall_status"] == "ready_for_review"
