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

for filename, info in ground_truth.items():
    file_path = os.path.join(SAMPLES_DIR, filename)
    doc_type = info["document_type"]
    category = info["category"]
    expected_status = info["expected_processing_status"]
    expected_fields = info.get("expected_fields", {})

    print(f"Processing {filename} ({category})...")
    res = process_document(file_path, document_type=doc_type)

    extracted_fields_dict = {}
    if res.fields:
        for f_name, f_obj in res.fields.items():
            extracted_fields_dict[f_name] = {
                "value": f_obj.value,
                "confidence": f_obj.confidence,
                "raw_text": f_obj.raw_text
            }

    results.append({
        "filename": filename,
        "category": category,
        "document_type": doc_type,
        "expected_status": expected_status,
        "actual_status": res.processing_status,
        "error": res.error,
        "expected_fields": expected_fields,
        "extracted_fields": extracted_fields_dict
    })

eval_out_path = os.path.join(BASE_DIR, "evaluation_results.json")
with open(eval_out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("\n--- EVALUATION SUMMARY ---")
for r in results:
    status_match = "PASS" if r["expected_status"] == r["actual_status"] else "FAIL"
    print(f"[{status_match}] {r['filename']} ({r['category']}) -> status: {r['actual_status']}")
    if r["error"]:
        print(f"    Error handled: {r['error']}")
    if r["expected_fields"]:
        for k, v in r["expected_fields"].items():
            act = r["extracted_fields"].get(k, {})
            act_val = act.get("value")
            act_conf = act.get("confidence")
            match = "EXACT" if str(act_val) == str(v) else "MISMATCH"
            print(f"    - {k:25s} | Expected: {v} | Extracted: {act_val} (conf: {act_conf}) [{match}]")
