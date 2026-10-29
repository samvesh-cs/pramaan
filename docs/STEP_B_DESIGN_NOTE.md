# Step B Design Note: Declarative Engine Cutover, Three-Valued Logic & Parity

## 1. Overview
This design note documents the architecture, logic semantics, schema migration, fallback behavior, and verification harness for Step B (Declarative Cutover) under SIH 2026 Problem Statement 26261. Step B establishes complete legacy parity for the declarative engine without altering the default system behavior (`RULE_ENGINE_MODE` defaults to `"legacy"`).

---

## 2. Condition Grammar and Schema
Rule conditions are declarative ASTs validated via Pydantic models in `backend/app/schemas/rule_definition.py`:
- **Recursive Nesting Depth:** Restricted to $\le 3$ levels (`get_depth()` validator per D-017).
- **Compound Operators:**
  - `all_of: list[RuleCondition]` (Kleene AND)
  - `any_of: list[RuleCondition]` (Kleene OR)
  - `not_: RuleCondition` (Kleene NOT)
- **Atomic Operators:**
  - `exists` / `not_exists` (Presence of document or field)
  - `equals` / `not_equals` (Exact match)
  - `greater_or_equal` / `less_or_equal` / `greater_than` / `less_than` (Numeric comparisons)
  - `date_not_expired` (Compares date against application cutoff date)
  - `date_lte_years` / `date_gte_years` (Calendar year / anniversary comparisons)
  - `fuzzy_similarity` (Text similarity compared against configurable `settings.NAME_SIMILARITY_THRESHOLD`)
  - `custom` (Advisory handler for domain checks like TER payment amounts)
- **Branch Outcomes:** Rules with complex branching define `branches: list[RuleBranch]`, where each branch has a condition and an outcome (`pass`, `flagged`, `unresolved`), mapping to finding statuses.

---

## 3. Three-Valued Kleene Logic Truth Tables
Conditions evaluate strictly to `TRUE`, `FALSE`, or `UNKNOWN`.
Any missing document/field, unparseable date, or extraction confidence $< 0.70$ evaluates to `UNKNOWN` (never `pass`).

### 3.1 Logical AND (`all_of`)
| Operand A | Operand B | $A \land B$ |
| :--- | :--- | :--- |
| **TRUE** | **TRUE** | **TRUE** |
| **TRUE** | **FALSE** | **FALSE** |
| **TRUE** | **UNKNOWN** | **UNKNOWN** |
| **FALSE** | **TRUE** | **FALSE** |
| **FALSE** | **FALSE** | **FALSE** |
| **FALSE** | **UNKNOWN** | **FALSE** |
| **UNKNOWN** | **TRUE** | **UNKNOWN** |
| **UNKNOWN** | **FALSE** | **FALSE** |
| **UNKNOWN** | **UNKNOWN** | **UNKNOWN** |

### 3.2 Logical OR (`any_of`)
| Operand A | Operand B | $A \lor B$ |
| :--- | :--- | :--- |
| **TRUE** | **TRUE** | **TRUE** |
| **TRUE** | **FALSE** | **TRUE** |
| **TRUE** | **UNKNOWN** | **TRUE** |
| **FALSE** | **TRUE** | **TRUE** |
| **FALSE** | **FALSE** | **FALSE** |
| **FALSE** | **UNKNOWN** | **UNKNOWN** |
| **UNKNOWN** | **TRUE** | **TRUE** |
| **UNKNOWN** | **FALSE** | **UNKNOWN** |
| **UNKNOWN** | **UNKNOWN** | **UNKNOWN** |

### 3.3 Logical NOT (`not`)
| Operand A | $\neg A$ |
| :--- | :--- |
| **TRUE** | **FALSE** |
| **FALSE** | **TRUE** |
| **UNKNOWN** | **UNKNOWN** |

### 3.4 Rule Outcome Mapping
- `TRUE` $\rightarrow$ `pass`
- `FALSE` $\rightarrow$ `flagged` (or branch-specific outcome)
- `UNKNOWN` $\rightarrow$ `unresolved`

---

## 4. Dialect-Neutral Alembic Migration
Migration `backend/alembic/versions/b4c1a2d3e5f6_step_b_ruleset_version.py` adds additive nullable columns using `op.batch_alter_table`:
- **`findings` table:**
  - `advisory`: `Boolean`, nullable=True, server_default='0'
  - `ruleset_version`: `String(64)`, nullable=True
  - `rule_engine_mode`: `String(32)`, nullable=True
- **`applications` table:**
  - `ruleset_version`: `String(64)`, nullable=True
  - `rule_engine_mode`: `String(32)`, nullable=True

### Migration Invariance
- Uses `batch_alter_table` to guarantee SQLite table rebuild support as well as PostgreSQL `ALTER TABLE`.
- Pre-existing rows contain `NULL` for `ruleset_version` and serialize as `"Legacy ruleset"` in API responses.
- *Note:* Verified and tested on SQLite; PostgreSQL dialect execution is untested in this environment.

---

## 5. Per-Request Mode Inspection and Fallback Behavior
- **Dynamic Configuration:** In `ValidationEngine.validate_application`, `settings.RULE_ENGINE_MODE` is inspected per-request.
- **Fail-Safe Fallback:** When `RULE_ENGINE_MODE == "declarative"`:
  ```python
  try:
      raw_findings = default_declarative_engine.evaluate(context)
  except Exception as exc:
      failed_rule_id = getattr(exc, "rule_id", "DECLARATIVE_ENGINE")
      logger.warning(
          "DECLARATIVE_FALLBACK: application_id=%s rule_id=%s error=%s",
          application_id, failed_rule_id, type(exc).__name__
      )
      # Execute legacy rules for this request
      raw_findings = [r for rule in self.rules for r in rule.evaluate(context)]
      effective_mode = "legacy"
  ```
- **Guarantees:**
  - Fallback logs contain zero document text or extracted values (preventing information leakage).
  - Clean transaction management: previous findings are deleted before evaluation; fallback generates exact legacy finding set with no duplicates or partial writes.
  - Endpoint returns HTTP 200 normal report, never HTTP 500.

---

## 6. Replay and Parity Harness Design
The harness (`backend/app/rules/parity_harness.py`) executes both engines side-by-side:
1. **Sources:**
   - (a) Full synthetic scenario dataset from `backend/tests/demo_samples/manifest.json`.
   - (b) All stored applications in the dev database (`sih_prototype.db` opened read-only).
   - (c) B2 boundary fixtures (confidence thresholds 0.70/0.699/0.701, expiry equal to cutoff, building age 30y/30y+1d, Feb 29 leap years, empty/whitespace, Unicode Hindi names).
2. **Comparison:**
   - Evaluates rule-by-rule status (`pass`, `flagged`, `missing`, `unresolved`, `not_applicable`) and advisory metadata.
3. **Allow-List Gating:**
   - Any status mismatch produces a `Discrepancy`.
   - If a discrepancy is not in `ALLOW_LIST`, or if an `ALLOW_LIST` entry lacks a written justification ($\ge 10$ characters), the harness exits non-zero (exit code 1).

