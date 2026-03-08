# EchoMind

Prototype-ready starter scaffold for EchoMind with pinned dependencies.

## Stack Baseline

- Python 3.11
- PostgreSQL 15+
- pgvector extension
- Redis (optional)
- FFmpeg (optional unless using audio pipeline)

## Quick Start (Windows PowerShell)

1. Create and activate a virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install prototype dependencies:
```powershell
pip install --upgrade pip
pip install -r requirements\prototype.txt
```

3. Download NLP model/data:
```powershell
python scripts\bootstrap_nlp.py
```

4. Copy env template and adjust values:
```powershell
Copy-Item .env.example .env
```

5. Run API:
```powershell
uvicorn echomind.main:app --app-dir src --reload
```

## Dependency Layout

- `requirements/prototype.txt`: lean stack for rapid prototype development
- `requirements/all.txt`: full stack (prototype + optional + production extras)
- `requirements/runtime.txt`: points to prototype by default
- `requirements/dev.txt`: prototype + local developer utilities

## System Dependencies

Install separately:

- PostgreSQL 15+
- pgvector extension
- Redis (optional)
- FFmpeg (only for audio transcription features)
- Docker (optional)

## Setup Profiles

- Prototype (default):
```powershell
.\scripts\setup.ps1
```
- Full stack:
```powershell
.\scripts\setup.ps1 -Profile full
```

## Project Structure

```text
src/echomind/
  api/
  core/
  db/
  workers/
  main.py
scripts/
requirements/
tests/
docker-compose.yml
Dockerfile
```
