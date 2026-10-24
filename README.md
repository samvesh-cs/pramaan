# SIH 2026 PS 26261 — Application Validation & Document Compliance Verification

Shared project documentation for the SIH 2026 Problem Statement 26261 prototype.

## Files
- `AGENTS.md` — shared instructions for AI coding agents and module ownership.
- `docs/PROJECT_CONTEXT.md` — project purpose, MVP scope, workflow, and limitations.
- `docs/API_CONTRACT.md` — shared API shapes and integration rules.
- `docs/TASKS.md` — workstream checklists and integration checkpoints.
- `docs/DECISIONS.md` — accepted technical decisions and open scope questions.

## Project scope
The prototype supports preliminary scrutiny of institutional applications using synthetic data. It extracts selected document fields, runs explicit validation rules, and presents evidence-linked findings for human review. It does not make final AICTE approval decisions or prove document authenticity.

## Selected stack
React + Vite + Tailwind CSS; Python + FastAPI; PaddleOCR; PyMuPDF; PostgreSQL; custom Python validation rules.
