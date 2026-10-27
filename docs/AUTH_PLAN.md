# AUTH_PLAN.md — Authentication & Role-Based Authorization
## Pramaan · SIH 2026 PS 26261

**Status:** APPROVED — Implementation in progress.
**Branch:** `feature/auth`
**Date:** 2026-10-27

---

## 0. Baseline

### 0.1 Pre-implementation check results

```
Backend: 20/20 tests passing (test_applications, test_documents, test_validation, test_features_1_to_3)
Runtime: 137s (PaddleOCR model load included)
Frontend: lint clean, build clean (Vite)
```

Verified command:
```bash
# Backend (from backend/)
.venv\Scripts\python -m pytest tests/test_applications.py tests/test_documents.py \
  tests/test_validation.py tests/test_features_1_to_3.py -v
# Frontend
npm run lint && npm run build
```

---

## 1. Codebase Findings

### 1.1 Current endpoints — with planned access rules

| Method | Path | Current | Planned access rule |
|--------|------|---------|---------------------|
| GET | `/health` | Public | **Public** (always) |
| GET | `/docs`, `/redoc` | Public | **Dev-only** — hidden when `DEBUG=false` |
| POST | `/api/applications` | Open | **INSTITUTION only** |
| GET | `/api/applications` | Open | **INSTITUTION**: own apps · **REVIEWER**: submitted apps |
| GET | `/api/applications/{id}` | Open | **INSTITUTION**: own (404 for others) · **REVIEWER**: submitted |
| POST | `/api/applications/{id}/documents` | Open | **INSTITUTION**: own app only |
| GET | `/api/applications/{id}/documents` | Open | **INSTITUTION**: own · **REVIEWER**: submitted |
| GET | `/api/applications/{id}/documents/{doc_id}/file` | Open | **INSTITUTION**: own · **REVIEWER**: submitted |
| POST | `/api/applications/{id}/validate` | Open | **INSTITUTION**: own, any status |
| GET | `/api/applications/{id}/report` | Open | **INSTITUTION**: own · **REVIEWER**: submitted |
| PATCH | `/api/applications/{id}/findings/{finding_id}` | Open | **REVIEWER only** |
| POST | `/api/auth/register` | (new) | **Public** — INSTITUTION accounts only |
| POST | `/api/auth/login` | (new) | **Public** |
| POST | `/api/auth/refresh` | (new) | **Public** (cookie-based) |
| POST | `/api/auth/logout` | (new) | **Authenticated** |
| GET | `/api/auth/me` | (new) | **Authenticated** |
| POST | `/api/applications/{id}/submit` | (new) | **INSTITUTION**: own app |

### 1.2 Current models (all in `backend/app/models/`)

- **Application**: `id`, `institution_name`, `application_category`, `academic_year`, `overall_status`, `created_at`, `updated_at` — **no owner column**
- **Document**: `id`, `application_id (FK)`, `document_type`, filenames, `mime_type`, `file_size_bytes`, `processing_status`, `created_at`, `updated_at`
- **ExtractionRun**: linked to Document
- **Finding**: linked to Application + Document; includes `reviewer_decision`, `reviewer_notes`, `reviewed_by`, `reviewed_at`

### 1.3 Migration history

Alembic is configured (`backend/alembic/`, `alembic.ini`, `env.py` connected to `Base.metadata`). The `versions/` directory is **empty** — no migrations exist yet. All schema comes from `Base.metadata.create_all()` at startup. We will generate Alembic migrations for all auth changes.

### 1.4 Frontend API client

`frontend/src/api.js` — single `request(path, options)` helper, calls `fetch(${API_BASE_URL}/api${path}, options)`. No auth headers set anywhere. Dual-mode: real API or mock localStorage (`VITE_USE_MOCKS`). `react-router-dom` v7 already installed. No routing or auth context exists.

### 1.5 Test infrastructure

`tests/conftest.py` uses `sqlite+aiosqlite:///:memory:`, overrides `get_db` via `app.dependency_overrides`, provides async `client` fixture. All existing tests use the unauthenticated `client`. The override strategy is the correct hook point for auth dependency overrides in tests.

---

## 2. Design Decisions

### 2.1 Password hashing

**Recommendation: `bcrypt` via `passlib[bcrypt]`** with `rounds=12` (~250ms hash time).

Argon2 is marginally stronger, but bcrypt at cost 12 is more than adequate for a prototype. `passlib` provides a clean upgrade path. Smallest footprint, most battle-tested in Python web apps.

