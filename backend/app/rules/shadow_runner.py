"""
Shadow Evaluation Runner for Declarative Rule Engine.
Executes declarative rules in shadow mode on an in-memory deep-copied context
with zero database access in the worker thread.
"""

import asyncio
import copy
import logging
from types import SimpleNamespace
from typing import Any

from app.config import settings
from app.rules.declarative_engine import default_declarative_engine

logger = logging.getLogger(__name__)


def create_shadow_context(
    application_id: str,
    application: Any,
    documents: list[Any],
    extractions_by_doc_id: dict[str, Any],
    all_system_documents: list[Any],
) -> dict[str, Any]:
    """
    Creates a completely detached, deep-copied in-memory snapshot of the validation context.
    Zero references to SQLAlchemy sessions or database connections.
    """
    detached_docs = [
        SimpleNamespace(
            id=getattr(d, "id", None),
            application_id=getattr(d, "application_id", None),
            document_type=getattr(d, "document_type", None),
            original_filename=getattr(d, "original_filename", None),
            processing_status=getattr(d, "processing_status", None),
        )
        for d in documents
    ]

    detached_extractions = {}
    for doc_id, ext in extractions_by_doc_id.items():
        if ext:
            detached_extractions[doc_id] = SimpleNamespace(
                id=getattr(ext, "id", None),
                document_id=getattr(ext, "document_id", None),
                processing_status=getattr(ext, "processing_status", None),
                fields=copy.deepcopy(getattr(ext, "fields", {})) if isinstance(getattr(ext, "fields", None), dict) else {},
                raw_text=getattr(ext, "raw_text", None),
                confidence=getattr(ext, "confidence", None),
                error=getattr(ext, "error", None),
            )
        else:
            detached_extractions[doc_id] = None

    detached_app = SimpleNamespace(
        id=getattr(application, "id", application_id),
        institution_name=getattr(application, "institution_name", None),
        application_category=getattr(application, "application_category", None),
        academic_year=getattr(application, "academic_year", None),
        overall_status=getattr(application, "overall_status", None),
    )

    detached_all_docs = [
        SimpleNamespace(
            id=getattr(d, "id", None),
            application_id=getattr(d, "application_id", None),
            document_type=getattr(d, "document_type", None),
            original_filename=getattr(d, "original_filename", None),
        )
        for d in all_system_documents
    ]

    return {
        "application_id": application_id,
        "application": detached_app,
        "documents": detached_docs,
        "extractions": detached_extractions,
        "all_system_documents": detached_all_docs,
    }


def run_shadow_evaluation_worker(
    application_id: str,
    copied_context: dict[str, Any],
    legacy_findings_summary: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Worker function executed in asyncio.to_thread with ZERO database access.
    Logs discrepancies adhering strictly to:
    application_id, rule_id, legacy_status, shadow_status, discrepancy code.
    """
    discrepancies: list[dict[str, Any]] = []
    try:
        shadow_findings = default_declarative_engine.evaluate(copied_context)

        legacy_map = {f["rule_id"]: f["status"] for f in legacy_findings_summary}
        shadow_map = {f.rule_id: f.status for f in shadow_findings}

        all_rules = sorted(set(legacy_map.keys()) | set(shadow_map.keys()))
        for r_id in all_rules:
            l_stat = legacy_map.get(r_id, "MISSING_IN_LEGACY")
            s_stat = shadow_map.get(r_id, "MISSING_IN_SHADOW")
            if l_stat != s_stat:
                code = "STATUS_MISMATCH" if l_stat != "MISSING_IN_LEGACY" and s_stat != "MISSING_IN_SHADOW" else "COVERAGE_MISMATCH"
                discrepancy_info = {
                    "application_id": application_id,
                    "rule_id": r_id,
                    "legacy_status": l_stat,
                    "shadow_status": s_stat,
                    "discrepancy_code": code,
                }
                discrepancies.append(discrepancy_info)
                logger.info(
                    "SHADOW_DISCREPANCY: application_id=%s rule_id=%s legacy_status=%s shadow_status=%s discrepancy_code=%s",
                    application_id,
                    r_id,
                    l_stat,
                    s_stat,
                    code,
                )
    except Exception as exc:
        logger.warning(
            "SHADOW_FAILURE: application_id=%s shadow declarative evaluation failed: %s",
            application_id,
            exc,
        )

    return discrepancies


async def dispatch_shadow_evaluation(
    application_id: str,
    application: Any,
    documents: list[Any],
    extractions_by_doc_id: dict[str, Any],
    all_system_documents: list[Any],
    legacy_findings: list[Any],
) -> None:
    """
    Safely dispatches shadow evaluation in a background worker thread.
    Never blocks the request and never raises exceptions to caller.
    """
    if not getattr(settings, "ENABLE_SHADOW_DECLARATIVE_ENGINE", False):
        return

    try:
        shadow_context = create_shadow_context(
            application_id=application_id,
            application=application,
            documents=documents,
            extractions_by_doc_id=extractions_by_doc_id,
            all_system_documents=all_system_documents,
        )
        copied_context = copy.deepcopy(shadow_context)
        legacy_summary = [
            {"rule_id": getattr(f, "rule_id", ""), "status": getattr(f, "status", "")}
            for f in legacy_findings
        ]

        # Dispatch non-blocking in worker thread with timeout
        async def _safe_run():
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(
                        run_shadow_evaluation_worker,
                        application_id,
                        copied_context,
                        legacy_summary,
                    ),
                    timeout=5.0,
                )
            except Exception as e:
                logger.warning(
                    "SHADOW_FAILURE: application_id=%s shadow execution timed out or failed: %s",
                    application_id,
                    e,
                )

        asyncio.create_task(_safe_run())
    except Exception as e:
        logger.warning(
            "SHADOW_FAILURE: Failed to dispatch shadow evaluation for application %s: %s",
            application_id,
            e,
        )
