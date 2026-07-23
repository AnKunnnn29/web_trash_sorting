#!/usr/bin/env python3
"""Train a CPU-friendly MobileNetV2 candidate on a fixed clean split."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import Dense, Dropout, GlobalAveragePooling2D
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.regularizers import l2


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT = BASE_DIR / "reports" / "training-split.csv"
DEFAULT_OUTPUT_ROOT = BASE_DIR / "model_candidates"
IMG_SIZE = (224, 224)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=["E2", "E4"], required=True)
    parser.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--finetune-epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-train-per-class", type=int, default=160)
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Load an existing candidate and only regenerate its metrics.",
    )
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)


def load_split(path: Path, max_train_per_class: int, seed: int):
    df = pd.read_csv(path)
    df["filepath"] = df["filepath"].map(lambda value: str(BASE_DIR / value))
    train = df[df["split"] == "train"].copy()
    if max_train_per_class:
        train = (
            train.groupby("label", group_keys=False)
            .apply(lambda group: group.sample(
                n=min(len(group), max_train_per_class), random_state=seed
            ))
            .reset_index(drop=True)
        )
    validation = df[df["split"] == "validation"].copy()
    test = df[df["split"] == "test"].copy()
    external = df[df["split"] == "external_test"].copy()
    labels = sorted(df["label"].unique())
    return train, validation, test, external, labels


def generators(
    train, validation, test, external, labels, batch_size, seed=20260723
):
    train_datagen = ImageDataGenerator(
        rotation_range=18,
        width_shift_range=0.10,
        height_shift_range=0.10,
        zoom_range=0.15,
        brightness_range=(0.8, 1.2),
        horizontal_flip=True,
        fill_mode="nearest",
    )
    plain_datagen = ImageDataGenerator()
    common = {
        "x_col": "filepath",
        "y_col": "label",
        "target_size": IMG_SIZE,
        "batch_size": batch_size,
        "class_mode": "categorical",
        "classes": labels,
        "interpolation": "bilinear",
    }
    train_gen = train_datagen.flow_from_dataframe(
        dataframe=train, shuffle=True, seed=seed, **common
    )
    val_gen = plain_datagen.flow_from_dataframe(
        dataframe=validation, shuffle=False, **common
    )
    test_gen = plain_datagen.flow_from_dataframe(
        dataframe=test, shuffle=False, **common
    )
    external_gen = None
    if len(external):
        external_gen = plain_datagen.flow_from_dataframe(
            dataframe=external, shuffle=False, **common
        )
    return train_gen, val_gen, test_gen, external_gen


def build_model(num_classes: int, experiment: str):
    inputs = tf.keras.Input(shape=(224, 224, 3), name="input")
    base = MobileNetV2(
        weights="imagenet",
        include_top=False,
        input_shape=(224, 224, 3),
    )
    base.trainable = False
    x = tf.keras.layers.Lambda(preprocess_input, name="mobilenet_preprocess")(inputs)
    x = base(x, training=False)
    x = GlobalAveragePooling2D()(x)
    regularizer = l2(1e-4)
    dropout_rate = 0.2 if experiment == "E2" else 0.3
    x = Dense(256, activation="relu", kernel_regularizer=regularizer)(x)
    x = Dropout(dropout_rate)(x)
    outputs = Dense(num_classes, activation="softmax")(x)
    model = Model(inputs, outputs)
    smoothing = 0.0 if experiment == "E2" else 0.05
    model.compile(
        optimizer=Adam(learning_rate=1e-3),
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=smoothing),
        metrics=["accuracy"],
    )
    return model, base, smoothing


def callbacks():
    return [
        EarlyStopping(
            monitor="val_loss",
            patience=3,
            min_delta=0.002,
            restore_best_weights=True,
            verbose=1,
        ),
        ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=1,
            min_lr=1e-6,
            verbose=1,
        ),
    ]


def metrics_from_probabilities(probabilities, generator, labels):
    expected = np.asarray(generator.classes)
    predicted = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    accepted = confidence >= 0.45
    recalls = []
    per_label = {}
    for index, label in enumerate(labels):
        mask = expected == index
        support = int(mask.sum())
        true_positive = int(((predicted == index) & mask).sum())
        predicted_positive = int((predicted == index).sum())
        recall = true_positive / support if support else 0.0
        precision = true_positive / predicted_positive if predicted_positive else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )
        if support:
            recalls.append(f1)
        per_label[label] = {
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return {
        "accuracy": float((predicted == expected).mean()),
        "macro_f1": float(np.mean(recalls)),
        "average_confidence": float(confidence.mean()),
        "coverage_at_45": float(accepted.mean()),
        "accepted_accuracy": (
            float((predicted[accepted] == expected[accepted]).mean())
            if accepted.any() else 0.0
        ),
        "per_label": per_label,
    }


def classification_metrics(model, generator, labels):
    if generator is None:
        return None
    return metrics_from_probabilities(
        model.predict(generator, verbose=0), generator, labels
    )


def saved_model_metrics(saved_model_dir, generator, labels):
    if generator is None:
        return None
    loaded = tf.saved_model.load(str(saved_model_dir))
    infer = loaded.signatures["serving_default"]
    batches = []
    for index in range(len(generator)):
        images, _ = generator[index]
        outputs = infer(tf.constant(images))
        batches.append(next(iter(outputs.values())).numpy())
    probabilities = np.concatenate(batches, axis=0)[:len(generator.classes)]
    return metrics_from_probabilities(probabilities, generator, labels)


def merge_history(first, second=None):
    result = {
        key: [float(value) for value in values]
        for key, values in first.history.items()
    }
    if second:
        for key, values in second.history.items():
            result.setdefault(key, []).extend(float(value) for value in values)
    return result


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    set_seed(args.seed)
    output = args.output_root / f"{args.experiment.lower()}-seed-{args.seed}"
    output.mkdir(parents=True, exist_ok=True)
    saved_model_dir = output / "saved_model"
    train, validation, test, external, labels = load_split(
        args.split_manifest, args.max_train_per_class, args.seed
    )
    train_gen, val_gen, test_gen, external_gen = generators(
        train, validation, test, external, labels, args.batch_size, args.seed
    )
    if args.evaluate_only:
        if not saved_model_dir.exists():
            raise SystemExit(f"Candidate does not exist: {saved_model_dir}")
        metrics = {
            "experiment": args.experiment,
            "seed": args.seed,
            "split_sha256": file_sha256(args.split_manifest),
            "train_samples": len(train),
            "validation_samples": len(validation),
            "test_samples": len(test),
            "external_test_samples": len(external),
            "elapsed_seconds": 0,
            "history": {},
            "test": saved_model_metrics(saved_model_dir, test_gen, labels),
            "external_test": saved_model_metrics(
                saved_model_dir, external_gen, labels
            ),
        }
        (output / "metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return
    model, base, smoothing = build_model(len(labels), args.experiment)
    started = time.time()
    phase1 = model.fit(
        train_gen,
        validation_data=val_gen,
        epochs=args.epochs,
        callbacks=callbacks(),
    )
    phase1_weights = model.get_weights()
    phase1_best = min(phase1.history["val_loss"])

    for layer in base.layers[-30:]:
        if not isinstance(layer, tf.keras.layers.BatchNormalization):
            layer.trainable = True
    model.compile(
        optimizer=Adam(learning_rate=1e-5),
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=smoothing),
        metrics=["accuracy"],
    )
    phase2 = model.fit(
        train_gen,
        validation_data=val_gen,
        epochs=args.finetune_epochs,
        callbacks=callbacks(),
    )
    if min(phase2.history["val_loss"]) > phase1_best:
        model.set_weights(phase1_weights)

    @tf.function(input_signature=[
        tf.TensorSpec(shape=[None, 224, 224, 3], dtype=tf.float32, name="input")
    ])
    def serving_fn(input_tensor):
        return {"output": model(input_tensor, training=False)}

    tf.saved_model.save(
        model,
        str(saved_model_dir),
        signatures={"serving_default": serving_fn},
    )
    (saved_model_dir / "labels.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metrics = {
        "experiment": args.experiment,
        "seed": args.seed,
        "split_sha256": file_sha256(args.split_manifest),
        "train_samples": len(train),
        "validation_samples": len(validation),
        "test_samples": len(test),
        "external_test_samples": len(external),
        "elapsed_seconds": time.time() - started,
        "history": merge_history(phase1, phase2),
        "test": classification_metrics(model, test_gen, labels),
        "external_test": classification_metrics(model, external_gen, labels),
    }
    (output / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output),
        "test_accuracy": metrics["test"]["accuracy"],
        "test_macro_f1": metrics["test"]["macro_f1"],
        "external_accuracy": metrics["external_test"]["accuracy"],
        "elapsed_minutes": metrics["elapsed_seconds"] / 60,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
