# data-analyst-agent — Local, Open-Source Data Analysis Assistant

An agentic data-analysis assistant that runs entirely on your machine. Point it
at your files and databases, ask questions in plain language, and it plans the
analysis, writes and runs SQL/Python in a sandbox, and returns charts,
statistics, and written findings — without copying your data to anyone's cloud.



## Overview

The system is a set of Docker services orchestrated by `docker compose`:

| Service | Role | Dev port | Prod port |
|---------|------|----------|-----------|
| **frontend** | React/Vite web UI (chat, datasource manager, settings) | 3130 | 3030 |
| **app** | Core API: datasource registry, model list, analysis | 8173 | 8073 |
| **agent-service** | ReAct agent: planning, execution, reflection, HITL, chat sessions, knowledge base, skills, memory | 8174 | 8074 |
| **sandbox** | DuckDB-backed Python + SQL execution sandbox | internal | internal |
| **context-engine** | Builds query-aware schema context for the agent | 8172 | internal |
| **qdrant** | Vector store backing the memory system | 6333 | internal |
| **redis** | Working-memory cache | 6379 | internal |

Data is queried **in place** through DuckDB: uploaded files stay on disk and
remote databases are attached read-only — never copied. The agent can join a
CSV, an Excel sheet, and a live Postgres table in a single query with no prior
ETL.

## Tech Stack

### Frontend (`frontend/`)

| Layer | Technologies |
|-------|--------------|
| **Framework** | React 19, TypeScript 5.8 |
| **Build** | Vite 7, SWC |
| **Routing & data** | TanStack Router, TanStack Query, TanStack Table |
| **UI** | Tailwind CSS 4, shadcn/ui (Radix UI), Lucide / Tabler icons |
| **State & forms** | Zustand, React Hook Form, Zod |
| **HTTP** | Axios |
| **Runtime** | Node.js 22 (Docker) |

### Backend services

All API services use **FastAPI** + **Uvicorn**. Python **3.11** (`app`, `agent-service`, `sandbox`); **3.12** (`context-engine`).

| Service | Key libraries & tools |
|---------|----------------------|
| **app** | Pydantic, DuckDB, Pandas, OpenAI SDK (model listing) |
| **agent-service** | LangGraph, LangChain, SQLAlchemy + Alembic + aiosqlite (session DB), Mem0, Qdrant client, Redis |
| **sandbox** | DuckDB, Pandas/NumPy, Matplotlib, Seaborn, SciPy, statsmodels, scikit-learn, sympy |
| **context-engine** | Pydantic, httpx (schema context for the agent) |

### Agent & memory

- **Orchestration**: LangGraph multi-agent workflow (ReAct planner, SQL/Python executor, reflection, HITL)
- **LLM**: OpenAI-compatible API (Ollama default; any compatible provider)
- **Embeddings**: OpenAI-compatible endpoint (e.g. `nomic-embed-text` via Ollama)
- **Memory**: 4-layer system — Qdrant (semantic/episodic vectors), Redis (working memory), Mem0, procedural defaults in SQLite

### Data & infrastructure

| Component | Role |
|-----------|------|
| **DuckDB** | In-place querying across files and attached Postgres/MySQL/DuckDB sources |
| **Docker Compose** | Dev (`docker-compose.dev.yml`) and prod (`docker-compose.yml`) stacks |
| **Qdrant** | Vector store for long-term memory |
| **Redis** | Working-memory cache |
| **SQLite** | Agent chat sessions and run metadata (`agent-service`) |

## Key Features

- 📊 Data visualization and written analysis
- 🚀 Table joins across heterogeneous sources (files + databases) in one query
- 📈 Statistical tests run directly on your dataset
- 🐍 Built-in Python + SQL sandbox (DuckDB)
- 🧠 4-layer agent memory (semantic / episodic / procedural + working memory)
- 📚 Knowledge base and reusable skills
- 🦙 Any OpenAI-compatible LLM provider (Ollama by default)
- 🔒 Local-first — run fully offline if you want

## Quick Start

1. Ensure Docker is installed and running.

