<div align="center">

# HiRo

### Human Intelligence & Resource Orchestration

**An AI-native enterprise HR platform — local-first, agent-driven, explainable.**

[![CI](https://github.com/Daksh-Aneja-Projects/HiRo/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Daksh-Aneja-Projects/HiRo/actions/workflows/ci-cd.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg)](https://www.python.org/)
[![React 18](https://img.shields.io/badge/react-18-61DAFB.svg)](https://react.dev/)
[![LLM: Ollama qwen2.5](https://img.shields.io/badge/LLM-Ollama%20qwen2.5-000000.svg)](https://ollama.com/)

</div>

---

## What is HiRo?

HiRo (**H**uman **I**ntelligence & **R**esource **O**rchestration) is an AI-native platform for the full **Hire-to-Retire** employee lifecycle. It pairs a multi-agent orchestration layer with explainable decisioning, digital-twin workforce simulation, and a policy-as-code governance engine — delivered through role-aware portals for Employees, Managers, HR Business Partners, HRIT, and Admins.

HiRo runs **fully local by default**: all LLM inference happens on a local [Ollama](https://ollama.com/) server (`qwen2.5:7b`), so no data leaves your infrastructure and no cloud API keys are required.

> **Project status:** active development. The platform boots end-to-end and the portals/APIs are wired, but a number of AI/agent capabilities are still backed by heuristics or mock data. See the [Roadmap](ROADMAP.md) for what is real today and what is being made functional next.

---

## Highlights

- **Local-first AI** — Ollama + `qwen2.5:7b` for chat, JSON generation, and native tool-calling. Zero cloud dependencies, zero API keys.
- **Multi-agent orchestration** — natural-language commands are planned into multi-step agent workflows, with signature-verified execution over a NATS event bus.
- **Explainable AI (XAI)** — every automated decision exposes the factors, weights, and policy checks behind it, in plain English.
- **Digital-twin simulation** — model attrition, workforce, and "what-if" scenarios against employee data.
- **Policy-as-code governance** — versioned policies, approval workflows, hierarchical enforcement, and an audit trail.
- **Role-aware portals** — Employee / Manager / HRBP / HRIT / Admin, each with a tailored, live dashboard.
- **Unified Data Model (UDM)** — a Hire-to-Retire schema on PostgreSQL, with a Dgraph org-graph for hierarchy and pgvector for retrieval.

---

## Architecture

```
                          ┌──────────────────────────────┐
   Browser  ──────────▶   │   Nginx gateway  (:80)        │
                          │   static React + /api proxy   │
                          └───────────────┬──────────────┘
                                          │
                          ┌───────────────▼──────────────┐
                          │   FastAPI backend  (:8001)    │
                          │   routers · services · agents │
                          └──┬───────┬────────┬────────┬──┘
                             │       │        │        │
        ┌────────────────────┘       │        │        └───────────────┐
        ▼                            ▼        ▼                         ▼
  ┌───────────┐   ┌───────────┐  ┌────────┐  ┌──────────┐   ┌────────────────────┐
  │ PostgreSQL│   │  MongoDB  │  │ Redis  │  │  Dgraph  │   │  NATS JetStream    │
  │ UDM store │   │ auth/log  │  │ cache  │  │ org graph│   │  agent event bus   │
  └───────────┘   └───────────┘  └────────┘  └──────────┘   └────────────────────┘
        │
        ▼
  ┌──────────────────────┐
  │  Ollama  (:11434)    │   local LLM — qwen2.5:7b
  └──────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full breakdown.

---

## Tech stack

| Layer        | Technology |
|--------------|------------|
| **Frontend** | React 18, CRACO, React Router 6, Tailwind CSS + shadcn/Radix UI, Recharts, ReactFlow, Axios |
| **Backend**  | FastAPI (async), Gunicorn + Uvicorn, Pydantic, Python 3.11+ |
| **AI / LLM** | Ollama (`qwen2.5:7b`), OpenAI-compatible tool-calling, pgvector retrieval |
| **Data**     | PostgreSQL 16 (primary UDM), MongoDB 6 (auth/legacy), Redis 7 (cache/rate-limit), Dgraph (org graph) |
| **Messaging**| NATS 2.10 JetStream (agent events) |
| **Infra**    | Docker Compose, Nginx, GitHub Actions CI/CD |

---

## Quick start

### Prerequisites
- Docker + Docker Compose
- ~12 GB RAM free (the `qwen2.5:7b` model alone needs ~5 GB)

### Run the full stack

```bash
git clone https://github.com/Daksh-Aneja-Projects/HiRo.git
cd HiRo
cp .env.example .env        # then edit secrets in .env
docker compose up -d --build
```

On first boot the Ollama image pulls `qwen2.5:7b` (a few minutes). Once healthy:

- **App:** http://localhost
- **API docs:** http://localhost:8001/docs
- **Ollama:** http://localhost:11434

### Local development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# Frontend (separate terminal)
cd frontend
npm install
npm start        # http://localhost:3000, proxies /api -> :8001
```

You'll need a local Ollama running with the model pulled:

```bash
ollama pull qwen2.5:7b
```

---

## Configuration

All configuration is environment-driven — see [.env.example](.env.example) for the full list. Key settings:

| Variable            | Default             | Purpose |
|---------------------|---------------------|---------|
| `LLM_MODEL_NAME`    | `qwen2.5:7b`        | Local Ollama model used for all inference |
| `OLLAMA_BASE_URL`   | `http://ollama:11434` | Ollama server endpoint |
| `POSTGRES_*`        | —                   | Primary UDM datastore |
| `JWT_SECRET_KEY`    | —                   | Backend JWT signing (never expose to the frontend) |

> **Security:** never commit a real `.env`. All secrets are read from the environment; the repo ships only `.env.example` with placeholders.

---

## Project layout

```
HiRo/
├── backend/            FastAPI app — routers, services, agents, config
│   ├── server.py       app assembly (middleware, router mounting, exception handlers)
│   ├── app_lifespan.py startup/shutdown wiring + background tasks
│   ├── config/         settings (env-driven)
│   ├── routes/         API endpoints, grouped by domain (governance, hr_core, ...)
│   ├── services/       business logic, agents, AI, DB clients
│   └── tests/          pytest suite (391 tests)
├── frontend/           React 18 SPA (CRACO)
│   └── src/            components · pages · contexts · config · hooks
├── dgraph_init/        Dgraph org-graph schema initializer
├── docker-compose.yml  full local stack
├── ROADMAP.md          implementation roadmap
└── docs/               architecture & deeper docs
```

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — components, data flow, and design decisions
- [Roadmap](ROADMAP.md) — phased plan to make every capability functional
- [Contributing](CONTRIBUTING.md) — dev setup, conventions, and workflow

---

## License

[MIT](LICENSE) © Daksh Aneja
