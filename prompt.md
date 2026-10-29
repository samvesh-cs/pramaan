ROLE
You are a senior engineer planning (NOT yet implementing) a set of features for "Pramaan", an AICTE document-scrutiny platform (SIH 2026, PS 26261). Produce a detailed, multi-phase IMPLEMENTATION PLAN only. Do not write feature code in this step.

STEP 0 — MANDATORY RECON (before planning)
1. Read PROJECT_CONTEXT.md and the AICTE rulebook PDF (AICTE_rulebook.pdf, the Approval Process Handbook) fully. Also read the actual repository: backend (FastAPI), frontend (React+Vite), DB models/migrations, the existing rule engine, extraction code, auth, duplicate-detection code, and the 22 backend tests.
2. Output a short "Current State Map": modules, DB tables, API routes, rule-engine interface, finding/report schema, how duplicates are detected today, how auth/roles work. Mark anything you could not find as "UNKNOWN – needs confirmation" instead of guessing.
3. Do not assume file names, table names, or library versions. Verify them.

HARD CONSTRAINTS
- Do NOT break existing behaviour. All 22 backend tests, frontend lint and production build must still pass after every phase. Each phase must be independently mergeable and revertible.
- All DB changes are additive Alembic (or the repo's existing migration tool) migrations: nullable columns / new tables only, no destructive changes, with downgrade paths and backfill strategy for existing rows.
- Existing API responses stay backward compatible. New fields are optional. Version or flag anything that must change.
- Every new capability sits behind a feature flag / config setting, default OFF where it has external dependencies (LLM, pyHanko trust roots, models).
- Scanned-image OCR is currently UNVERIFIED (PaddleOCR is incompatible with the Python 3.14 interpreter). Plan nothing that silently depends on it. Design OCR-dependent parts (bounding boxes from OCR, QR from scans, ELA on scans) to degrade gracefully, and state this in the plan. Propose, but do not assume, a fix (e.g. pinning a Python 3.12 venv).
- Honest-claims rule: the system produces SIGNALS for human review, never "genuine/fraudulent" verdicts. All UI/report wording for tamper, signature, issuer and ELA results must say "signal, not proof" or equivalent. Final decisions stay with AICTE officials.
- Verdicts (pass/flag) are produced ONLY by the deterministic rule engine. An LLM may be used only for (a) field extraction assistance and (b) natural-language explanation. It must never decide pass/fail.
- No clause citation may be invented. Every clause reference must come from a clause registry built from the handbook PDF and be traceable to a page number. Any rule whose clause cannot be located in the PDF is marked "UNVERIFIED CITATION" in the plan, not silently filled in. (Note: the example "Annexure-2 §2.1(iv) Structural Stability Certificate if building >30 years" is illustrative from the product owner and must be verified against the PDF before use.)
- Security: no secrets in git; env-based config; uploaded PDFs are untrusted input (size/page limits, timeouts, no executing embedded content, safe handling of malicious/huge/encrypted PDFs).
- Privacy: cross-institution duplicate matches must not expose another institution's identity or documents to a non-privileged user. Define role-based visibility using the existing auth.

FEATURES TO PLAN

F1. Data-driven rule engine with clause citations
- Move rules into declarative data (YAML/JSON) validated by a schema (pydantic). Each rule: id, title, applies_to (application type/category, document type, state, conditions), check type, parameters, severity, and a mandatory `citation` {document, annexure/section/clause, page, quoted-summary paraphrase}.
- Keep the existing Python rules working: plan an adapter/legacy-wrapper so current rules run unchanged and are migrated one at a time with parity tests (same inputs -> same outcomes as before).
- Build a Clause Registry (clauses.json) generated from the PDF with a script plus manual review checklist; add a CI test that every rule's citation exists in the registry.
- Extend the Finding schema with optional: rule_id, clause_ref, severity, evidence (see F5), explanation, "signal_type" (rule | tamper | issuer | duplicate).
- Conditional rules (e.g. building age >30 years from completion date): specify date arithmetic, missing-date behaviour (result = "cannot evaluate", not pass), timezone/format handling, and leap-year/boundary tests.
- Edge cases: missing extracted fields, conflicting values across documents, unknown document types, applications of categories not in the rule set, rule config load errors (fail loudly at startup with clear message, not at request time), rule versioning (a stored report must record the ruleset version used).

F2. Tamper and authenticity signals (each is a separate pluggable "signal provider" with a common interface; failure of one must never fail the whole validation)
 a) PDF metadata forensics (PyMuPDF): modification date vs issue date, producer/creator anomalies, incremental saves/multiple %%EOF revisions, missing/stripped metadata, page-count/object oddities. Define a documented, configurable, conservative heuristic list and label weak signals as low severity. Handle PDFs with no metadata, malformed dates, and timezone formats.
 b) Digital signature validation with pyHanko: per-signature results (integrity, signer cert, validity period, revocation if feasible offline, coverage of whole document vs modified-after-signing). Be explicit about trust: without a configured trust store (e.g. Indian CCA roots), report "signature cryptographically intact / signer trust not established", never "valid and trusted". Handle unsigned PDFs (not an error; flag only where the handbook requires DSC), encrypted PDFs, multiple signatures, broken signatures, library exceptions. Check the handbook for exactly where DSC is required and cite it.
 c) QR/barcode decoding: render pages with PyMuPDF, decode with a library you justify (pyzbar/zxing-cpp/OpenCV; consider system-dependency/Windows install friction). Parse the payload, compare encoded certificate number/institution/date to extracted fields, and apply certificate-number format checks per issuer from a data file. No QR present = "not applicable", not a failure. Do not fetch URLs found in QR codes automatically (SSRF risk); propose an allow-list design only for the issuer-adapter in F3.
 d) Image checks (Error Level Analysis) for raster/scanned certificates only: Pillow-based, heatmap output, always labelled "signal, not proof", low confidence, off by default; document the known false-positive causes (re-compression, screenshots).
 e) Duplicate detection: review the existing implementation first and EXTEND it: file hash (SHA-256) and normalised certificate number across different institutions. Handle same-institution resubmission (not fraud), re-uploads of the same file after a rejected scan, certificate-number normalisation (case, spaces, hyphens, OCR confusions like O/0), and the privacy rules above. Plan an index and a backfill for existing documents.

