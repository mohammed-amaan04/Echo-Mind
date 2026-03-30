# EchoMind

EchoMind is a voice-driven cognitive memory system prototype. It converts semantic outputs into persistent, queryable memory structures in PostgreSQL with pgvector-powered embeddings.

**Current Status:** Phase 5 baseline implemented (Retrieval + Response) — the system can now retrieve contextual memory and generate grounded answers via a unified API flow.

## What Works Right Now

### Phase 5: Response Layer (✅ Implemented & Tested)

EchoMind can generate grounded responses from retrieved memory context:

- Exposes a unified `POST /ask` endpoint that runs retrieval + response generation
- Formats retrieved events/entities/chunks into an LLM-ready context block
- Builds grounded prompts with explicit anti-hallucination rules
- Calls an OpenAI-compatible chat-completions endpoint (configurable model/base URL)
- Falls back safely to retrieval context summary when API key/call is unavailable
- Computes confidence scores from context density, entity match, and salience
- Suggests non-executing follow-up actions (`set_reminder`, `draft_message`, `follow_up`, `draft_reply`)

### Phase 4: Retrieval Layer (✅ Complete & Tested)

EchoMind can reconstruct relevant memory context in response to natural-language queries:

- Parses user queries to detect referenced entities, classify intent (informational/temporal/relational), and extract time filters
- Performs **vector similarity search** on `memory_chunks.embedding` via pgvector cosine distance
- Performs **entity-based graph search** via `entity_event_links` with multi-entity intersection semantics
- **Merges** vector and graph results into a unified candidate set
- **Ranks** results using a composite score: `0.4·vector_similarity + 0.3·salience + 0.2·recency + 0.1·entity_overlap`
- **Expands** the knowledge graph to fetch linked entities and supporting memory chunks
- **Assembles** a structured `RetrievalResult` with chronological events, entities, chunks, and a plain-text context summary
- Exposes a `POST /retrieve` API endpoint for query access

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

## Current Scope vs Future Phases

### ✅ Implemented (Phase 5 — Response)
- `POST /ask` endpoint (retrieval + response orchestration)
- Context formatter + prompt builder for grounded LLM answers
- OpenAI-compatible client with safe fallback behavior
- Confidence scoring and rule-based action suggestion engine
- 18 tests covering response formatting, confidence, actions, and orchestration

### ✅ Implemented (Phase 4 — Retrieval)
- Hybrid retrieval engine (vector similarity + entity graph + temporal + salience)
- Query parser with entity detection, intent classification, and time filter extraction
- Composite ranking engine with configurable weights
- Graph expansion for contextual entity/chunk discovery
- Context builder generating LLM-ready summaries
- `POST /retrieve` API endpoint
- Embedding seeding script for vector search readiness
- 16 integration tests for retrieval behavior

### ✅ Implemented (Phase 3 — Persistence)
- Database schema + migrations (22 tables, pgvector integration)
- Persistence controller and services (entity normalization, event creation, graph linking)
- Queue/failure handling and DB logging
- Dummy data seeding for end-to-end pipeline validation
- 15 unit and integration tests for persistence behavior

### 🔧 Ready for Integration (Phase 2 Dependencies)
- spaCy transformer NLP model (`en_core_web_trf`) for entity extraction
- NLTK corpus data for text processing
- Sentence transformers for vector embeddings (`all-MiniLM-L6-v2`)
- All Python dependencies installed and validated

### 🚧 Pending Development
- **Phase 2:** Semantic extraction module (`src/echomind/semantic/`) — Entity recognition, event detection, salience scoring
- **Phase 1:** Full source ingestion connectors (WhatsApp/Gmail/Meet/Voice)

### 📋 Future Phases
- **Phase 6:** End-user UI experience
- **Phase 7:** Production hardening (auth, observability, deployment, scale)

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
pip install -r all.txt
pip install -e .
```

**Troubleshooting:** If you encounter `resolution-too-deep` error, use the legacy resolver:

```powershell
pip install --use-deprecated=legacy-resolver -r all.txt
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

