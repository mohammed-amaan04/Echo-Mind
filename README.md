# EchoMind

EchoMind is a voice-driven cognitive memory system prototype. It converts semantic outputs into persistent, queryable memory structures in PostgreSQL.

Current implementation status: **Phase 3 complete** (Persistence Layer stabilization and pipeline integration).

## What Works Right Now

EchoMind can now persist semantic pipeline outputs safely and consistently.

- Updates `memory_chunks` with refined salience and processed state
- Normalizes entities and performs per-user entity upsert with deduplication
- Increments `mention_count`, updates `last_seen`, and adjusts entity salience
- Creates events only when salience threshold is met
- Links entities to events with relationship roles
- Links events to source memory chunks for evidence traceability
- Manages queue state transitions: `pending -> processing -> done/failed`
- Escalates repeated failures into `failed_jobs`
- Writes structured operational logs to `system_logs`
- Provides Alembic-managed schema and indexes for retrieval-ready queries

## Current Scope vs Future Phases

Implemented:
- Database schema + migrations
- Persistence controller and services
- Queue/failure handling and DB logging
- Dummy data seeding for end-to-end pipeline validation
- Unit and integration tests for persistence behavior

Not yet implemented in full product form:
- Full source ingestion connectors (WhatsApp/Gmail/Meet/etc.)
- Production semantic inference pipeline wiring
- Advanced retrieval and response reasoning layer (Phase 4+)
- End-user UI experience

## Tech Stack

- Python 3.11
- FastAPI
- PostgreSQL 15 + `pgvector`
- SQLAlchemy + Alembic
- Redis (available for worker-oriented flows)

## Quick Start (Windows PowerShell)

### 1. Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements\prototype.txt
pip install -e .
```

### 3. Configure environment

```powershell
Copy-Item .env.example .env
```

Default local URLs in `.env.example` are configured for Docker Compose:
- PostgreSQL: `localhost:5433`
- Redis: `localhost:6379`

### 4. Start infrastructure

```powershell
docker compose up -d
```

### 5. Run migrations

```powershell
python -m alembic upgrade head
```

### 6. Seed Phase 3 dummy data (optional but recommended)

```powershell
python scripts\seed_phase3.py
```

### 7. Run API

```powershell
uvicorn echomind.main:app --app-dir src --reload
```

## Testing

Run persistence-specific tests:

```powershell
pytest tests\test_normalizer.py -v
pytest tests\test_persistence.py -v
```

## Key Tables Active in Phase 3

- `memory_chunks`
- `entities`
- `events`
- `entity_event_links`
- `event_memory_links`
- `processing_queue`
- `failed_jobs`
- `system_logs`
- `user_preferences`

## Project Structure

```text
src/echomind/
  api/
  core/
  db/
  persistence/
  workers/
  main.py
alembic/
scripts/
requirements/
tests/
docker-compose.yml
Dockerfile
```
