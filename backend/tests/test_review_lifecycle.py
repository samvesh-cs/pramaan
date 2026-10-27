import pytest
from httpx import AsyncClient

from app.auth.dependencies import get_current_user
from app.main import app
from app.models.document import Document
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
    finding_ids = [finding["id"] for finding in report_response.json()["findings"]]
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
