# AICTE Rulebook Reference — Approval Process Handbook 2024-2027

> **Source:** `AICTE rulebook.pdf` (231 pages) — Approval Process Handbook 2024-2027
> **Purpose:** Quick reference for the prototype team. This file extracts only the sections relevant to our MVP scope.
> **Last extracted:** 2026-10-25

---

## 1. Confirmed Application Category: Extension of Approval (EoA)

**Chapter II** of the handbook covers "Grant of Extension of Approval for Existing Institutions."

EoA is a recurring annual/multi-year approval that existing AICTE-approved institutions must obtain to continue operating. This aligns with the MVP scope (D-001) — a common, repeatable workflow.

### EoA Sub-categories (Chapter II)
- EoA based on **Self-Disclosure** (simplest — our MVP target)
- Increase in Intake / Additional Courses
- New Programme / Level in existing institutions
- NRI / Foreign National seats
- Merger / Conversion / Closure etc.

**MVP Focus:** EoA based on Self-Disclosure (Clause 2.1 of Annexure-2)

---

## 2. Required Documents for EoA Self-Disclosure (Annexure-2, Section 2.1)

These are the documents that existing institutions must upload for EoA based on Self-Disclosure. This is our **official checklist source**.

| # | Document | Code (for system) | Applicability | Extractable Fields | Source Clause |
|---|----------|-------------------|---------------|-------------------|---------------|
| 1 | **Affidavit-2** (sworn statement by Chairman/Secretary on e-stamp paper of Rs. 100) | `affidavit_2` | `required` | institution_name, signatory_name, notary_date, stamp_paper_value | Annexure-2, §2.1(i) |
| 2 | **Copy of TER Payment Receipt** (Technical Education Regulatory charges receipt from AICTE portal) | `ter_payment_receipt` | `required` | institution_name, receipt_number, payment_date, amount, academic_year | Annexure-2, §2.1(ii) |
| 3 | **Occupancy/Completion Certificate / Building License / Form D** (issued by Competent Authority, per Clause 7.17) | `building_completion_certificate` | `required` | institution_name, certificate_number, issue_date, issuing_authority | Annexure-2, §2.1(iii) |
| 4 | **Structural Stability Certificate** (from registered Structural Engineer — **only if building > 30 years old** from issue of Completion Certificate) | `structural_stability_certificate` | `required_if_applicable` | institution_name, engineer_name, certificate_date, building_age_years | Annexure-2, §2.1(iv) |
| 5 | **Fire Safety Certificate** (valid, issued by Competent Authority) | `fire_safety_certificate` | `required` | institution_name, certificate_number, issue_date, expiry_date, issuing_authority | Annexure-2, §2.1(v) |
| 6 | **Satellite Map** (geographical location with lat/long at main building entrance) | `satellite_map` | `required` | latitude, longitude | Annexure-2, §2.1(vi) |
| 7 | **Audited Statement of Accounts** (of Trust/Society/Company for previous year) | `audited_accounts` | `required` | institution_name, financial_year, auditor_name, audit_date | Annexure-2, §2.1(vii) |

### Additional Context from Affidavit-2 (Page 202-203)
The Affidavit-2 itself references/confirms many of these documents:
- Point 5: Occupancy/Completion Certificate uploaded
- Point 7: Valid Fire Safety Certificate uploaded
- Point 12: Land, Built-up area declarations
- Point 15: Land/Built-up area details table
- Point 16: Additional documents/NOCs/Certificates uploaded
- Point 17: Faculty salary details uploaded
- Point 26: Audited statement of accounts uploaded

---

## 3. MVP Document Selection (Recommended 3 for Prototype)

For the MVP, we select **3 representative document types** that cover different validation scenarios:

### Selected Documents

| Document | Code | Why Selected | Key Validations |
|----------|------|-------------|-----------------|
| **Fire Safety Certificate** | `fire_safety_certificate` | Has expiry date → tests expiry check; has institution name → tests cross-doc consistency | presence, field completeness, expiry, name match |
| **Building Completion Certificate** | `building_completion_certificate` | Core infrastructure document; no expiry but has issue date and authority | presence, field completeness, name match |
| **Affidavit-2** | `affidavit_2` | Legal sworn statement; tests institution name extraction and notary date | presence, field completeness, name match |

### Field Matrix for Selected Documents

| Field | `fire_safety_certificate` | `building_completion_certificate` | `affidavit_2` |
|-------|--------------------------|----------------------------------|---------------|
| `institution_name` | ✅ extract + cross-check | ✅ extract + cross-check | ✅ extract + cross-check |
| `document_number` | ✅ extract | ✅ extract | ❌ |
| `issue_date` | ✅ extract | ✅ extract | ❌ |
| `expiry_date` | ✅ extract + expiry check | ❌ not applicable | ❌ |
| `issuing_authority` | ✅ extract | ✅ extract | ❌ |
| `notary_date` | ❌ | ❌ | ✅ extract |
| `signatory_name` | ❌ | ❌ | ✅ extract |

