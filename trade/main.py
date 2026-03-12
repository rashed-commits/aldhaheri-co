"""
Trade-Bot Orchestration
=======================
Runs each phase of the pipeline in order.

Usage
-----
    python main.py [--phase N] [--dry-run]

    --phase 1            Data ingestion      → data/combined.csv
    --phase 2            Feature engineering  → data/features.csv
    --phase 3            Model training       → model/saved/
    --phase 4            Daily signal gen     → output/signals_YYYY-MM-DD.json
    --phase 4 --dry-run  Phase 4 without writing any output files
    --phase 5            Paper trade execute  → output/open_positions.json
    --phase 5 --dry-run  Phase 5 without submitting orders or writing files
    (no flag)            Run phases 1-3 sequentially
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from src.notifications import notify_error, notify_pipeline_complete, notify_pipeline_start
from src.utils import get_logger

log = get_logger("main")


def run_phase1() -> None:
    """Phase 1: Data ingestion / combination (produces ``data/combined.csv``)."""
    try:
        from src.ingest import run as ingest_run

        ingest_run()
    except Exception as exc:
        log.error("Phase 1 failed: %s", exc, exc_info=True)
        raise


def run_phase2() -> None:
    """Phase 2: Feature engineering (produces ``data/features.csv``)."""
    try:
        from src.features import run as features_run

        features_run()
    except Exception as exc:
        log.error("Phase 2 failed: %s", exc, exc_info=True)
        raise


def run_phase3() -> None:
    """Phase 3: Model training (produces ``model/saved/`` artefacts)."""
    try:
        from src.train import run as train_run

        train_run()
    except Exception as exc:
        log.error("Phase 3 failed: %s", exc, exc_info=True)
        raise


def run_phase4(dry_run: bool = False) -> None:
    """Phase 4: Daily signal generator (produces ``output/signals_YYYY-MM-DD.json``)."""
    try:
        from src.signals import run as signals_run

        signals_run(dry_run=dry_run)
    except Exception as exc:
        log.error("Phase 4 failed: %s", exc, exc_info=True)
        raise


def run_phase5(dry_run: bool = False) -> None:
    """Phase 5: Alpaca paper trade execution (reads signals, manages positions)."""
    try:
        from src.execution.executor import run as executor_run

        executor_run(dry_run=dry_run)
    except Exception as exc:
        log.error("Phase 5 failed: %s", exc, exc_info=True)
        raise


def main() -> None:
    """CLI entry point — parse args and dispatch to the requested phase(s)."""
    parser = argparse.ArgumentParser(description="Trade-Bot pipeline orchestrator")
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3, 4, 5],
        default=None,
        help="Run a specific phase only (1-5). Omit to run phases 1-3 sequentially.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Phases 4 & 5: run full logic but skip writing files / submitting orders.",
    )
    args = parser.parse_args()

    phase_label = f"Phase {args.phase}" if args.phase else "Phases 1-3"
    notify_pipeline_start(phase_label)

    try:
        if args.phase == 1:
            run_phase1()
        elif args.phase == 2:
            run_phase2()
        elif args.phase == 3:
            run_phase3()
        elif args.phase == 4:
            run_phase4(dry_run=args.dry_run)
        elif args.phase == 5:
            run_phase5(dry_run=args.dry_run)
        else:
            # Default: run the training pipeline (phases 1-3)
            run_phase1()
            run_phase2()
            run_phase3()
    except Exception as exc:
        log.error("Pipeline aborted due to error above.")
        notify_error(phase_label, str(exc))
        sys.exit(1)

    notify_pipeline_complete(phase_label)


if __name__ == "__main__":
    main()
