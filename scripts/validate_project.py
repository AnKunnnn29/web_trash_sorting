#!/usr/bin/env python3
"""Validate dataset, frontend catalog, and trained-model label alignment."""

from __future__ import annotations

import json
import hashlib
import os
import re
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = BASE_DIR / "dataset"
MOCK_DATA_PATH = BASE_DIR / "src" / "mockData.js"
TRASH_ITEMS_JSON_PATH = BASE_DIR / "src" / "trashItems.json"
DATASET_MAPPING_PATH = BASE_DIR / "config" / "dataset-labels.json"
SAVED_LABELS_PATH = BASE_DIR / "saved_model_keras" / "labels.json"
TFJS_LABELS_PATH = BASE_DIR / "public" / "tfjs_model" / "labels.json"
TFJS_MODEL_PATH = BASE_DIR / "public" / "tfjs_model" / "model.json"
MODEL_BASELINE_PATH = BASE_DIR / "config" / "model-baseline.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VALID_CATEGORIES = {"green", "yellow", "red", "other"}
REQUIRED_ITEM_FIELDS = {"id", "name", "category", "emoji", "keywords", "tip", "impact"}


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def parse_trash_items() -> dict[str, dict[str, str]]:
    if TRASH_ITEMS_JSON_PATH.exists():
        data = json.loads(TRASH_ITEMS_JSON_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            fail(f"Frontend catalog must be a JSON array: {TRASH_ITEMS_JSON_PATH}")
        validate_trash_catalog(data)
        items = {
            str(item["id"]): item
            for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if not items:
            fail(f"Could not parse any trash items from {TRASH_ITEMS_JSON_PATH}")
        return items

    if not MOCK_DATA_PATH.exists():
        fail(f"Missing frontend catalog: {MOCK_DATA_PATH}")

    content = MOCK_DATA_PATH.read_text(encoding="utf-8")
    items: dict[str, dict[str, str]] = {}
    for block in re.findall(r"\{([^{}]+)\}", content, flags=re.DOTALL):
        if "id:" not in block:
            continue
        item: dict[str, str] = {}
        for key in ("id", "name", "category", "emoji"):
            match = re.search(rf"{key}:\s*['\"]([^'\"]+)['\"]", block)
            if match:
                item[key] = match.group(1)
        item_id = item.get("id")
        if item_id:
            items[item_id] = item
    if not items:
        fail("Could not parse any trashItems from src/mockData.js")
    return items


def validate_trash_catalog(data: list[object]) -> None:
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    invalid_items: list[str] = []

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            invalid_items.append(f"item[{index}] is not an object")
            continue

        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            invalid_items.append(f"item[{index}] has missing/invalid id")
            continue

        if item_id in seen_ids:
            duplicate_ids.add(item_id)
        seen_ids.add(item_id)

        missing_fields = sorted(REQUIRED_ITEM_FIELDS - set(item))
        if missing_fields:
            invalid_items.append(f"{item_id} missing fields: {', '.join(missing_fields)}")

        category = item.get("category")
        if category not in VALID_CATEGORIES:
            invalid_items.append(f"{item_id} has invalid category: {category!r}")

        keywords = item.get("keywords")
        if not isinstance(keywords, list) or not all(isinstance(kw, str) and kw.strip() for kw in keywords):
            invalid_items.append(f"{item_id} has invalid keywords")

    if duplicate_ids:
        fail("Duplicate trash item ids: " + ", ".join(sorted(duplicate_ids)))
    if invalid_items:
        fail("Invalid trash catalog entries: " + "; ".join(invalid_items))


def parse_folder_mapping() -> dict[str, str]:
    if not DATASET_MAPPING_PATH.exists():
        fail(f"Missing dataset mapping: {DATASET_MAPPING_PATH}")
    value = json.loads(DATASET_MAPPING_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"Dataset mapping must be a JSON object: {DATASET_MAPPING_PATH}")
    return {str(k): str(v) for k, v in value.items()}


def count_dataset_images() -> dict[str, int]:
    if not DATASET_DIR.exists():
        warn(f"Dataset directory is not available; skipping image-count checks: {DATASET_DIR}")
        return {}

    counts: dict[str, int] = {}
    for folder in sorted(DATASET_DIR.iterdir()):
        if not folder.is_dir():
            continue
        counts[folder.name] = sum(
            1
            for file_path in folder.iterdir()
            if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS
        )
    if not counts:
        warn("Dataset directory has no class folders; skipping image-count checks")
    return counts


def read_labels(path: Path) -> list[str] | None:
    if not path.exists():
        warn(f"Missing labels file: {path}")
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        fail(f"Labels file must be a JSON string array: {path}")
    duplicate_labels = sorted({label for label in data if data.count(label) > 1})
    if duplicate_labels:
        fail(f"{path} contains duplicate labels: {', '.join(duplicate_labels)}")
    return data


def validate_tfjs_model(expected_label_count: int | None) -> None:
    if not TFJS_MODEL_PATH.exists():
        warn(f"Missing TF.js model: {TFJS_MODEL_PATH}")
        return

    model_data = json.loads(TFJS_MODEL_PATH.read_text(encoding="utf-8"))
    model_format = model_data.get("format")
    if model_format != "graph-model":
        fail(f"TF.js model format is {model_format!r}; frontend expects 'graph-model'")

    model_dir = TFJS_MODEL_PATH.parent
    shard_paths = [
        path
        for group in model_data.get("weightsManifest", [])
        for path in group.get("paths", [])
    ]
    if not shard_paths:
        fail("TF.js model has no weight shard paths")

    missing_shards = [path for path in shard_paths if not (model_dir / path).is_file()]
    if missing_shards:
        fail("TF.js model is missing weight shards: " + ", ".join(missing_shards))

    outputs = model_data.get("signature", {}).get("outputs", {})
    output_shape = None
    if outputs:
        first_output = next(iter(outputs.values()))
        dims = first_output.get("tensorShape", {}).get("dim", [])
        if dims:
            output_shape = dims[-1].get("size")

    if expected_label_count is not None and output_shape not in (None, str(expected_label_count)):
        fail(
            "TF.js output class count does not match labels: "
            f"shape={output_shape}, labels={expected_label_count}"
        )

    ok(
        f"TF.js model is a graph-model, has {len(shard_paths)} weight shards, "
        "and matches the label count"
    )


def validate_model_baseline() -> None:
    if not MODEL_BASELINE_PATH.exists():
        warn(f"Missing model baseline metadata: {MODEL_BASELINE_PATH}")
        return

    metadata = json.loads(MODEL_BASELINE_PATH.read_text(encoding="utf-8"))
    expected_hashes = {
        TFJS_MODEL_PATH: metadata.get("modelJsonSha256"),
        TFJS_LABELS_PATH: metadata.get("labelsSha256"),
    }
    for path, expected_hash in expected_hashes.items():
        if not path.exists() or not expected_hash:
            fail(f"Baseline metadata cannot verify missing path/hash: {path}")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            fail(
                f"Baseline hash changed for {path.name}. "
                "Run the AI benchmark and update config/model-baseline.json intentionally."
            )
    ok(f"Model baseline metadata verified: {metadata.get('version', 'unknown')}")


def main() -> None:
    trash_items = parse_trash_items()
    folder_to_id = parse_folder_mapping()
    dataset_counts = count_dataset_images()

    ok(f"Parsed {len(trash_items)} frontend trash items")
    ok(f"Parsed {len(folder_to_id)} dataset folder mappings")
    if dataset_counts:
        ok(f"Found {len(dataset_counts)} dataset folders")
        missing_mapping = sorted(set(dataset_counts) - set(folder_to_id))
        if missing_mapping:
            fail("Dataset folders without mapping: " + ", ".join(missing_mapping))

    invalid_mapping_targets = sorted(set(folder_to_id.values()) - set(trash_items))
    if invalid_mapping_targets:
        fail("FOLDER_TO_ID targets missing from trashItems: " + ", ".join(invalid_mapping_targets))

    if dataset_counts:
        zero_image_folders = [folder for folder, count in dataset_counts.items() if count == 0]
        if zero_image_folders:
            fail("Dataset folders with no images: " + ", ".join(zero_image_folders))

        grouped_counts: dict[str, int] = {}
        for folder, count in dataset_counts.items():
            mapped_id = folder_to_id[folder]
            grouped_counts[mapped_id] = grouped_counts.get(mapped_id, 0) + count

        small_labels = sorted((label, count) for label, count in grouped_counts.items() if count < 100)
        if small_labels:
            warn(
                "Labels with fewer than 100 images after mapping: "
                + ", ".join(f"{label}={count}" for label, count in small_labels)
            )

    saved_labels = read_labels(SAVED_LABELS_PATH)
    tfjs_labels = read_labels(TFJS_LABELS_PATH)

    for label_path, labels in ((SAVED_LABELS_PATH, saved_labels), (TFJS_LABELS_PATH, tfjs_labels)):
        if labels is None:
            continue
        unknown_labels = sorted(set(labels) - set(trash_items))
        if unknown_labels:
            fail(f"{label_path} contains labels missing from trashItems: {', '.join(unknown_labels)}")
        ok(f"{label_path.name} contains {len(labels)} labels known by frontend")

    if saved_labels is not None and tfjs_labels is not None and saved_labels != tfjs_labels:
        fail("saved_model_keras labels.json and public/tfjs_model labels.json differ")

    validate_tfjs_model(len(tfjs_labels) if tfjs_labels is not None else None)
    validate_model_baseline()

    ok("Project validation passed")


if __name__ == "__main__":
    main()
