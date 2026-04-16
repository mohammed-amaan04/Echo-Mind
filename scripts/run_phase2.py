from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from echomind.workers.phase2_semantic_worker import run_phase2_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EchoMind Phase 2 semantic worker")
    parser.add_argument("--model", default="mistral", help="Ollama model name")
    parser.add_argument("--limit", type=int, default=10, help="Chunks to process per poll")
    parser.add_argument("--once", action="store_true", help="Process a single batch and exit")
    args = parser.parse_args()

    run_phase2_worker(model=args.model, limit=args.limit, once=args.once)


if __name__ == "__main__":
    main()