The current backend validation schema also exposes compatible aliases: `certificate_number` for `document_number`, and `affidavit_date` / `deponent_name` for `notary_date` / `signatory_name`. Both names are retained in extraction output where applicable.

---

## 4. Key AICTE Definitions (from pages 12-15)

| Term | Definition | Relevance |
|------|-----------|-----------|
| **EoA** | Extension of Approval granted by AICTE for conduct of Technical Programme(s)/Course(s) for an Academic Year | Our application category |
| **Extended EoA** | Extension of Approval granted for up to 3 years for qualifying institutions | Extended variant |
| **Academic Year** | Academic activities of the concerned university in a Year (Odd + Even Semester) | Used in application form |
| **Affidavit** | Written sworn statement voluntarily made by a deponent under oath, witnessed by Notary/Commissioner of Oaths | Document type we validate |
| **Approved Institution** | Institution offering Technical Programmes approved by the Council | Our user's institution |
| **TER Charges** | Technical Education Regulatory charges paid through AICTE portal | Receipt we validate |
| **Break in EoA** | Break in obtaining EoA by an institution on their own in the preceding Academic Year(s) | Alternate EoA scenario |

---

## 5. Validation Rules Derived from Handbook

### Rule 1: Document Presence Check
- **Source:** Annexure-2, §2.1 items (i)-(vii)
- **Logic:** For EoA Self-Disclosure, all 7 documents are required. In our MVP, check presence of our selected 3.
- **Status:** `missing` if not uploaded, `pass` if present

### Rule 2: Expiry Date Check
- **Source:** Annexure-2, §2.1(v) — "A **valid** Fire Safety Certificate"
- **Logic:** If `expiry_date` is extracted and is before current date → `flagged`
- **Status:** `flagged` if expired, `pass` if valid, `unresolved` if date not extractable

### Rule 3: Required Field Completeness
- **Source:** Each document has mandatory fields (certificate number, institution name, etc.)
- **Logic:** If a required field for the document type cannot be extracted → `missing` or `unresolved`
- **Status:** `missing` if field clearly absent, `unresolved` if OCR uncertain

### Rule 4: Cross-Document Institution Name Consistency
- **Source:** Affidavit-2 (page 202) — institution declarations must match across documents
- **Logic:** Compare normalized `institution_name` across all uploaded documents and the application
- **Status:** `flagged` if mismatch detected, `unresolved` if name not extractable from any document

### Rule 5: Structural Stability Conditional Check
- **Source:** Annexure-2, §2.1(iv) — required only if building > 30 years old
- **Logic:** If building age > 30 years, structural stability certificate is `required`; else `not_applicable`
- **Status:** `not_applicable` by default in MVP (building age not tracked)

---

## 6. TER Charges Reference (Table 2.1, Page 29)

| Institution Type | TER Charges (Rs. in Lakh/Year) |
|-----------------|-------------------------------|
| Government / Government Aided | 0.50 |
| Minority (Private Unaided) | 0.75 |
| Private (Unaided) | 1.00 |
| Standalone (PGDM) | 1.50 |

> Note: 10% TER charges increase annually.

---

## 7. Processing Timeline (Table 2.2, Page 44)

| Category | Processing Period |
|----------|-----------------|
| EoA based on Self-Disclosure | As per Public Notice Period |
| Change of Site/Location | Year round |
| Closure of Institution | Year round |

---

## 8. Application Status Mapping to AICTE Process

| AICTE Step | Our System Status |
|-----------|------------------|
| Application submitted, docs pending | `processing_incomplete` |
| All docs uploaded, not yet validated | `processing_incomplete` |
| Validation complete, issues found | `discrepancies_found` / `missing_documents` |
| Validation complete, no issues | `checks_passed` |
| Ready for human scrutiny committee | `ready_for_review` |

---

## 9. Important Regulatory Notes

1. **Self-Disclosure is self-attested** — the institution itself uploads and declares. Our system helps verify completeness and consistency, NOT authenticity.
2. **Competent Authority** varies by document type — Fire Safety from Fire Department, Building from Municipal Authority, etc.
3. **Digital signatures** on Affidavits — we cannot verify digital signature validity in the MVP; this is out of scope.
4. **Satellite maps** — primarily an image document; OCR extraction of lat/long may not be reliable. Consider marking fields as `unresolved`.
5. **Audited accounts** — complex multi-page documents; for MVP, verify presence and extract basic header info only.
