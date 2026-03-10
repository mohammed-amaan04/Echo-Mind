# EchoMind

EchoMind is a voice-driven cognitive memory system prototype. It converts semantic outputs into persistent, queryable memory structures in PostgreSQL with pgvector-powered embeddings.

**Current Status:** Phase 3 complete (Persistence Layer) + **Phase 2 Integration Ready** (Semantic Pipeline dependencies installed and validated).

## What Works Right Now

### Phase 3: Persistence Layer (✅ Complete & Tested)

EchoMind can persist semantic pipeline outputs safely and consistently:

- Updates `memory_chunks` with refined salience and processed state
- Normalizes entities and performs per-user entity upsert with deduplication
- Increments `mention_count`, updates `last_seen`, and adjusts entity salience
- Creates events only when salience threshold is met (configurable via `user_preferences`)
- Links entities to events with relationship roles (`participant`, `subject`, `organizer`, etc.)
- Links events to source memory chunks for evidence traceability
- Manages queue state transitions: `pending -> processing -> done/failed`
- Escalates repeated failures (>3 retries) into `failed_jobs` table
- Writes structured operational logs to `system_logs`
- Provides Alembic-managed schema and indexes for retrieval-ready queries

### Phase 2: Integration Readiness (✅ Dependencies Installed)

All required NLP models and libraries are downloaded and validated:

- **spaCy transformer model** (`en_core_web_trf-3.7.3`) — High-accuracy entity recognition
- **NLTK corpus data** (`punkt`, `wordnet`, `stopwords`) — Text processing utilities
- **Sentence Transformers** (`all-MiniLM-L6-v2`) — Vector embeddings (384-dim)
- **Runtime validation** — All imports and model loading tested successfully

The persistence layer is ready to receive `SemanticOutput` objects from Phase 2 semantic extraction module.

## Current Scope vs Future Phases

### ✅ Implemented (Phase 3)
- Database schema + migrations (22 tables, pgvector integration)
- Persistence controller and services (entity normalization, event creation, graph linking)
- Queue/failure handling and DB logging
- Dummy data seeding for end-to-end pipeline validation
- Unit and integration tests for persistence behavior

### 🔧 Ready for Integration (Phase 2 Dependencies)
- spaCy transformer NLP model (`en_core_web_trf`) for entity extraction
- NLTK corpus data for text processing
- Sentence transformers for vector embeddings (`all-MiniLM-L6-v2`)
- All Python dependencies installed and validated
- Environment configured for semantic pipeline development

### 🚧 Pending Development (Phase 2)
- **Semantic extraction module** (`src/echomind/semantic/`) — Entity recognition, event detection, salience scoring
- **Worker integration** — Background processing of `processing_queue`
- **API endpoints** — Manual semantic processing triggers

### 📋 Future Phases
- **Phase 1:** Full source ingestion connectors (WhatsApp/Gmail/Meet/Voice)
- **Phase 4:** Advanced retrieval engine (vector search + graph traversal)
- **Phase 5:** Response generation and reasoning layer
- **Phase 6:** End-user UI experience

## Tech Stack

### Core Framework
- Python 3.11
- FastAPI 0.111.0
- Uvicorn (ASGI server)

### Database & Storage
- PostgreSQL 15 + `pgvector` (0.2.5)
- SQLAlchemy 2.0.30 (ORM)
- Alembic 1.13.2 (migrations)
- asyncpg 0.29.0 (async PostgreSQL driver)

### NLP & Machine Learning
- spaCy 3.7.4 + `en_core_web_trf` model (transformer-based NER)
- sentence-transformers 2.7.0 (vector embeddings)
- NLTK 3.8.1 (text processing)
- transformers 4.41.2 + torch 2.3.0 (Hugging Face models)
- scikit-learn 1.5.0 (ML utilities)

### Task Processing
- APScheduler 3.10.4 (background job scheduling)
- Redis (available for Celery workers)

### Development Tools
- pytest 8.2.2 (testing)
- black 24.4.2 (code formatting)
- ruff 0.4.8 (linting)

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

**Troubleshooting:** If you encounter `resolution-too-deep` error, use the legacy resolver:

```powershell
pip install --use-deprecated=legacy-resolver -r requirements\prototype.txt
pip install huggingface-hub==0.36.2 packaging==24.2
```

