#!/usr/bin/env python3
"""Evaluate any SavedModel against the fixed duplicate-safe split."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from train_candidate import (
    BASE_DIR,
    file_sha256,
    generators,
    load_split,
    saved_model_metrics,
)


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split-manifest",
        type=Path,
        default=BASE_DIR / "reports" / "training-split.csv",
    )
    args = parser.parse_args()
    train, validation, test, external, labels = load_split(
        args.split_manifest, 0, 20260723
    )
    _, _, test_gen, external_gen = generators(
        train, validation, test, external, labels, 32
    )
    result = {
        "model": str(args.model),
        "split_sha256": file_sha256(args.split_manifest),
        "test": saved_model_metrics(args.model, test_gen, labels),
        "external_test": saved_model_metrics(args.model, external_gen, labels),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "test_accuracy": result["test"]["accuracy"],
        "test_macro_f1": result["test"]["macro_f1"],
        "external_accuracy": result["external_test"]["accuracy"],
    }, indent=2))


if __name__ == "__main__":
    main()