### 2.2 JWT strategy

**Access token:** Short-lived JWT (HS256, `python-jose[cryptography]`), default 15-minute expiry (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`), signed with `JWT_SECRET_KEY` from env.
Payload: `{ sub: user_id, role: "INSTITUTION"|"REVIEWER", iat, exp }`.
Role is embedded in the token; `is_active` is always checked against the DB on every request.

**Refresh token:** 7-day opaque UUID stored as SHA-256 hash in `refresh_tokens` table. Delivered in an `httpOnly; SameSite=Lax; Secure` cookie named `pramaan_refresh`. Rotated on every use.

**Rejected alternative:** Longer-lived access tokens only (no refresh). Rejected because deactivating a user must take effect immediately — the DB check on every short-lived access token achieves this.

### 2.3 Token storage on the frontend

**In-memory access token (React Context), httpOnly cookie for refresh token.**

- Access token in React Context module variable — never written to `localStorage`/`sessionStorage` (eliminates XSS theft).
- On page refresh: frontend calls `POST /api/auth/refresh` (sends cookie automatically) → receives new access token in response body.
- `localStorage` NOT used for auth tokens. Existing `pramaan-demo-applications-v1` keys are unrelated to auth and only active when `VITE_USE_MOCKS=true`.

### 2.4 CORS / cookie / CSRF settings

| Environment | `allow_credentials` | SameSite | Secure | Notes |
|-------------|--------------------|-----------|----|-------|
| Local dev (HTTP) | true | Lax | omit | Vite at `localhost:5173` → backend at `localhost:8000` |
| Production (HTTPS) | true | Lax | true | Same domain preferred |

`SameSite=Lax` prevents CSRF for cookie-based auth — cross-site POST requests do not send the cookie. No separate CSRF token needed. Controlled by `COOKIE_SECURE` env var.

### 2.5 Data model — new tables

**`users`**
```sql
id              VARCHAR(36)   PRIMARY KEY          -- UUID
email           VARCHAR(255)  UNIQUE NOT NULL       -- stored lowercase, stripped
password_hash   VARCHAR(255)  NOT NULL
role            VARCHAR(20)   NOT NULL              -- CHECK IN ('INSTITUTION','REVIEWER')
is_active       BOOLEAN       NOT NULL DEFAULT TRUE
created_at      DATETIME      NOT NULL
last_login_at   DATETIME      NULL
```

**`institutions`** (one per user, thin profile)
```sql
id              VARCHAR(36)   PRIMARY KEY
user_id         VARCHAR(36)   FK → users.id  UNIQUE   -- one institution per user
display_name    VARCHAR(500)  NOT NULL
created_at      DATETIME      NOT NULL
```

**`refresh_tokens`**
```sql
id              VARCHAR(36)   PRIMARY KEY
token_hash      VARCHAR(64)   UNIQUE NOT NULL  -- SHA-256 of raw token; breach-safe
user_id         VARCHAR(36)   FK → users.id  ON DELETE CASCADE
expires_at      DATETIME      NOT NULL
revoked         BOOLEAN       NOT NULL DEFAULT FALSE
created_at      DATETIME      NOT NULL
```

**`applications` — two additive columns:**
```sql
owner_id        VARCHAR(36)   NULL  FK → users.id ON DELETE SET NULL
status          VARCHAR(20)   NOT NULL DEFAULT 'draft'  -- 'draft'|'submitted'
```

`owner_id` is NULL for legacy rows until the backfill seed runs.

### 2.6 Authorization dependencies (FastAPI)

All in `backend/app/auth/dependencies.py` — no scattered if-checks in routes:

```python
get_current_user(token, db) -> User
  # Decodes JWT, rejects "alg:none", checks is_active in DB. Raises 401 on failure.

require_role(*roles) -> Callable
  # Depends on get_current_user, checks role. Raises 403 if wrong role.

require_application_access(application_id, current_user, db) -> Application
  # INSTITUTION: fetch where owner_id == user.id (else 404 — no existence leak)
  # REVIEWER: fetch where status == 'submitted' (else 404)
```

### 2.7 Reviewer account creation

**No public reviewer registration.** Only via:
1. Idempotent seed script `backend/scripts/seed_reviewer.py` reading `REVIEWER_EMAIL` + `REVIEWER_PASSWORD` from env. Safe to run twice (`ON CONFLICT DO NOTHING`).
2. `POST /api/auth/register` hardcodes `role = "INSTITUTION"` — ignores any `role` field in body (mass-assignment protection).

---

## 3. Migration and Backfill

### 3.1 Strategy

Generate two Alembic migrations:
- **Migration 001** (`baseline_schema`): captures the existing schema (applications, documents, extractions, findings) as a baseline.
- **Migration 002** (`auth_tables`): adds `users`, `institutions`, `refresh_tokens` tables; adds `owner_id` (nullable) and `status` (default `'draft'`) to `applications`.

Both nullable/defaulted — zero data loss, zero application breakage on apply.

### 3.2 Backfill

```
Seed script: seed_demo_institution.py
1. Upsert demo institution user (from DEMO_INSTITUTION_EMAIL + DEMO_INSTITUTION_PASSWORD env vars)
2. Upsert institutions row for that user
3. UPDATE applications SET owner_id = <demo_user_id>, status = 'draft' WHERE owner_id IS NULL
```

All existing data (applications, documents, uploads) remains accessible via the demo institution account.

### 3.3 Uploaded files

Files under `backend/uploads/` are accessed via `document_service.get_document_file()` which constructs paths from DB `stored_filename` (UUID-based server-generated name). No user-controlled path component. Auth is enforced before the DB lookup in the dependency chain.

---

## 4. Phased Rollout

> **Rule:** Run full backend test suite after every backend commit. Frontend lint + build after every frontend commit. No merge to main unless all green.

### Phase A — Baseline + new tables (no behavior change)

| # | Commit | Verification command |
|---|--------|---------------------|
| A1 | `feat(auth): alembic migration 001 baseline_schema` | `alembic upgrade head; alembic downgrade -1; pytest (20 green)` |
| A2 | `feat(auth): User, Institution, RefreshToken models + migration 002_auth_tables` | `alembic upgrade head; alembic downgrade -1; pytest (20 green)` |
| A3 | `feat(auth): JWT_SECRET_KEY + auth env vars in config + .env.example; fail-fast guard` | `pytest (20 green)` |

### Phase B — Auth endpoints + tests (existing endpoints unchanged)

| # | Commit | Verification command |
|---|--------|---------------------|
| B4 | `feat(auth): JWT helpers + password hashing (app/auth/jwt.py, app/auth/password.py)` | `pytest tests/test_auth_helpers.py` |
| B5 | `feat(auth): auth service + schemas (app/services/auth_service.py, app/schemas/auth.py)` | Import clean |
| B6 | `feat(auth): auth router (register, login, refresh, logout, me) + mount in routes/__init__.py` | `pytest (20 + new auth green)` |
| B7 | `test(auth): full auth endpoint tests (tests/test_auth.py)` | `pytest tests/test_auth.py` |
| B8 | `chore: seed scripts (seed_reviewer.py, seed_demo_institution.py)` | Run twice — idempotent |

### Phase C — Enforce auth endpoint by endpoint

Before each commit: update affected existing tests to use `institution_client` fixture. Assertion logic unchanged.

| # | Commit | Verification command |
|---|--------|---------------------|
| C9 | `feat(auth): protect POST /applications` + tests | Full pytest suite |
| C10 | `feat(auth): protect GET /applications + GET /{id}` + tests | Full pytest suite |
| C11 | `feat(auth): protect POST + GET /documents` + tests | Full pytest suite |
| C12 | `feat(auth): protect GET /documents/{id}/file` + tests | Full pytest suite |
| C13 | `feat(auth): protect POST /validate + GET /report` + tests | Full pytest suite |
| C14 | `feat(auth): protect PATCH /findings/{id} (REVIEWER only)` + tests | Full pytest suite |
| C15 | `feat(auth): add POST /applications/{id}/submit` + tests | Full pytest suite |
| C16 | `test(auth): IDOR + enforcement tests (test_auth_enforcement.py)` | Full pytest suite |

**conftest.py additions:**
```python
@pytest_asyncio.fixture
async def institution_client(client):
    from app.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: FakeUser(role="INSTITUTION", id="inst-1", is_active=True)
    yield client
    app.dependency_overrides.pop(get_current_user, None)

@pytest_asyncio.fixture
async def reviewer_client(client):
    from app.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: FakeUser(role="REVIEWER", id="rev-1", is_active=True)
    yield client
    app.dependency_overrides.pop(get_current_user, None)
```

### Phase D — Frontend

| # | Commit | Verification command |
|---|--------|---------------------|
| D17 | `feat(frontend): AuthContext + ProtectedRoute` | `npm run lint && npm run build` |
| D18 | `feat(frontend): LoginPage + RegisterPage` | `npm run lint && npm run build` |
| D19 | `feat(frontend): role-based nav + 401/403 handling + single-flight refresh` | `npm run lint && npm run build` |
| D20 | `feat(frontend): logout clears all state + BroadcastChannel tab sync` | `npm run lint && npm run build` |

### Phase E — Seeds, docs, final regression

| # | Commit | Verification command |
|---|--------|---------------------|
| E21 | `chore: .env.example with all auth vars + demo credentials` | Review file |
| E22 | `docs: README auth setup + seed commands + demo login section` | Review |
| E23 | `docs: PROJECT_CONTEXT.md + DECISIONS.md move auth to in-scope` | Review |
| E24 | Final regression | `pytest (all ~102 green); npm run lint; npm run build` |

---

## 5. Edge Case Matrix

### Authentication

| Case | Expected behavior | How tested |
|------|------------------|------------|
| Wrong password | `401 {code:"INVALID_CREDENTIALS", message:"Invalid email or password."}` — identical wording for wrong password AND unknown email (no user enumeration) | `test_auth.py::test_wrong_password`, `test_unknown_email` |
| Unknown email | Same 401 + same timing (bcrypt.checkpw on dummy hash prevents timing oracle) | `test_auth.py::test_unknown_email` |
| Email case/whitespace variants | Normalized to lowercase + stripped before storage and lookup | `test_auth.py::test_email_normalization` |
| Duplicate registration (race) | First → 201. Second (including concurrent) → catch `IntegrityError` → 409 `EMAIL_ALREADY_REGISTERED`. Never 500. | `test_auth.py::test_duplicate_registration` |
| Weak/empty/very long password | 422 `VALIDATION_FAILED`; min 8, max 128 chars enforced in `RegisterRequest` Pydantic schema | `test_auth.py::test_password_validation` |
| Unicode credentials | Accepted; Pydantic `EmailStr` validates; bcrypt handles unicode passwords | `test_auth.py::test_unicode_credentials` |
| Malformed email | 422 `VALIDATION_FAILED` | Schema-level |
| Request body > limit | FastAPI default 1MB for JSON; document in config comments | Config note |
| Brute force: > 5 failed logins/IP/5min | 429 `RATE_LIMITED`. `slowapi` with `InMemoryRateLimiter`. `RATE_LIMIT_ENABLED` env flag (default `true`; set `false` in tests). | `test_auth.py::test_brute_force_lockout` |
| Expired access token | `get_current_user` raises 401 `TOKEN_EXPIRED` | `test_auth_helpers.py` + `freezegun` |
| Malformed token | 401 `INVALID_TOKEN` | `test_auth_helpers.py` |
| Tampered token | Signature fails → 401 `INVALID_TOKEN` | `test_auth_helpers.py` |
| `alg: none` attack | `decode_access_token` uses `algorithms=["HS256"]` — python-jose rejects `alg:none` | `test_auth_helpers.py::test_alg_none_attack` |
| Wrong secret | Signature fails → 401 | `test_auth_helpers.py` |
| Deactivated user | `get_current_user` checks `user.is_active` in DB on **every** request → 401 `ACCOUNT_DEACTIVATED` immediately | `test_auth.py::test_deactivated_user` |
| Refresh token reuse | Old token revoked on rotation; re-use → 401 `REFRESH_TOKEN_REVOKED` | `test_auth.py::test_refresh_rotation` |
| Logout + subsequent refresh | `POST /logout` sets `revoked=TRUE`; subsequent refresh → 401 | `test_auth.py::test_logout_invalidates_refresh` |
| Clock skew | `python-jose` `options={"leeway":10}` — 10-second tolerance | Unit test |
| Missing Authorization header | 401 with `WWW-Authenticate: Bearer` | `test_auth.py::test_no_auth_header` |
| Invalid header format | 401 `INVALID_TOKEN` | `test_auth.py::test_invalid_auth_header` |

### Authorization

| Case | Expected behavior | How tested |
|------|------------------|------------|
| IDOR: institution A → B's application | **404** (not 403) — does not reveal existence | `test_auth_enforcement.py::test_idor_application` |
| IDOR: nested resources (document, file, report, finding) | **404** at each level | `test_auth_enforcement.py::test_idor_nested_*` |
| IDOR: list endpoints | Institution A's list never contains B's apps | `test_auth_enforcement.py::test_list_scoped` |
| Client sends `role`/`owner_id` in request body | Ignored — not present in `RegisterRequest` / `ApplicationCreate` schemas (`extra="ignore"`) | Schema-level, no handler code needed |
| Reviewer tries `POST /applications` | 403 `FORBIDDEN` | `test_auth_enforcement.py` |
| Reviewer tries `POST /documents` | 403 | `test_auth_enforcement.py` |
| Institution tries `PATCH /findings/{id}` | 403 | `test_auth_enforcement.py` |
| Reviewer sees DRAFT applications | **No** — reviewer queries filter `status='submitted'`; drafts return 404 | `test_auth_enforcement.py::test_reviewer_no_draft` |
| Institution edits after submit | `status='submitted'` is locked: `POST /documents` and `POST /validate` return 409 `APPLICATION_LOCKED` | `test_auth_enforcement.py::test_locked_application` |
| Who triggers validation | **INSTITUTION only**, own app, any status | `test_auth_enforcement.py` |
| Token expires mid-validation | Validation is synchronous; result stored in DB. Client gets 401 on **next** request, not mid-flight. Documented. | Manual test note |
| Public endpoints stay public | `/health`, `/docs` (debug), `/redoc` (debug) — no auth required | `test_auth.py::test_public_endpoints` |
| `/docs` in production | `docs_url=None, redoc_url=None` when `DEBUG=False` | Config test |

### Data and Migration

| Case | Expected behavior | How tested |
|------|------------------|------------|
| Existing rows with no owner | `owner_id=NULL`; backfill script assigns demo institution | Seed script + manual |
| `alembic upgrade head` run twice | No-op (already at head) — idempotent | CI |
| `alembic downgrade -1` | Reverses migration cleanly | Documented command |
| Seed script run twice | `ON CONFLICT DO NOTHING` — no duplicates, no error | `test_auth.py::test_seed_idempotency` |
| Orphaned uploads on disk | Pre-existing; no new orphans after auth (files tied to owned apps) | n/a |
| Filename path traversal | `document_service.get_document_file()` uses server-set UUID filenames; no user-controlled path | Code review + existing tests |
| Auth checked before file access | `require_application_access` dependency runs before handler body | Dependency injection order |

### Frontend

| Case | Expected behavior | How tested |
|------|------------------|------------|
| Token expiry during long upload | 401 → interceptor calls `POST /refresh` → retry original request. If refresh fails: clean logout + redirect to `/login?returnUrl=<current>` | `AuthContext` unit test with mocked fetch |
| Many concurrent 401s | Promise-based mutex: first 401 starts refresh; others await same promise (single-flight) | `AuthContext` unit test |
| Refresh failure | Clears in-memory token, calls `POST /logout`, redirects to login with return URL | Manual test |
| Logout clears all state | Clears auth context, clears mock localStorage keys, clears cached responses. Next user sees no previous data. | Manual + BroadcastChannel test |
| Browser back after logout | `ProtectedRoute` re-checks auth on each render → redirect to login | Manual |
| Logout/login in another tab | `BroadcastChannel("pramaan_auth")`: `"logout"` message → all tabs log out; `"login"` → re-check session | `AuthContext` unit test |
| Page refresh keeps session | `AuthContext.useEffect` calls `POST /refresh` on mount; if cookie valid → session restored | `test_auth.py::test_session_restore` |
| Wrong-role direct URL | `ProtectedRoute` checks `user.role`; wrong role → 403 page with redirect | Manual |
| Loading state (no flash) | `AuthContext` exposes `isLoading`; `ProtectedRoute` shows spinner until `isLoading=false` | Component test |
| Network error vs auth error | `TypeError` (network) → show "Cannot reach API" toast, do NOT log out. `response.status===401` → trigger refresh flow. | `api.js` unit test |

### Operations

| Case | Expected behavior | How tested |
|------|------------------|------------|
| Missing `JWT_SECRET_KEY` in production | `Settings` validator raises `ValueError` at startup — app refuses to start | `test_auth.py::test_startup_fails_without_secret` |
| Default/weak `JWT_SECRET_KEY` | Log `CRITICAL` warning in dev; block startup in production | Config validator |
| CORS with credentials | `allow_credentials=True` + explicit origins (no wildcard) — already in place | Existing CORS config |
| HTTP vs HTTPS cookie flags | `COOKIE_SECURE=false` in dev (HTTP OK); `COOKIE_SECURE=true` in prod | `.env.example` |
| UI error messages | Generic user-facing messages only. No stack traces, no internals. | Frontend component test |

---

## 6. Test Plan

### New packages (add to `requirements.txt`)

```
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
slowapi>=0.1.9
freezegun>=1.5.0
```

### New test files

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_auth_helpers.py` | ~12 | `hash_password`, `verify_password`, `create_access_token`, `decode_access_token` (valid, expired, malformed, alg-none, tampered, wrong-secret) |
| `tests/test_auth.py` | ~40 | All auth endpoints × role × state — see §5 Authentication rows |
| `tests/test_auth_enforcement.py` | ~30 | Every existing endpoint × (anonymous, institution-owner, other-institution, reviewer, deactivated) |

### Expected test count summary

| Suite | Before | After Phase E |
|-------|--------|---------------|
| `test_applications.py` | 6 | 6 (fixture updated, assertions unchanged) |
| `test_documents.py` | 4 | 4 (fixture updated) |
| `test_validation.py` | 6 | 6 (fixture updated) |
| `test_features_1_to_3.py` | 4 | 4 (fixture updated) |
| `test_auth_helpers.py` | 0 | ~12 |
| `test_auth.py` | 0 | ~40 |
| `test_auth_enforcement.py` | 0 | ~30 |
| **Total** | **20** | **~102** |

**Existing tests are never deleted or weakened.** Only the fixture (`client` → `institution_client`) changes in Phase C; all assertion logic is preserved.

---

## 7. Audit / Logging

Minimal hooks added in `backend/app/auth/audit.py` (Phase B):

```python
audit_logger = logging.getLogger("pramaan.audit")  # structured JSON to stdout

def log_login_success(user_id, email, ip): ...
def log_login_failure(email, ip, reason): ...      # reason: wrong_password, unknown_email, deactivated, rate_limited
def log_auth_denial(user_id, path, method): ...
def log_reviewer_access(reviewer_id, application_id, action): ...
```

**What is logged:** `user_id`, `email` (failures only), IP, timestamp, path, action, HTTP status.  
**What is NEVER logged:** passwords, tokens, token hashes, document content, PII beyond email.

Ready to plug into a future audit-history DB table without further changes.

---

## 8. Explicitly Out of Scope (Prototype Assumptions)

| Item | Prototype mock |
|------|---------------|
| Real AICTE SSO / SAML / OAuth | Username/password only |
| DigiLocker integration | Not implemented |
| DSC / Aadhaar login | Not implemented |
| Real email sending (verification, password reset) | `audit_logger.info("STUB_EMAIL: ...")` — logged, not sent |
| Approval/rejection decisions by reviewers | Reviewers record `reviewer_decision` on findings only; no "approve application" action |
| Admin role or admin UI | Reviewer seed via CLI script only |
| Multi-factor authentication | Single factor (password) only |

---

## 9. Risks, Open Questions, and Checklist

### Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `slowapi` in-memory limiter resets on restart | Low (prototype) | Document; use Redis in production |
| httpOnly cookie adds frontend complexity | Medium | Auth context + single-flight pattern is well-documented |
| Alembic autogenerate produces wrong schema | Low | Always review generated file before committing; test upgrade + downgrade |
| Phase C fixture changes inadvertently weaken tests | Medium | Review every assertion in affected tests line-by-line before committing |

### Resolved Design Decisions

| ID | Decision / Question | Resolved Answer |
|----|---------------------|-----------------|
| Q-AUTH-01 | One institution per user, or many? | **One institution per user account** |
| Q-AUTH-02 | After submit: fully locked or still editable? | **Locked till reviewer validates, and based on the report they can create new application of the same report with changes** |
| Q-AUTH-03 | Reviewer creation method | **One-time admin setup route** (`POST /api/auth/admin/setup`) protected by `ADMIN_SETUP_TOKEN` + CLI seed script |
| Q-AUTH-04 | Access token lifetime | **60 min default** (`ACCESS_TOKEN_EXPIRE_MINUTES=60` for better demo UX) |
| Q-AUTH-05 | `/docs` and `/redoc` security | **Hidden when `DEBUG=false`, open when `DEBUG=true`** |
| Q-AUTH-06 | Rate limiting | **Rate limiting enabled in prod, disabled in test environment (`RATE_LIMIT_ENABLED`)** |

### Step-by-Step Commit Checklist

```
[ ] Phase A — new tables, no behavior change
    [ ] A1: alembic revision --autogenerate "baseline_schema" → review → commit
            Verify: alembic upgrade head; alembic downgrade -1; pytest (20 green)
    [ ] A2: User, Institution, RefreshToken models + alembic migration 002_auth_tables
            Verify: alembic upgrade head; alembic downgrade -1; pytest (20 green)
    [ ] A3: JWT_SECRET_KEY + auth env vars in config + .env.example + fail-fast startup guard
            Verify: pytest (20 green)

[ ] Phase B — auth endpoints, existing endpoints unchanged
    [ ] B4: JWT helpers + password hashing (app/auth/jwt.py, app/auth/password.py)
            Verify: pytest tests/test_auth_helpers.py (all green)
    [ ] B5: auth service + schemas
            Verify: import clean, no errors
    [ ] B6: auth router + mount in routes/__init__.py
            Verify: pytest (20 + new auth green)
    [ ] B7: test_auth.py (full auth tests)
            Verify: pytest tests/test_auth.py (all green)
    [ ] B8: seed_reviewer.py + seed_demo_institution.py
            Verify: run twice — idempotent, no errors

[ ] Phase C — enforce auth endpoint by endpoint, full suite after each
    [ ] C9:  protect POST /applications — update test fixture; full pytest
    [ ] C10: protect GET /applications + GET /{id}; full pytest
    [ ] C11: protect POST + GET /documents; full pytest
    [ ] C12: protect GET /documents/{id}/file; full pytest
    [ ] C13: protect POST /validate + GET /report; full pytest
    [ ] C14: protect PATCH /findings/{id} (REVIEWER only); full pytest
    [ ] C15: add POST /applications/{id}/submit; full pytest
    [ ] C16: test_auth_enforcement.py (IDOR + role tests); full pytest (~102 green)

[ ] Phase D — frontend auth
    [ ] D17: AuthContext + ProtectedRoute; npm run lint && npm run build
    [ ] D18: LoginPage + RegisterPage; npm run lint && npm run build
    [ ] D19: role-based nav + 401/403 + single-flight refresh; npm run lint && npm run build
    [ ] D20: logout clears state + BroadcastChannel; npm run lint && npm run build

[ ] Phase E — polish, seeds, docs
    [ ] E21: .env.example with all auth vars + demo credentials
    [ ] E22: README auth setup + seed commands + demo logins
    [ ] E23: PROJECT_CONTEXT.md + DECISIONS.md move auth to in-scope
    [ ] E24: Final regression: pytest (~102 green); npm run lint; npm run build
             Record: "Final: N tests passing. Lint: clean. Build: clean."
```

---

## 10. Suggested Doc Edits (NOT applied — suggestions only, pending approval)

### `docs/PROJECT_CONTEXT.md` — Section 7 (Out of scope)

Remove:
> `Authentication/role-based access unless explicitly required by the demo environment.`

Add to Section 4 (MVP features — in scope):
> - JWT-based authentication with two roles: INSTITUTION (creates and manages own applications) and REVIEWER (read-only access to submitted applications, records reviewer decisions). Reviewer accounts are seeded via CLI — no self-registration.

Add new Section 7a:
> **7a. Authentication and roles (in scope as of 2026-10-27)**
> See `docs/AUTH_PLAN.md` for the full design and phased implementation plan. See `docs/DECISIONS.md` D-014.

### `docs/DECISIONS.md` — Add D-014

```markdown
### D-014 — Authentication and role-based access
**Status:** Accepted (pending AUTH_PLAN.md approval)
**Decision:** JWT-based authentication with INSTITUTION and REVIEWER roles.
INSTITUTION users self-register; REVIEWER accounts are seeded via idempotent CLI script.
Short-lived access tokens (HS256); refresh token in httpOnly cookie; is_active checked on
every request so deactivation takes effect immediately.
**Reference:** docs/AUTH_PLAN.md
**Date / Owner:** 2026-10-27 / Full-stack review
```

---

*End of AUTH_PLAN.md. Awaiting explicit approval before Phase 2 (implementation).*