### 3. Download NLP models

```powershell
# spaCy transformer model (required for Phase 2)
python -m spacy download en_core_web_trf

# If the above fails with 404, use direct wheel installation:
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_trf-3.7.3/en_core_web_trf-3.7.3-py3-none-any.whl

# NLTK corpus data
python scripts\bootstrap_nlp.py
```

### 4. Configure environment

```powershell
Copy-Item .env.example .env
```

Default local URLs in `.env.example` are configured for Docker Compose:
- PostgreSQL: `localhost:5433`
- Redis: `localhost:6379`

### 5. Start infrastructure

```powershell
docker compose up -d
```

### 6. Run migrations

```powershell
python -m alembic upgrade head
```

### 7. Seed Phase 3 dummy data (optional but recommended)

```powershell
python scripts\seed_phase3.py
```

This creates:
- Test user with salience threshold preference
- 5 dummy memory chunks (WhatsApp, Gmail, voice notes)
- Processing queue entries
- Example semantic outputs persisted via the controller

### 8. Run API

```powershell
uvicorn echomind.main:app --app-dir src --reload
```

API will be available at: `http://localhost:8000`

API docs (Swagger): `http://localhost:8000/docs`

## Testing

Run persistence-specific tests:

```powershell
pytest tests\test_normalizer.py -v
pytest tests\test_persistence.py -v
```

## Key Tables Active in Phase 3

### Cognitive Memory
- `memory_chunks` — Raw episodic memory with embeddings and salience scores
- `entities` — Deduplicated people, projects, tools (normalized via persistence layer)
- `events` — High-salience moments (meetings, decisions, deadlines)
- `entity_event_links` — Graph relationships with semantic roles
- `event_memory_links` — Traceability to source memory chunks

### Pipeline Management
- `processing_queue` — Ensures exactly-once semantic processing per chunk
- `failed_jobs` — Escalation for permanently failed processing
- `system_logs` — Operational activity logs

### Configuration
- `users` — Single-user profile
- `user_preferences` — Key-value settings (e.g., `salience_threshold=0.5`)

## Project Structure

```text
src/echomind/
  api/
    routes/              # API endpoints (health check currently)
  core/                  # Config, logging
  db/
    models/              # 22 SQLAlchemy models (complete)
    base.py
    session.py
  persistence/           # ✅ Phase 3 complete
    controller.py        # 7-step persistence orchestrator
    entity_service.py    # Entity upsert + deduplication
    event_service.py     # Event creation logic
    relationship_service.py  # Graph linking
    entity_normalizer.py # Name normalization + alias mapping
    queue_manager.py     # Queue state transitions
    failure_manager.py   # Retry + escalation logic
    logging_service.py   # System log writes
    schemas.py           # SemanticOutput contract
  workers/               # Background job infrastructure
    celery_app.py
    scheduler.py
  main.py                # FastAPI app
alembic/
  versions/
    001_initial_schema.py  # Complete schema migration
scripts/
  bootstrap_nlp.py       # ✅ NLP model initialization
  seed_phase3.py         # ✅ Dummy data seeding
requirements/
  prototype.txt          # ✅ All dependencies installed
tests/
  test_persistence.py    # ✅ Persistence layer tests
  test_normalizer.py     # ✅ Entity normalization tests
docker-compose.yml       # PostgreSQL + Redis
```

### 🔜 Phase 2 Integration Will Add

```text
src/echomind/
  semantic/              # To be integrated by teammate
    extractor.py         # Main SemanticExtractor class
    entity_recognition.py    # spaCy NER wrapper
    event_detection.py       # Event candidate logic
    salience_scorer.py       # Refined salience calculation
    relationship_extractor.py # Entity-role mapping
  api/
    routes/
      semantic.py        # Processing endpoints
  workers/
    semantic_worker.py   # Background batch processor
```

## Phase 2 Integration Contract

When Phase 2 semantic extraction module is integrated, it will:

1. **Read from:** `memory_chunks` table (via `processing_queue` with `status=pending`)
2. **Process:** Extract entities, detect events, score salience, identify relationships
3. **Output:** `SemanticOutput` objects (defined in `src/echomind/persistence/schemas.py`)
4. **Call:** `persist_semantic_output(db, semantic_output)` from `src/echomind/persistence/controller.py`
5. **Result:** Persistence layer handles all database writes, deduplication, and graph construction

