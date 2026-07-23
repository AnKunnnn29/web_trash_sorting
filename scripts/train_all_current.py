#!/usr/bin/env python3
"""Run the complete current-split candidate matrix sequentially on CPU."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
SPLIT = BASE_DIR / "reports" / "training-split.csv"
STATUS = BASE_DIR / "reports" / "train-all-current-status.json"
RUNS = [
    ("E2", 20260727),
    ("E4", 20260727),
    ("E4", 20260728),
    ("E4", 20260729),
]


def split_sha256() -> str:
    return hashlib.sha256(SPLIT.read_bytes()).hexdigest()


def write_status(payload: dict) -> None:
    STATUS.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def metrics_match(experiment: str, seed: int, split_hash: str) -> bool:
    path = (
        BASE_DIR / "model_candidates"
        / f"{experiment.lower()}-seed-{seed}" / "metrics.json"
    )
    if not path.exists():
        return False
    metrics = json.loads(path.read_text(encoding="utf-8"))
    return metrics.get("split_sha256") == split_hash


def run_logged(command: list[str], log_name: str) -> int:
    log_path = BASE_DIR / "reports" / log_name
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.run(
            command,
            cwd=str(BASE_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    return process.returncode


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    readiness = subprocess.run(
        [sys.executable, "scripts/check_pretraining_readiness.py"],
        cwd=str(BASE_DIR),
    )
    if readiness.returncode:
        raise SystemExit("Pre-training readiness gate failed.")

    split_hash = split_sha256()
    status = {
        "split_sha256": split_hash,
        "started_at": time.time(),
        "state": "running",
        "runs": [],
    }
    write_status(status)

    for experiment, seed in RUNS:
        item = {
            "experiment": experiment,
            "seed": seed,
            "state": "pending",
        }
        status["runs"].append(item)
        if metrics_match(experiment, seed, split_hash):
            item["state"] = "skipped_existing"
            write_status(status)
            continue
        item["state"] = "running"
        item["started_at"] = time.time()
        write_status(status)
        command = [
            sys.executable,
            "scripts/train_candidate.py",
            "--experiment", experiment,
            "--seed", str(seed),
            "--epochs", "8",
            "--finetune-epochs", "4",
            "--max-train-per-class", "160",
        ]
        returncode = run_logged(
            command, f"training-{experiment.lower()}-{seed}.log"
        )
        item["elapsed_seconds"] = time.time() - item["started_at"]
        item["returncode"] = returncode
        item["state"] = "completed" if returncode == 0 else "failed"
        write_status(status)
        if returncode:
            status["state"] = "failed"
            write_status(status)
            return returncode

    evaluation_commands = [
        (
            [
                sys.executable,
                "scripts/evaluate_model_split.py",
                "--model", "saved_model_keras",
                "--output", "reports/baseline-clean-split-current.json",
            ],
            "baseline-current-evaluation.log",
        ),
        (
            [sys.executable, "scripts/summarize_training.py"],
            "training-summary-current.log",
        ),
        (
            [sys.executable, "scripts/evaluate_brand_smoke.py"],
            "brand-smoke-current.log",
        ),
    ]
    for command, log_name in evaluation_commands:
        if run_logged(command, log_name):
            status["state"] = "evaluation_failed"
            write_status(status)
            return 1
    status["state"] = "completed"
    status["elapsed_seconds"] = time.time() - status["started_at"]
    write_status(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