### 7. Seed data

```powershell
# Phase 3: Create knowledge graph (users, chunks, entities, events, relationships)
python scripts\seed_phase3.py

# Phase 4: Generate vector embeddings for memory chunks
python scripts\seed_phase4.py
```

Phase 3 seed creates:
- Test user with salience threshold preference
- 5 dummy memory chunks (WhatsApp, Gmail, voice notes)
- Processing queue entries
- Example semantic outputs persisted via the controller

Phase 4 seed adds:
- Real 384-dim vector embeddings for all memory chunks (using `all-MiniLM-L6-v2`)

### 8. Run API

```powershell
uvicorn echomind.main:app --app-dir src --reload
```

API will be available at: `http://localhost:8000`

API docs (Swagger): `http://localhost:8000/docs`

### 9. Query memory (Phase 4)

```powershell
# Test retrieval endpoint
curl -X POST http://localhost:8000/retrieve `
  -H "Content-Type: application/json" `
  -d '{"query_text": "What did Amaan and Abdullah decide about EchoMind?", "user_id": 1, "top_k": 5}'

# Test unified ask endpoint (Phase 5)
curl -X POST http://localhost:8000/ask `
  -H "Content-Type: application/json" `
  -d '{"query_text": "What did Amaan and Abdullah decide about EchoMind?", "user_id": 1, "top_k": 5}'
```

## Testing

Run all tests (currently 59 test functions):

```powershell
pytest -v
```

Run specific test suites:

```powershell
# Entity normalization (pure unit tests, no DB)
pytest tests\test_normalizer.py -v

# Persistence layer (requires PostgreSQL)
pytest tests\test_persistence.py -v

# Retrieval layer (requires PostgreSQL + embedding model)
pytest tests\test_retrieval.py -v

# Response layer (LLM calls mocked)
pytest tests\test_response.py -v
```

## Key Tables

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
    routes/
      health.py            # Health check endpoint
      retrieval.py         # ✅ POST /retrieve endpoint (Phase 4)
      response.py          # ✅ POST /ask endpoint (Phase 5)
  core/                    # Config, logging
  db/
    models/                # 22 SQLAlchemy models (complete)
    base.py
    session.py
  persistence/             # ✅ Phase 3 complete
    controller.py          # 7-step persistence orchestrator
    entity_service.py      # Entity upsert + deduplication
    event_service.py       # Event creation logic
    relationship_service.py    # Graph linking
    entity_normalizer.py   # Name normalization + alias mapping
    queue_manager.py       # Queue state transitions
    failure_manager.py     # Retry + escalation logic
    logging_service.py     # System log writes
    schemas.py             # SemanticOutput contract
  retrieval/               # ✅ Phase 4 complete
    engine.py              # 7-step retrieval orchestrator
    query_parser.py        # Query understanding (entities, intent, time)
    vector_search.py       # pgvector semantic similarity search
    entity_search.py       # Entity-based graph retrieval
    graph_traversal.py     # Knowledge graph expansion
    ranker.py              # Composite scoring engine
    context_builder.py     # Context assembly + summary generation
    schemas.py             # RetrievalQuery/RetrievalResult contracts
  response/                # ✅ Phase 5 baseline implemented
    engine.py              # Response orchestrator
    context_formatter.py   # LLM-ready context formatting
    prompt_builder.py      # Grounded prompt construction
    llm_client.py          # OpenAI-compatible client + fallback
    confidence.py          # Confidence scoring
    actions.py             # Suggested follow-up actions
    schemas.py             # ResponseRequest/ResponseOutput contracts
  workers/                 # Background job infrastructure
    celery_app.py
    scheduler.py
  main.py                  # FastAPI app
alembic/
  versions/
    001_initial_schema.py  # Complete schema migration
scripts/
  bootstrap_nlp.py         # ✅ NLP model initialization
  seed_phase3.py           # ✅ Knowledge graph seeding
  seed_phase4.py           # ✅ Embedding generation
