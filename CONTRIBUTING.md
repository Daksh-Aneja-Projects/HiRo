# Contributing to HiRo

Thanks for your interest in HiRo (**H**uman **I**ntelligence & **R**esource **O**rchestration). This guide covers local setup, conventions, and the contribution workflow.

## Development setup

### Full stack (Docker)
```bash
cp .env.example .env
docker compose up -d --build
```

### Backend only
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.in
uvicorn server:app --reload --port 8001
```

### Frontend only
```bash
cd frontend
npm install
npm start
```

A local [Ollama](https://ollama.com/) with `qwen2.5:7b` pulled is required for AI features:
```bash
ollama pull qwen2.5:7b
```

## Conventions

### Backend (Python)
- FastAPI + async. Offload CPU/IO-bound work off the event loop (`asyncio.to_thread`).
- All config comes from `config/settings.py` (env-driven). Never hardcode secrets.
- LLM access goes through `services/ai_services.py` (`AIService`) — do not call Ollama directly from other modules.
- Type hints and Pydantic models for request/response shapes.

### Frontend (React)
- Functional components + hooks. Lazy-load route pages.
- **Premium SVG icons, never emojis** in UI copy.
- **No em-dashes** in UI text — use hyphens or restructure.
- Live, animated visuals (rAF) over static images. Translate raw codes/enums into plain-English narrative.
- Respect `prefers-reduced-motion`.

### General
- Small, focused commits. Conventional-commit style messages (`feat:`, `fix:`, `chore:`, `docs:`).
- Never commit `.env`, secrets, build artifacts, or internal planning docs.

### Dependencies

`backend/requirements.txt` is compiled from `backend/requirements.in` with
[pip-tools](https://github.com/jazzband/pip-tools). To change a backend dependency,
edit `requirements.in`, then regenerate the lock:

```bash
cd backend && pip-compile requirements.in
```

The frontend `package-lock.json` is generated with **npm 10** (the version CI's
Node 20 ships); use `npx npm@10 install` when changing frontend dependencies so
`npm ci` stays in sync.

## Testing

```bash
# Backend (pytest.ini puts backend/ on sys.path, so `import server` resolves)
cd backend && pytest

# Backend with the coverage gate CI enforces (fails under 38%)
cd backend && pytest --cov=. --cov-report=term-missing --cov-fail-under=38

# Frontend
cd frontend && npm test
```

Add or update tests for any behavioral change. Non-trivial logic should ship with at least one runnable check.

## Pull requests

1. Branch from `main` (`feat/…`, `fix/…`).
2. Keep the diff scoped; describe what changed and why.
3. Ensure CI (lint → test → build) is green.
4. Link the related roadmap item or issue where relevant.

## Reporting issues

Open a GitHub issue with reproduction steps, expected vs actual behavior, and environment details.
