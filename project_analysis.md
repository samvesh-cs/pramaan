# SIH 26 — Project Analysis, Gaps, USPs & API Reference

## 1. Project Idea Analysis

### What You're Building
An AI-powered **preliminary document scrutiny tool** for AICTE institutional applications. It does NOT make approval decisions — it helps a human reviewer identify missing documents, expired certificates, field mismatches, and incomplete applications before formal scrutiny.

### Strengths of the Idea
- **Real pain point:** AICTE processes thousands of EoA applications. Manual document checking is repetitive and error-prone.
- **Well-scoped:** Only tackles document completeness + consistency, not authentication/forgery — this is honest and achievable.
- **Evidence-linked:** Every finding cites the document, page, extracted text — reviewers can verify.
- **Regulatory grounding:** Rules derived directly from AICTE APH 2024-2027, Annexure-2.

### Weaknesses / Risks
- **OCR reliability:** PaddleOCR on scanned certificates with stamps/seals can be noisy. Extracted values may be wrong.
- **Limited document coverage:** Only 3 of 7 EoA documents in MVP.
- **No real AICTE integration:** Can't verify TER payment receipts or cross-reference AICTE portal data.

---

## 2. Gaps Identified

### 2.1 Idea-Level Gaps

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| **No confidence threshold** for OCR results | High | Define a minimum confidence (e.g., 0.7) below which a field becomes `unresolved` instead of used for checks |
| **No document version/year awareness** | Medium | Fire Safety Certificates vary by state. The system should note which format it expects |
| **Satellite map validation is impractical** | Low | OCR on satellite maps yields poor results. Mark all satellite_map fields as `unresolved` or skip for MVP |
| **No reviewer correction flow** | Medium | If OCR extracts wrong date, reviewer has no way to correct it. Add as post-MVP feature |
| **Single language assumption** | Medium | AICTE documents may be bilingual (English + regional). PaddleOCR supports multilingual but needs config |

### 2.2 Implementation-Level Gaps

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| **Person 2 has no code yet** | 🔴 Critical | Aditya's branch has 0 file changes. Extraction module blocks integration. Person 3 must build with mock first |
| **No API_CONTRACT.md update for decisions** | Medium | Q-001, Q-002, Q-003 need to be marked as resolved in DECISIONS.md |
| **No synthetic test documents created** | High | No team member has created the test PDFs yet. This blocks validation testing |
| **No database migration setup** | Medium | Alembic not initialized yet |
| **Frontend also not started** | Medium | `frontend/` is empty. Person 1 needs to start |
| **.gitignore was empty** | ✅ Fixed | Updated with comprehensive rules |

### 2.3 Architecture Gaps

| Gap | Recommendation |
|-----|----------------|
| No async file processing | Use FastAPI background tasks for OCR processing. Don't block upload response |
| No idempotent validation | Multiple POST to `/validate` should clear previous findings and regenerate |
| No pagination | Sufficient for MVP, but note for scaling |

---

## 3. USPs (Unique Selling Points) You Can Add

### Must-Have USPs (Differentiation for Judges)

| USP | Description | Difficulty |
|-----|-------------|-----------|
| 🏆 **AICTE-Specific Rule Engine** | Rules mapped directly to APH 2024-27 annexure clauses with source citations in every finding | Low — already planned |
| 🏆 **Evidence-Linked Findings** | Every finding shows exact extracted text, page number, bounding box, and confidence | Low — in API contract |
| 🏆 **Confidence-Aware Processing** | System doesn't guess — low-confidence OCR becomes `unresolved` with explanation | Low — just a threshold |
| 🏆 **Cross-Document Consistency** | Auto-detects if institution name in Fire Safety ≠ name in Affidavit ≠ name in application | Medium — fuzzy matching |

### Nice-to-Have USPs (If Time Permits)

| USP | Description | Difficulty |
|-----|-------------|-----------|
| 🌟 **Visual Evidence Overlay** | Show bounding boxes on the original document image highlighting extracted fields | Medium |
| 🌟 **Smart Document Type Detection** | Auto-classify document type from content instead of requiring user to select | Medium — needs LLM or classifier |
| 🌟 **Fuzzy Name Matching** | Use Levenshtein/Jaro-Winkler distance for institution name comparison instead of exact match | Low |
| 🌟 **Processing Pipeline Visualization** | Live progress: upload → OCR → extract → validate → report | Low-Medium |
| 🌟 **Compliance Score** | Numerical score (e.g., 85%) based on checks passed vs total | Low |
| 🌟 **PDF Summary Report** | Generate downloadable PDF report for the reviewer | Medium |
| 🌟 **Multi-Page OCR with Page Stitching** | Handle certificates that span multiple pages | Medium |
| 🌟 **Gemini Flash Integration** | Use Gemini Flash API for intelligent field extraction from complex/messy documents as fallback when PaddleOCR confidence is low | Medium-High |