requirements/
  runtime.txt              # Runtime dependency entrypoint (currently references prototype file)
  dev.txt                  # Dev dependency entrypoint
all.txt                    # Current complete dependency list used in setup
tests/
  test_health.py           # ✅ API health check test
  test_normalizer.py       # ✅ Entity normalization tests (10)
  test_persistence.py      # ✅ Persistence layer tests (15)
  test_retrieval.py        # ✅ Retrieval layer tests (16)
  test_response.py         # ✅ Response layer tests (18)
docker-compose.yml         # PostgreSQL + Redis
```

## Retrieval Layer Architecture

### RetrievalQuery Interface (Input)

```python
@dataclass
class RetrievalQuery:
    query_text: str
    user_id: int
    top_k: int = 10
```

### RetrievalResult Interface (Output)

```python
@dataclass
class RetrievalResult:
    relevant_events: list[Event]
    relevant_entities: list[Entity]
    supporting_chunks: list[MemoryChunk]
    context_summary: str
```

### Retrieval Pipeline Flow

```
User Query
    ↓
Query Parser (entity detection, intent, time filter)
    ↓
[Vector Search] + [Entity Search]
    ↓
Merged Candidate Events
    ↓
Ranking Engine (0.4·vector + 0.3·salience + 0.2·recency + 0.1·overlap)
    ↓
Graph Expansion (linked entities + supporting chunks)
    ↓
Context Builder (chronological summary)
    ↓
RetrievalResult (ready for LLM input in Phase 5)
```

### Database Table Usage

| Table              | Usage               |
| ------------------ | ------------------- |
| memory_chunks      | vector similarity   |
| entities           | entity matching     |
| events             | core retrieval unit |
| entity_event_links | graph traversal     |
| event_memory_links | evidence            |
| user_preferences   | optional filters    |

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

### Verify Retrieval Layer

```powershell
# Start API server
uvicorn echomind.main:app --app-dir src --reload

# In another terminal, test retrieval
curl -X POST http://localhost:8000/retrieve -H "Content-Type: application/json" -d "{\"query_text\": \"What did Amaan decide?\", \"user_id\": 1, \"top_k\": 5}"
```

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
# All tests (currently 59 test functions)
pytest -v

# Specific test files
pytest tests\test_persistence.py -v
pytest tests\test_normalizer.py -v
pytest tests\test_retrieval.py -v

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
6. **Layer 6:** Retrieval ← *Phase 4 ✅ complete*
7. **Layer 7:** Response & Action
8. **Layer 8:** UI

### Data Flow

```
memory_chunks (with embeddings)
    ↓
[Phase 2: Semantic Extraction]  ← Pending integration
    ↓
SemanticOutput
    ↓
[Phase 3: Persistence Layer]    ← ✅ Complete
    ↓
Knowledge Graph (entities, events, relationships)
    ↓
[Phase 4: Retrieval Layer]      ← ✅ Complete
    ↓
RetrievalResult (events, entities, chunks, context_summary)
    ↓
[Phase 5: Response Layer]       ← ✅ Implemented baseline
```

## Contributing

This is a prototype project developed in phases:

- **Phase 5** (current): Response layer baseline — retrieval-grounded answering + actions
- **Phase 4** (complete): Retrieval layer — hybrid vector + graph memory search
- **Phase 3** (complete): Persistence layer stabilization
- **Phase 2** (in development): Semantic extraction module
- **Phase 1** (planned): Full ingestion pipeline
- **Phase 6+** (planned): UI, production hardening

## Known Gaps (Current Snapshot)

- `src/echomind/semantic/` is still pending (semantic extraction pipeline not yet implemented in-repo)
- `requirements/runtime.txt` and `requirements/dev.txt` currently point to `..\\prototype.txt`, which is not present in this workspace
- `Dockerfile` currently copies `requirements/all.txt`, while the dependency file exists at project root as `all.txt`

## License

[Add license information]

## Contact

[Add contact information]