### SemanticOutput Interface

```python
@dataclass
class SemanticOutput:
    memory_chunk_id: int
    entities: list[ExtractedEntity]        # name, entity_type
    event_candidate: EventCandidate | None  # title, summary, event_type
    relationships: list[Relationship]       # entity_name, role
    refined_salience: float                 # 0.0 - 1.0
```

The persistence layer is **fully tested and production-ready** to receive these outputs.

## Verification Commands

### Verify Python Environment

```powershell
# Check all dependencies installed
pip check

# Verify NLP models loaded successfully
python -c "import spacy; nlp=spacy.load('en_core_web_trf'); print('✓ spaCy model ready')"

# Verify embedding model cached
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2'); print('✓ Embedding model ready')"

# Test all critical imports
python -c "import fastapi, spacy, transformers, sentence_transformers, sqlalchemy, pgvector; print('✓ All imports successful')"
```

### Verify Database Setup

```powershell
# Check PostgreSQL connection
docker compose ps

# Verify migrations applied
python -m alembic current

# Count tables in database
python -c "from echomind.db.session import engine; from sqlalchemy import inspect; print(f'✓ {len(inspect(engine).get_table_names())} tables created')"
```

### Verify API Health

```powershell
# Start API server
uvicorn echomind.main:app --app-dir src

# In another terminal, test health endpoint
curl http://localhost:8000/health
```

Expected response: `{"status":"healthy"}`

## Database Queries for Manual Testing

After running `python scripts\seed_phase3.py`, you can verify the knowledge graph:

```sql
-- View all entities
SELECT id, name, entity_type, mention_count, salience_score 
FROM entities;

-- View all events with high salience
SELECT id, title, event_type, salience_score, start_time
FROM events
WHERE salience_score >= 0.5
ORDER BY salience_score DESC;

-- View entity-event relationships
SELECT e.name, ev.title, eel.role
FROM entities e
JOIN entity_event_links eel ON e.id = eel.entity_id
JOIN events ev ON eel.event_id = ev.id;

-- Trace event back to source memory
SELECT ev.title, mc.content, mc.timestamp
FROM events ev
JOIN event_memory_links eml ON ev.id = eml.event_id
JOIN memory_chunks mc ON eml.memory_chunk_id = mc.id;

-- Check processing queue status
SELECT status, COUNT(*) 
FROM processing_queue 
GROUP BY status;
```

## Development Workflow

### Run Tests

```powershell
# All tests
pytest -v

# Specific test files
pytest tests\test_persistence.py -v
pytest tests\test_normalizer.py -v

# With coverage
pytest --cov=echomind --cov-report=html
```

### Code Quality

```powershell
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking (if mypy configured)
mypy src/
```

### Database Migrations

```powershell
# Create new migration
python -m alembic revision --autogenerate -m "description"

# Apply migrations
python -m alembic upgrade head

# Rollback one version
python -m alembic downgrade -1

# View migration history
python -m alembic history
```

## Architecture Notes

### 8-Layer System Design

1. **Layer 1:** Data Input (connectors)
2. **Layer 2:** Preprocessing & Normalization
3. **Layer 3:** Semantic Understanding ← *Phase 2 pending integration*
4. **Layer 4:** Knowledge Structuring ← *Phase 3 ✅ complete*
5. **Layer 5:** Persistence (PostgreSQL + pgvector)
6. **Layer 6:** Retrieval
7. **Layer 7:** Response & Action
8. **Layer 8:** UI

### Data Flow

```
memory_chunks (with embeddings)
    ↓
[Phase 2: Semantic Extraction]  ← Teammate's development
    ↓
SemanticOutput
    ↓
[Phase 3: Persistence Layer]    ← ✅ Ready for integration
    ↓
Knowledge Graph (entities, events, relationships)
```

## Contributing

This is a prototype project developed in phases:

- **Phase 3** (current): Persistence layer stabilization
- **Phase 2** (in development): Semantic extraction module
- **Phase 1** (planned): Full ingestion pipeline
- **Phase 4+** (planned): Retrieval, reasoning, UI

## License

[Add license information]

## Contact

[Add contact information]
