# HiRo Implementation Roadmap

**Goal:** take HiRo from "boots end-to-end, many capabilities mocked" to a genuinely functional, secure, local-first HR platform — without ever breaking the running stack.

This roadmap is honest about the current state: the platform runs, the portals and APIs are wired, but a meaningful slice of "AI" is deterministic heuristics or mock data behind graceful-degradation stubs. Each phase below turns one slice real.

**Legend:** ✅ done · 🟡 in progress · ⬜ planned

---

## Phase 0 — Foundation & local-first AI ✅

The professional-repo baseline (this milestone).

- ✅ Rebrand **Org360 → HiRo** across the codebase and ops scripts.
- ✅ **LLM → local Ollama only** (`qwen2.5:7b`): rewrote `AIService` to a single Ollama code path with native tool-calling; removed all Gemini/Groq SDKs, code paths, keys, and env passthrough.
- ✅ Removed dead/duplicate files, redundant Nginx configs, and internal planning docs.
- ✅ Added the missing **Dgraph schema initializer** so the graph store bootstraps cleanly.
- ✅ Removed hardcoded secrets from build scripts; frontend no longer receives AI keys or JWT secrets.
- ✅ Professional docs: `README`, `LICENSE`, `CONTRIBUTING`, `ARCHITECTURE`, this roadmap.

---

## Phase 1 — Security hardening ⬜

Close the gaps that block any real deployment. Highest priority.

- ⬜ Verify **real auth guards** (JWT `Depends`) are enforced on every route in `comprehensive_routes.py` — replace any remaining mock role dependencies.
- ⬜ Move JWT from `sessionStorage` to **HttpOnly cookies**; strip any JWT secret from the frontend entirely.
- ⬜ Tighten **CORS** to explicit origins; remove wildcard + credentials combinations.
- ⬜ Run **Nginx as non-root**; consolidate to the single `nginx.conf`.
- ⬜ Remove source-code **volume mounts** from the production compose profile.
- ⬜ Add **TLS termination** (self-signed for dev, real certs for prod) + HSTS.
- ⬜ Ensure no credentials or test users leak from any health/diagnostic endpoint.

**Exit criteria:** an unauthenticated request cannot reach any privileged route; no secret is reachable from the browser bundle.

---

## Phase 2 — Make the AI real ⬜

Turn the "AI" surface from mocks into live local inference.

- ⬜ Route **every agent** through `AIService` (Ollama). Audit for direct/mock LLM shortcuts.
- ⬜ Implement **real embeddings** via Ollama (`nomic-embed-text`), replacing the mocked embedding in `ingestion_agent.py`; store to pgvector.
- ⬜ Add **structured-output validation** (Pydantic) on LLM JSON responses with retry-on-malformed.
- ⬜ Upgrade the **orchestrator** to a real plan→execute→verify loop using tool-calling, with LLM observability (log prompts, latency, token counts).
- ⬜ Replace the **mock digital twin** with a real statistical model (scikit-learn over historical UDM data) for attrition/what-if.
- ⬜ Remove `MOCK_AI_RESPONSES` / `ENABLE_MOCK_MODE` code paths once the above land.

**Exit criteria:** disabling all mock flags leaves a fully working AI feature set on local Ollama.

---

## Phase 3 — Live data everywhere ⬜

No static charts, no silent mock fallbacks (per the product's "live, not static" standard).

- ⬜ Wire the `components/charts/` widgets (Area/Bar/Pie) to **real API data** — every consumer (AgentStatusMonitor, DigitalTwinRiskChart, ComplianceDashboard, DynamicDashboard) currently passes no `data` and renders placeholder `defaultData`.
- ⬜ Add **animated/live** behaviors (count-ups, sparklines, live meters) where dashboards are static.
- ⬜ Replace **silent mock fallbacks** in the frontend with explicit loading/empty/error states.
- ⬜ Remove the empty `MOCK_*` scaffolding once real data flows.
- ⬜ Replace the `BPMNCanvas` placeholder with a real renderer (`bpmn-js`) or remove the feature.

**Exit criteria:** every visible dashboard reflects real backend data; a broken API is visibly an error, not fake data.

---

## Phase 4 — Untangle & retire aspirational stubs ⬜

The blockchain/PQC/"conceptual" modules are **load-bearing** (imported by 6–10 modules each), so they can't just be deleted. Untangle first, then remove.

- ⬜ Extract the real constants/interfaces the importers actually need (e.g. `POLICY_ESS_PURPOSE`) into a proper module.
- ⬜ Replace `pqc_pii_layer.py` (mock post-quantum crypto) with standard, real encryption for PII at rest, or drop the abstraction.
- ⬜ Remove `hyperledger_chaincode.py` and rewire `policy_scraping_agent` to a real audit-log sink.
- ⬜ Delete the `pii_vault_core_logic_conceptual` shell once its constants are relocated.
- ⬜ Collapse duplicate model modules (`models.py` vs `schemas/models.py`) into one source of truth.

**Exit criteria:** no file with "conceptual"/mock-crypto in its name remains; every importer resolves to real logic.

---

## Phase 5 — Architecture & maintainability ⬜

- ⬜ Split `comprehensive_routes.py` (~27 routers, 100+ endpoints) into domain route modules.
- ⬜ Introduce explicit **dependency injection**, replacing `app.state` service-locator lookups.
- ⬜ Add **Alembic migrations** for PostgreSQL; formalize the UDM schema.
- ⬜ Remove the import-time **try/except stub fallbacks** so missing services fail loudly.
- ⬜ Split large frontend components (e.g. `HRModules.js`) into focused components; adopt a server-state library (React Query) to replace ad-hoc fetch logic.

---

## Phase 6 — Testing & CI ⬜

- ⬜ Backend: pytest coverage on auth, routes, `AIService`, and enforcement — target 70%+.
- ⬜ Frontend: component tests + Playwright E2E for login → timesheet → leave → approvals.
- ⬜ Harden the GitHub Actions pipeline: lint → test → build → (deploy), with the model/Ollama mocked in CI.
- ⬜ Pre-commit hooks (ruff/black, eslint/prettier).

---

## Phase 7 — Observability & infra ⬜

- ⬜ Structured JSON logging with correlation IDs.
- ⬜ Prometheus metrics + a Grafana dashboard for API latency and agent throughput.
- ⬜ Health-check cascade (backend health reflects DB/NATS/Ollama status).
- ⬜ Right-size Docker resource limits; multi-stage image slimming; automated DB backups.

---

## Sequencing rationale

Security (1) is non-negotiable and comes first. AI-real (2) and live-data (3) deliver the most visible product value and can proceed in parallel. Stub untangling (4) and architecture (5) reduce risk and drag before scaling. Testing (6) and observability (7) harden what the earlier phases build. Throughout: **never break the booting stack** — untangle before delete, migrate before remove.
