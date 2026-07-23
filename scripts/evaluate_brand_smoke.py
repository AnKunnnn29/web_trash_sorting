#!/usr/bin/env python3
"""Smoke-test KUN, LOF and MILO cartons with baseline and best candidate."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
import tensorflow as tf


BASE_DIR = Path(__file__).resolve().parents[1]
TEST_ROOT = BASE_DIR / "tmp" / "brand-smoke-test"
REPORT_JSON = BASE_DIR / "reports" / "ai-kun-lof-milo-smoke.json"
REPORT_MD = BASE_DIR / "reports" / "ai-kun-lof-milo-smoke.md"
EXPECTED = "milk_carton"
MODELS = {
    "baseline": BASE_DIR / "saved_model_keras",
    "E4-best-seed": (
        BASE_DIR / "model_candidates" / "e4-seed-20260724" / "saved_model"
    ),
    "E4-refresh-20260726": (
        BASE_DIR / "model_candidates" / "e4-seed-20260726" / "saved_model"
    ),
}
SOURCES = {
    "kun": [
        "https://www.lof.vn/vi/brand/kun?type=5",
        "https://www.bachhoaxanh.com/sua-tuoi/thung-48-hop-sua-tuoi-tiet-trung-it-duong-lof-kun-100-sua-tuoi-180ml",
        "https://30day.com.vn/sua-kun-100-tuoi-it-duong-180ml",
    ],
    "lof": [
        "https://www.lof.vn/en/brand/lof",
        "https://www.bachhoaxanh.com/sua-ca-cao-socola/sua-lua-mach-huong-socola-bac-ha-lof-malto-hop-180ml",
    ],
    "milo": [
        "https://www.kidsplaza.vn/loc-4-hop-sua-milo-active-go-180ml-cho-be-tren-6-tuoi.html",
        "https://www.bachhoaxanh.com/sua-ca-cao-socola/hop-thuc-uong-lua-mach-uong-lien-milo-hop-180ml/",
    ],
}


def load_labels(model_dir: Path) -> list[str]:
    return json.loads((model_dir / "labels.json").read_text(encoding="utf-8"))


def load_image(path: Path) -> np.ndarray:
    with Image.open(path) as source:
        source = source.convert("RGBA")
        background = Image.new("RGBA", source.size, "white")
        image = Image.alpha_composite(background, source).convert("RGB")
        image = image.resize((224, 224), Image.BILINEAR)
    return np.asarray(image, dtype=np.float32)


def unique_samples() -> list[tuple[str, Path]]:
    samples = []
    seen = set()
    for brand_dir in sorted(TEST_ROOT.iterdir()):
        if not brand_dir.is_dir():
            continue
        for path in sorted(brand_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            samples.append((brand_dir.name, path))
    return samples


def infer(model_dir: Path, samples: list[tuple[str, Path]]) -> list[dict]:
    labels = load_labels(model_dir)
    loaded = tf.saved_model.load(str(model_dir))
    signature = loaded.signatures["serving_default"]
    batch = np.stack([load_image(path) for _, path in samples])
    outputs = signature(tf.constant(batch))
    probabilities = next(iter(outputs.values())).numpy()
    results = []
    for (brand, path), scores in zip(samples, probabilities):
        ranking = np.argsort(scores)[::-1][:3]
        results.append({
            "brand": brand,
            "file": str(path.relative_to(BASE_DIR)).replace("\\", "/"),
            "expected": EXPECTED,
            "predicted": labels[int(ranking[0])],
            "confidence": float(scores[ranking[0]]),
            "accepted_at_45": bool(scores[ranking[0]] >= 0.45),
            "correct": labels[int(ranking[0])] == EXPECTED,
            "top3": [
                {"label": labels[int(index)], "confidence": float(scores[index])}
                for index in ranking
            ],
        })
    return results


def aggregate(results: list[dict]) -> dict:
    grouped = defaultdict(list)
    for result in results:
        grouped[result["brand"]].append(result)
    summary = {}
    for brand, items in sorted(grouped.items()):
        correct = sum(item["correct"] for item in items)
        accepted = [item for item in items if item["accepted_at_45"]]
        summary[brand] = {
            "samples": len(items),
            "top1_accuracy": correct / len(items),
            "accepted": len(accepted),
            "accepted_accuracy": (
                sum(item["correct"] for item in accepted) / len(accepted)
                if accepted else 0.0
            ),
            "predictions": dict(Counter(item["predicted"] for item in items)),
        }
    return summary


def write_report(payload: dict) -> None:
    lines = [
        "# KUN / LOF / MILO carton smoke test",
        "",
        "> Product-page images collected after training. They are useful for a packaging "
        "smoke test but do not replace real camera photos.",
        "",
        f"- Unique images: {payload['sample_count']}",
        "- Expected output: `milk_carton`",
        "- Acceptance threshold: 45%",
        "",
        "## Summary",
        "",
        "| Model | Brand | Correct | Accepted | Predictions |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for model_name, model_result in payload["models"].items():
        for brand, summary in model_result["summary"].items():
            predictions = ", ".join(
                f"{label}: {count}"
                for label, count in sorted(summary["predictions"].items())
            )
            lines.append(
                f"| {model_name} | {brand.upper()} | "
                f"{sum(item['correct'] for item in model_result['results'] if item['brand'] == brand)}/{summary['samples']} "
                f"({summary['top1_accuracy'] * 100:.1f}%) | "
                f"{summary['accepted']}/{summary['samples']} | {predictions} |"
            )
    lines.extend([
        "",
        "## Per-image baseline results",
        "",
        "| Brand | Image | Top-1 | Confidence | Top-2 |",
        "| --- | --- | --- | ---: | --- |",
    ])
    for item in payload["models"]["baseline"]["results"]:
        lines.append(
            f"| {item['brand'].upper()} | `{Path(item['file']).name}` | "
            f"{item['predicted']} | {item['confidence'] * 100:.1f}% | "
            f"{item['top3'][1]['label']} ({item['top3'][1]['confidence'] * 100:.1f}%) |"
        )
    lines.extend([
        "",
        "## Sources",
        "",
    ])
    for brand, urls in SOURCES.items():
        lines.append(f"- {brand.upper()}: " + ", ".join(f"<{url}>" for url in urls))
    lines.extend([
        "",
        "The application classifies packaging/material, not brand identity. Therefore "
        "KUN, LOF and MILO cartons are correct only when the output is `milk_carton`.",
        "",
    ])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    samples = unique_samples()
    if not samples:
        raise SystemExit(f"No test images found in {TEST_ROOT}")
    models = {}
    for name, model_dir in MODELS.items():
        results = infer(model_dir, samples)
        models[name] = {
            "model_dir": str(model_dir.relative_to(BASE_DIR)).replace("\\", "/"),
            "summary": aggregate(results),
            "results": results,
        }
    payload = {
        "expected_label": EXPECTED,
        "sample_count": len(samples),
        "sources": SOURCES,
        "models": models,
    }
    REPORT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_report(payload)
    print(f"Brand smoke test complete: {len(samples)} images")
    for model_name, result in models.items():
        print(model_name, json.dumps(result["summary"], ensure_ascii=False))
    print(REPORT_MD)


if __name__ == "__main__":
    main()
