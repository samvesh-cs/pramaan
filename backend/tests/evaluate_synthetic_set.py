"""Evaluate process_document against backend/tests/ground_truth.json."""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.ocr import process_document

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GT_PATH = os.path.join(BASE_DIR, "ground_truth.json")
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")

with open(GT_PATH, "r", encoding="utf-8") as f:
    ground_truth = json.load(f)

results = []
failures = []
total_fields_checked = 0
passed_fields = 0

print("=" * 80)
print("RUNNING EVALUATION ON SYNTHETIC TEST SET")
print("=" * 80)

for filename, info in ground_truth.items():
    file_path = os.path.join(SAMPLES_DIR, filename)
    doc_type = info["document_type"]
    category = info["category"]
    expected_status = info["expected_processing_status"]
    expected_fields = info.get("expected_fields", {})

    print(f"\nEvaluating: {filename} ({category}) [DocType: {doc_type}]")
    res = process_document(file_path, document_type=doc_type)

    doc_status_pass = (res.processing_status == expected_status)
    if not doc_status_pass:
        failures.append({
            "filename": filename,
            "type": "processing_status_mismatch",
            "expected": expected_status,
            "actual": res.processing_status,
            "error": res.error
        })

    field_evaluations = {}
    for f_name, expected_val in expected_fields.items():
        total_fields_checked += 1
        actual_field_obj = res.fields.get(f_name)
        actual_val = actual_field_obj.value if actual_field_obj else None
        actual_status = actual_field_obj.status if actual_field_obj else "not_returned"
        actual_conf = actual_field_obj.confidence if actual_field_obj else None
        actual_raw = actual_field_obj.raw_text if actual_field_obj else None

        # Check match
        if expected_val is None:
            # Expected to be missing
            is_match = (actual_val is None) and (actual_status == "missing")
        else:
            is_match = (str(actual_val).strip() == str(expected_val).strip())

        if is_match:
            passed_fields += 1
            verdict = "PASS"
        else:
            verdict = "FAIL"
            failures.append({
                "filename": filename,
                "field": f_name,
                "expected": expected_val,
                "actual": actual_val,
                "status": actual_status,
                "confidence": actual_conf
            })

        print(f"  [{verdict}] {f_name:22s} | Expected: {str(expected_val):<35s} | Actual: {str(actual_val):<35s} | Status: {actual_status:<10s} | Conf: {str(actual_conf)}")

        field_evaluations[f_name] = {
            "expected": expected_val,
            "actual": actual_val,
            "verdict": verdict,
            "status": actual_status,
            "confidence": actual_conf,
            "raw_text": actual_raw
        }

    results.append({
        "filename": filename,
        "category": category,
        "document_type": doc_type,
        "expected_status": expected_status,
        "actual_status": res.processing_status,
        "doc_status_pass": doc_status_pass,
        "error": res.error,
        "fields": field_evaluations
    })

eval_out_path = os.path.join(BASE_DIR, "evaluation_results.json")
with open(eval_out_path, "w", encoding="utf-8") as f:
    json.dump({
        "summary": {
            "total_documents": len(ground_truth),
            "total_fields": total_fields_checked,
            "passed_fields": passed_fields,
            "failed_fields": total_fields_checked - passed_fields,
            "total_failures": len(failures)
        },
        "failures": failures,
        "details": results
    }, f, indent=2)

print("\n" + "=" * 80)
print(f"EVALUATION SUMMARY: {passed_fields}/{total_fields_checked} fields PASS ({len(failures)} total failures)")
print("=" * 80)
if failures:
    print("\nFAILURES FOUND:")
    for f in failures:
        print(f" - {f}")
else:
    print("\nNO FAILURES FOUND! ALL CASES PASSED.")