### **Recommended High-Impact USP: Gemini Flash as Smart Fallback**
If PaddleOCR confidence < threshold on a field → call Gemini Flash Vision API with the document image + structured prompt → extract fields with higher accuracy. This gives you:
- An AI-powered differentiator (it's literally in the problem statement name)
- Better accuracy on messy scanned documents
- A talking point for judges: "We use a hybrid approach — rule-based OCR with AI fallback"

---

## 4. API Reference — Main Suggested & Alternatives

### 4.1 OCR / Text Extraction

| API/Library | Role | Pros | Cons | Recommendation |
|-------------|------|------|------|----------------|
| **PaddleOCR** (Main) | Text recognition from images | Free, offline, multi-language, good accuracy, required by project | Heavy dependency (PaddlePaddle), slow cold start | ✅ **Use as primary** |
| **Gemini Flash Vision** (Alt) | AI-based field extraction | Extremely accurate on complex layouts, understands context | API cost, needs internet, rate limits | 🌟 **Use as smart fallback** |
| **Tesseract OCR** (Alt) | Text recognition | Free, mature, well-documented | Lower accuracy on complex documents, no layout analysis | ❌ Not needed with PaddleOCR |
| **Google Cloud Vision API** (Alt) | Cloud OCR | High accuracy, document AI features | Paid, needs GCP account | ❌ Overkill for prototype |
| **Azure Document Intelligence** (Alt) | Document parsing | Pre-built models for certificates | Paid, vendor lock-in | ❌ Not suitable |

### 4.2 PDF Processing

| Library | Role | Pros | Cons | Recommendation |
|---------|------|------|------|----------------|
| **PyMuPDF (pymupdf)** (Main) | PDF text extraction + page rendering | Fast, extracts selectable text, renders pages to images | Large binary | ✅ **Use as primary** |
| **pdfplumber** (Alt) | PDF text + table extraction | Good table extraction | Slower, less reliable rendering | 🔄 Use if table extraction needed |
| **pdf2image + poppler** (Alt) | PDF to image conversion | Simple | Requires poppler system dependency | ❌ PyMuPDF handles this |

### 4.3 Backend Framework

| Framework | Role | Pros | Cons | Recommendation |
|-----------|------|------|------|----------------|
| **FastAPI** (Main) | REST API server | Async, auto-docs, Pydantic validation, Python native | Newer ecosystem | ✅ **Selected (locked in)** |
| **Django REST** (Alt) | Full-stack API | Mature, batteries included | Heavyweight for prototype | ❌ Not switching |
| **Flask** (Alt) | Lightweight API | Simple, flexible | No async, no auto-validation | ❌ FastAPI is better fit |

### 4.4 Database

| Database | Role | Pros | Cons | Recommendation |
|----------|------|------|------|----------------|
| **PostgreSQL** (Main) | Primary data store | JSONB support, robust, ACID | Requires setup | ✅ **Selected (locked in)** |
| **SQLite** (Alt) | Dev/testing | Zero setup, file-based | Not production-ready, no concurrent writes | 🔄 Use for local dev/tests if PG setup is slow |

### 4.5 AI / LLM APIs (for USP features)

| API | Role | Pros | Cons | Recommendation |
|-----|------|------|------|----------------|
| **Gemini Flash 2.0** (Main) | Smart field extraction fallback | Fast, cheap, vision capable, Google product | Needs API key, internet | 🌟 **Recommended for USP** |
| **Gemini Pro** (Alt) | Higher accuracy extraction | Most capable | Slower, more expensive | 🔄 For complex cases |
| **OpenAI GPT-4o** (Alt) | Vision + text understanding | Excellent vision, widely known | Expensive, non-Google | ❌ Prefer Gemini for SIH |
| **Claude Vision** (Alt) | Document understanding | Good at structured extraction | Less suitable for demo | ❌ Not needed |

### 4.6 Fuzzy Matching (for cross-document checks)

| Library | Role | Pros | Cons | Recommendation |
|---------|------|------|------|----------------|
| **rapidfuzz** (Main) | String similarity | Fast, C-based, multiple algorithms | Extra dependency | ✅ **Use for name matching** |
| **fuzzywuzzy** (Alt) | String similarity | Well-known | Slower (pure Python) | ❌ rapidfuzz is faster |
| **difflib** (Alt) | Built-in Python | No extra dependency | Basic, slower | 🔄 Use if avoiding deps |

### 4.7 Testing

| Tool | Role | Recommendation |
|------|------|----------------|
| **pytest** | Unit/integration tests | ✅ Primary |
| **pytest-asyncio** | Async test support | ✅ Required for FastAPI |
| **httpx** | Async HTTP test client | ✅ For API testing |
| **Faker** | Synthetic data generation | 🔄 Optional |

---

## 5. Person 2 (Aditya) Status — Detailed

### Branch: `remotes/origin/aditya-work`
- **Commits:** 1 ("Architecture")
- **Files changed:** Same as initial commit on main (docs + .gitkeep files)
- **Actual OCR code:** ❌ None
- **Extraction module:** ❌ Not started
- **Test results:** ❌ None

### What Person 3 Needs from Person 2

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Working PaddleOCR on 1 image | Proof OCR works | ❌ |
| `extract(file_path, doc_type) → ExtractionResult` | Callable function | ❌ |
| Error documentation | What errors can occur | ❌ |
| At least 1 sample extraction output | Matching API_CONTRACT.md §5 | ❌ |

### Risk Mitigation
Person 3 should:
1. Build entire backend with **mock extraction** that returns realistic synthetic data
2. Define the exact interface Person 2 must implement
3. Keep OCR integration as a thin adapter layer that can swap mock → real easily

---

## 6. Recommended Next Actions

1. **Immediately:** Share this analysis with the team. Confirm EoA + 3 document types
2. **Day 1:** Start backend scaffold (Person 3), start frontend scaffold (Person 1), start PaddleOCR setup (Person 2)
3. **Day 2:** Person 2 delivers proof-of-concept OCR on 1 image → Checkpoint 2
4. **Day 3:** Person 3 delivers working API → Checkpoint 3
5. **Day 4:** Integration begins
6. **Day 5-6:** End-to-end testing with synthetic data
7. **Day 7:** Demo rehearsal

> [!WARNING]
> Person 2's branch shows **zero implementation progress**. This is the #1 risk to the project. Coordinate immediately to ensure PaddleOCR setup begins today.