F3. Competent-authority check (Annexure-14)
- Encode Annexure-14 (issuer authority per certificate type per state) as a data file extracted from the PDF with page citations; flag any rows that are ambiguous or unreadable.
- Define an IssuerVerificationAdapter interface (abstract base class/Protocol): input (state, certificate type, issuer text, certificate number, issue date), output (status: plausible | implausible | unknown | verified_by_authority, evidence, source, confidence). Provide: (1) a RuleBasedIssuerPlausibilityAdapter using Annexure-14 + fuzzy/alias matching, (2) a MockAuthorityAdapter clearly labelled MOCK in code, API and UI, (3) a documented stub showing how a real integration would plug in (config-selected via registry). Only the real adapter may ever output "verified_by_authority".
- Edge cases: state not determinable, issuer name variants/abbreviations/Hindi-Marathi transliteration, multiple valid authorities, central vs state authorities, unknown certificate type, adapter timeouts and errors (result = unknown, never crash).

F4. Policy-grounded Q&A (RAG over the handbook)
- Ingest the handbook PDF: chunk by clause/annexure using the Clause Registry (not naive fixed-size chunks), keep page + clause metadata. Choose and justify the embedding/vector store (prefer pgvector in the existing PostgreSQL, or a local lightweight option) and an LLM provider abstraction with config + API-key via env. Plan for the LLM being unavailable (feature disabled gracefully, retrieval-only fallback showing the matching clauses).
- Answer flow: retrieve clauses -> LLM drafts an explanation constrained to the retrieved text -> post-validate that every cited clause exists in the registry and appeared in the retrieved set; drop/flag any uncited claim. For application-specific questions ("is a structural stability certificate needed here?") the VERDICT must come from running the deterministic rule engine on that application's data; the LLM only explains it. Show a visible banner: "Verdicts are deterministic; AI only explains."
- Edge cases: out-of-scope questions, handbook version differences, prompt injection from uploaded documents (never feed raw uploaded document text into the LLM without treating it as untrusted data), cost/rate limiting, empty retrieval, conflicting clauses, citation to a clause not retrieved.
- Evaluation: a small golden Q&A set with expected clauses, and a test asserting citations are valid.

F5. Bounding boxes (evidence highlighting)
- For digital PDFs: use PyMuPDF word/line/block coordinates to locate extracted field values (institution name, dates, cert number). For OCR: store boxes from PaddleOCR when it works; otherwise absent.
- Store evidence as {document_id, page, bbox normalised 0-1 relative to the page, text, source: "text-layer"|"ocr", confidence}. Handle page rotation, CropBox/MediaBox offsets, multiple matches of the same string (pick by context; keep alternates), values split across lines, no match found (finding still shown, without a box), and scanned pages.
- Frontend: plan a PDF viewer overlay (e.g. react-pdf/pdf.js) with highlight rectangles linked from each finding; keyboard/mobile behaviour; large PDFs; lazy page rendering; colour/severity legend; a11y. Plan how this integrates with the existing report page without breaking it.
- Findings from F1-F4 should attach evidence boxes where applicable (e.g. QR location, signature field, mismatched institution name in two documents side by side).

REQUIRED PLAN OUTPUT FORMAT
1. Current State Map (from recon) + list of assumptions that need user confirmation.
2. Dependency/ordering rationale. Suggested phase order (you may improve it with reasons): Phase 0 safety net & baseline, Phase 1 Clause Registry + data-driven rule engine (+ legacy parity), Phase 2 Evidence/bounding boxes, Phase 3 Tamper signals (a->e as sub-phases), Phase 4 Issuer adapter, Phase 5 RAG, Phase 6 hardening/docs/demo.
3. For EACH phase: goal, files/modules to add or change, DB migrations (up/down), API changes (backward-compatible), frontend changes, new dependencies (with install/OS risks, e.g. Windows, Python 3.14 vs 3.12 compatibility), feature flag name, tests to add (unit/integration/regression, including fixture PDFs: unsigned, signed, tampered-after-signing, incremental-saved, QR-bearing, scanned, corrupted, encrypted, rotated), acceptance criteria, rollback plan, estimated effort, and "how this could break existing code and how it is prevented".
4. A consolidated Edge-Case Register (table: edge case | affected feature | expected behaviour | test).
5. A Risk Register including: false-positive risk of tamper signals, legal/ethical wording, LLM hallucination, performance (processing time per application, async/background jobs if needed), privacy of cross-institution data.
6. A "Claims we can honestly make in the demo" vs "Claims we must NOT make" list.
7. Open questions for the product owner (max 10), ranked by how much they block the plan.

STYLE
Be concrete and repo-specific. Do not pad. Where you are unsure, say so and propose how to verify. Do not start implementation until the plan is approved.