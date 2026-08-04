# HiRo Architecture

This document describes how HiRo (**H**uman **I**ntelligence & **R**esource **O**rchestration) is put together: its components, data flow, and the key design decisions behind them.

---

## 1. System overview

HiRo is a containerized, service-oriented application with a single FastAPI backend, a React SPA served through Nginx, a local Ollama LLM, and a set of purpose-specific datastores. Everything runs locally via Docker Compose.

```
Browser → Nginx (:80) → FastAPI (:8001) → { PostgreSQL, MongoDB, Redis, Dgraph, NATS, Ollama }
```

| Service          | Image / build          | Port  | Role |
|------------------|------------------------|-------|------|
| `nginx_proxy`    | frontend Dockerfile    | 80    | Serves the static React build and proxies `/api` + WebSocket |
| `backend`        | backend Dockerfile     | 8001  | FastAPI application (API, agents, orchestration) |
| `postgres_db`    | `postgres:16-alpine`   | 5432  | Primary Unified Data Model (UDM) store + pgvector |
| `mongo`          | `mongo:6.0`            | 27017 | Auth and legacy document store |
| `redis`          | `redis:7-alpine`       | 6379  | Cache and rate-limiting |
| `dgraph-alpha`   | `dgraph/dgraph`        | 8080/9080 | Org-hierarchy graph |
| `dgraph-zero`    | `dgraph/dgraph`        | 5080/6080 | Dgraph cluster coordinator |
| `dgraph-init`    | `curlimages/curl`      | —     | One-shot schema loader (`dgraph_init/init_schema.sh`) |
| `nats`           | `nats:2.10-alpine`     | 4222  | JetStream event bus for agents |
| `ollama`         | `Dockerfile.ollama`    | 11434 | Local LLM (`qwen2.5:7b`) |
| `mock-regulatory`| Flask                  | 8081  | Fake regulatory feed for policy scraping (dev) |

---

## 2. Backend

**Framework:** FastAPI (async), served by Gunicorn + Uvicorn workers in production.

**Entry point:** `backend/server.py` builds the app (CORS, GZip, a custom rate-limit middleware) and mounts every router under `/api`. Startup/shutdown wiring and the background loops live in `backend/app_lifespan.py`, whose lifespan constructs the services and attaches them to `app.state`.

### Layering
- **`config/settings.py`** — a single env-driven `Settings` object. All tunables (DB URLs, JWT, NATS, LLM model, enforcement thresholds, feature flags) resolve from environment variables with sane defaults.
- **`routes/`** — the API surface, one module per domain (`governance`, `hrsd`, `admin_ops`, `ai_data`, `hr_core`, `workforce`, `talent_ext`, `engagement`, plus `people_lifecycle`, `talent`, `ai_knowledge`, and `streaming`). Shared request models, the router instances, and helpers live in `routes/comprehensive_common.py`, which exposes `ALL_ROUTERS`.
- **`services/`** — the bulk of the system: business services, ~40 agents, the AI layer, and DB clients. `services/comprehensive_routes.py` is a thin aggregator that imports the domain route modules (registering their handlers) and re-exports `ALL_ROUTERS`, so existing imports keep working.
- **`utils/`** — async helpers, DB readiness waiter, custom exception hierarchy.

### Service wiring
Services are constructed during app startup and attached to `app.state`; routes read them from there. This is a pragmatic service-locator pattern; migrating to explicit dependency injection is a roadmap item.

---

## 3. AI / LLM layer

All model inference is funneled through **`services/ai_services.py` → `AIService`**, which talks to a **local Ollama** server via its OpenAI-compatible endpoint (`/v1/chat/completions`).

- **Model:** `qwen2.5:7b` by default (`LLM_MODEL_NAME`) — lightweight, CPU-friendly, and capable of native tool-calling.
- **Capabilities:** `generate_text`, `generate_json_response` (prompt-enforced JSON + robust extraction), and `generate_tool_call_or_text` (function-calling for the orchestrator).
- **Resilience:** exponential-backoff retry on transient/429 responses.
- **No cloud:** there are no Gemini/Groq/OpenAI code paths and no API keys — HiRo is local-first by design.

Retrieval uses pgvector embeddings stored in PostgreSQL (embedding generation is currently mocked — see the roadmap).

---

## 4. Agent orchestration

HiRo models HR automation as agents coordinated by an orchestrator:

1. A natural-language command hits the orchestrator (`ultimate_orchestrator.py`).
2. The planner uses the LLM's tool-calling to decompose it into steps.
3. Steps are published to **NATS JetStream**; an `orchestrator_listener` verifies signatures and applies approval gates before executing.
4. Specialized agents (HRSD, policy, workforce, remediation, digital-twin, etc.) carry out the work and emit events/telemetry.

Streaming endpoints surface agent "thoughts" (SSE) and live telemetry (WebSocket) to the UI.

> Today many agents are deterministic heuristics rather than fully autonomous LLM agents. The roadmap tracks upgrading the high-value ones to real agent loops.

---

## 5. Data model

- **PostgreSQL** is the system of record, holding the **Unified Data Model (UDM)** for the Hire-to-Retire lifecycle (`services/udm_schemas_complete.py`), plus HRSD tickets and pgvector embeddings.
- **Dgraph** stores the organizational graph (employees, reporting lines) for hierarchy-aware queries; its schema is applied at startup by `dgraph_init/init_schema.sh`.
- **MongoDB** backs authentication and some legacy/document data.
- **Redis** provides caching and rate-limit counters.

---

## 6. Frontend

**Stack:** React 18 (CRACO), React Router 6, Tailwind CSS with a shadcn/Radix component layer, Recharts, and ReactFlow.

- **Routing:** all pages are lazy-loaded (`React.lazy` + `Suspense`) behind a `ProtectedRoute` (JWT/403 guard) and an `AuthenticatedRouter` that redirects by role.
- **Portals:** Employee, Manager, HRBP, HRIT, and Admin, plus an orchestrator panel, analytics, and a social/collaboration hub.
- **API client:** a single Axios instance in `config/api.js` with request/response interceptors (bearer token, session-expiry handling). A dev proxy routes `/api` → `:8001`.
- **Realtime:** WebSocket telemetry + SSE agent-config streaming.
- **Theming:** CSS-variable design tokens with light/dark and an alternate "holographic" theme, plus a runtime customization context.

Auth tokens are currently held in `sessionStorage`; moving to HttpOnly cookies is a roadmap security item.

---

## 7. Security posture

Implemented: bcrypt password hashing, JWT auth with role guards, rate limiting, GZip, env-driven secrets (nothing committed).

Hardening tracked in the roadmap: HttpOnly-cookie tokens, tightened CORS, non-root Nginx, TLS termination, and removing the import-time mock/fallback stubs so failures surface loudly instead of silently degrading to mock data.

---

## 8. Key design decisions

| Decision | Rationale |
|----------|-----------|
| **Local Ollama over cloud LLMs** | Data never leaves the box; no per-token cost; reproducible; no key management. |
| **`qwen2.5:7b` as default** | Strong tool-calling at a size that runs on ~16 GB CPU hardware. |
| **PostgreSQL as the UDM system of record** | Relational integrity for HR data + pgvector for retrieval in one engine. |
| **Dgraph for the org graph** | Reporting hierarchies and reachability are natural graph queries. |
| **NATS JetStream for agents** | Durable, signed pub/sub decouples the orchestrator from agent execution. |
| **Feature flags + graceful degradation** | Lets the platform boot while capabilities are still being implemented (being phased out in favor of explicit failure). |
