# Adaptive Interview Platform

Backend foundation for a text-first adaptive interview product. The API separates answer evaluation, RAG retrieval, question selection, and interview state so each part can evolve independently.

## Requirements

- Python 3.12 or newer
- `uv` package manager

## Run locally (PowerShell)

```powershell
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Open `/docs` for interactive API docs. Liveness checks are at `/health` and `/api/v1/health`; the complete route guide is in [docs/api.md](docs/api.md).

## Project structure

- `app/api`: versioned routes and authentication dependencies
- `app/core`: settings and cross-cutting concerns
- `app/schemas`: request and response contracts
- `app/services`: application services and local repository prototype
- `app/ai`: answer evaluation and question generation
- `app/rag`: ingestion, embeddings, retrieval, and ranking
- `app/interview`: interview state machine and session rules
- `docs`: architecture and API guides

The current API is a runnable local MVP. Its records and sessions are in memory; persistent storage, managed auth, LLM-backed evaluation, and vector search are follow-on integrations. Candidate code execution remains disabled until an isolated sandbox is configured.