2. Clone the repository:
```bash
git clone <your-repo-url>
cd data-analyst-agent
```

3. Copy the environment template (defaults work out of the box):
```bash
cp .env.example .env
```

4. Start the dev stack:
```bash
docker compose -f docker-compose.dev.yml up --build
```

Wait for the containers to start, then open **http://localhost:3130**
(app API on **8173**, agent API on **8174**).

The production stack (`docker-compose.yml`) uses ports **3030 / 8073 / 8074**
and a separate Compose project name (`daa-prod` vs. `daa-dev`), so both stacks
can run side by side.

> **Datasource storage:** Uploaded files (CSV, Excel, SQLite, Parquet) and the
> registry manifest share a Docker volume — `dev_datasource_data` (dev) or
> `prod_datasource_data` (prod). The sandbox queries them in place through
> DuckDB; there is no separate database container for your data.

## LLM Provider Setup

Set any provider's `base_url` and `api_key` from the settings icon in the
top-right of the UI. Ollama is the default. Supported / tested:

- Ollama (default)
- llama.cpp
- LM Studio
- vLLM
- OpenAI
- Anthropic
- Groq
- (and any other OpenAI-compatible endpoint)

> If you point at a hosted provider (OpenAI, Groq, …), your dataset **schema**
> is sent to that provider. To keep everything local, run Ollama as below.

### Running fully local with Ollama

1. Install Ollama: https://ollama.com/

2. Pull a chat model (any instruction-tuned model works; pick by your hardware):
```bash
ollama pull qwen3:8b
```

3. Pull the embedding model used by the memory system:
```bash
ollama pull nomic-embed-text
```

After the models are downloaded, reload the browser and select the chat model
in the UI. If no model appears, confirm Ollama is on port **11434** — otherwise
update the `base_url` in settings.

> Tip: with a reasoning model, adding `/no_think` (or "Do not think.") to a
> query skips the thinking phase and generates code immediately.

## Sample Datasets & Queries

Bundled samples live in [`sample_dataset/`](sample_dataset/) — no download
needed. Upload the files via the **"new tables"** button in the UI:

- `sample_dataset/csv/` — HR workforce data (four joinable CSV tables)
- `sample_dataset/parquet/` — sales / customers / products / support tickets
- `sample_dataset/sqlite/` — inventory database

Each folder ships a `prompt.md` (and `task_*.md` files) with ready-made
prompts. Example queries for the HR CSV set:

1. Scatter plot of **Age** vs. **Total Working Years**.
2. **Chi-square test**: business-travel frequency for single vs. married employees.
3. **Box plot**: attrition vs. monthly income.
4. Top 3 offices with the lowest average survey rating.

## Supported Datasource Types

Registered through the web UI or the `/api/datasources/*` endpoints; all are
queried in place:

- **Files**: CSV, Excel (`.xlsx` / `.xls` — one view per sheet), SQLite
  (`.db` / `.sqlite`), Parquet
- **Databases**: PostgreSQL, MySQL, DuckDB

Each datasource is exposed in the sandbox as one or more DuckDB views, so the
agent can query files and a live database together without ETL.

### Connect an external database

Use the connect endpoint with a structured payload (dev port **8173**, prod
**8073**):

```bash
curl -X POST http://localhost:8173/api/datasources/connect \
  -H "Content-Type: application/json" \
  -d '{
    "name": "analytics_pg",
    "type": "postgres",
    "host": "your-host",
    "port": 5432,
    "database": "analytics",
    "user": "readonly_user",
    "password": "secret"
  }'
```

Or with a connection string:

```bash
curl -X POST http://localhost:8173/api/datasources/connect \
  -H "Content-Type: application/json" \
  -d '{
    "name": "analytics_pg",
    "type": "postgres",
    "connection_string": "postgresql://user:pass@host:5432/db"
  }'
```

Read-only credentials are recommended — DuckDB attaches Postgres and MySQL in
`READ_ONLY` mode by default.

## Contribution

Found a bug or have an idea? Please open a GitHub Issue. Pull requests welcome.
