# train_final.py
"""
Full training pipeline for multi-label tobacco classification.
- Phase 1: Train head only (base frozen) for warmup
- Phase 2: Fine-tune entire model with low learning rate
- Data augmentation, early stopping, learning rate reduction
- Evaluate on test set
- Save class_names.json for inference integration
"""

import argparse
import os
import json
from pathlib import Path

import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.metrics import classification_report, multilabel_confusion_matrix

# ── Clean class name mapping ──────────────────────────────────────────
CLEAN_NAMES = {
    "(Low": "Low",
    "Binder(Medium": "Binder_Medium",
    "Filler": "Filler",
    "Quality)": "Quality",
    "Wrapper(High": "Wrapper_High",
}


def load_data(csv_path: str, images_dir: str):
    df = pd.read_csv(csv_path)
    filename_col = df.columns[0]
    label_cols = df.columns[1:]
    class_names_raw = [c.strip() for c in label_cols]
    class_names = [CLEAN_NAMES.get(c, c) for c in class_names_raw]

    image_paths = df[filename_col].apply(lambda x: os.path.join(images_dir, x)).values
    labels = df[label_cols].astype(int).values
    return image_paths, labels, class_names


def preprocess_image(path, label):
    img = tf.io.read_file(path)
    img = tf.image.decode_jpeg(img, channels=3)
    img = tf.image.resize(img, (224, 224))
    img = tf.cast(img, tf.float32) / 255.0
    return img, label


def augment(image, label):
    image = tf.image.random_flip_left_right(image)
    image = tf.image.random_flip_up_down(image)
    image = tf.image.random_brightness(image, max_delta=0.2)
    image = tf.image.random_contrast(image, lower=0.8, upper=1.2)
    image = tf.image.random_saturation(image, lower=0.8, upper=1.2)
    image = tf.clip_by_value(image, 0.0, 1.0)
    return image, label


def build_dataset(image_paths, labels, batch_size, shuffle=True, do_augment=False):
    ds = tf.data.Dataset.from_tensor_slices((list(image_paths), labels))
    ds = ds.map(preprocess_image, num_parallel_calls=tf.data.AUTOTUNE)
    if do_augment:
        ds = ds.map(augment, num_parallel_calls=tf.data.AUTOTUNE)
    if shuffle:
        ds = ds.shuffle(buffer_size=len(image_paths))
    ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds


def create_model(num_classes: int):
    base = tf.keras.applications.MobileNetV2(
        weights="imagenet", include_top=False, input_shape=(224, 224, 3)
    )
    base.trainable = False  # Phase 1: freeze base

    inputs = tf.keras.Input(shape=(224, 224, 3))
    x = base(inputs, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    x = tf.keras.layers.Dense(128, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation="sigmoid")(x)
    model = tf.keras.Model(inputs, outputs)
    return model, base


def main():
    parser = argparse.ArgumentParser(description="Train multi-label tobacco classifier")
    parser.add_argument("--train-csv", required=True, help="Path to train CSV")
    parser.add_argument("--train-images", required=True, help="Folder with train images")
    parser.add_argument("--test-csv", default=None, help="Path to test CSV (optional)")
    parser.add_argument("--test-images", default=None, help="Folder with test images")
    parser.add_argument("--valid-csv", default=None, help="Path to valid CSV (optional)")
    parser.add_argument("--valid-images", default=None, help="Folder with valid images")
    parser.add_argument("--epochs-phase1", type=int, default=10, help="Epochs for phase 1 (head only)")
    parser.add_argument("--epochs-phase2", type=int, default=20, help="Epochs for phase 2 (fine-tune)")
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()

    # ── Load data ─────────────────────────────────────────────────────
    train_paths, train_labels, class_names = load_data(args.train_csv, args.train_images)
    print(f"Classes: {class_names}")
    print(f"Total train images: {len(train_paths)}")

    # ── Validation set ────────────────────────────────────────────────
    if args.valid_csv and args.valid_images:
        val_paths, val_labels, _ = load_data(args.valid_csv, args.valid_images)
        print(f"Using separate validation set: {len(val_paths)} images")
    else:
        # Split 15% from train
        n = len(train_paths)
        idx = np.arange(n)
        np.random.seed(42)
        np.random.shuffle(idx)
        split = int(0.85 * n)
        val_idx = idx[split:]
        train_idx = idx[:split]
        val_paths, val_labels = train_paths[val_idx], train_labels[val_idx]
        train_paths, train_labels = train_paths[train_idx], train_labels[train_idx]
        print(f"Split: {len(train_paths)} train / {len(val_paths)} val")

    train_ds = build_dataset(train_paths, train_labels, args.batch, shuffle=True, do_augment=True)
    val_ds = build_dataset(val_paths, val_labels, args.batch, shuffle=False, do_augment=False)

    # ── Build model ───────────────────────────────────────────────────
    num_classes = train_labels.shape[1]
    model, base = create_model(num_classes)

    # ── Callbacks ─────────────────────────────────────────────────────
    model_dir = Path("ai/models")
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "tobacco_model.keras"

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=5, restore_best_weights=True
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3, min_lr=1e-6
        ),
        tf.keras.callbacks.ModelCheckpoint(
            str(model_path), monitor="val_loss", save_best_only=True, verbose=1
        ),
    ]

    # ── Phase 1: Train head only ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("PHASE 1: Training head (base frozen)")
    print("=" * 60)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs_phase1,
        callbacks=callbacks,
    )

    # ── Phase 2: Fine-tune entire model ───────────────────────────────
    print("\n" + "=" * 60)
    print("PHASE 2: Fine-tuning entire model")
    print("=" * 60)
    base.trainable = True
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs_phase2,
        callbacks=callbacks,
    )

    # ── Load best model ───────────────────────────────────────────────
    model = tf.keras.models.load_model(str(model_path))
    print(f"\nBest model loaded from {model_path}")

    # ── Evaluate on validation set ────────────────────────────────────
    print("\n" + "=" * 60)
    print("VALIDATION SET EVALUATION")
    print("=" * 60)
    y_pred_val = (model.predict(val_ds) > 0.5).astype(int)
    report_val = classification_report(val_labels, y_pred_val, target_names=class_names, output_dict=True)
    print(classification_report(val_labels, y_pred_val, target_names=class_names))

    # ── Evaluate on test set (if provided) ────────────────────────────
    report_test = None
    if args.test_csv and args.test_images:
        print("\n" + "=" * 60)
        print("TEST SET EVALUATION")
        print("=" * 60)
        test_paths, test_labels, _ = load_data(args.test_csv, args.test_images)
        test_ds = build_dataset(test_paths, test_labels, args.batch, shuffle=False, do_augment=False)
        y_pred_test = (model.predict(test_ds) > 0.5).astype(int)
        report_test = classification_report(test_labels, y_pred_test, target_names=class_names, output_dict=True)
        conf_mat_test = multilabel_confusion_matrix(test_labels, y_pred_test)
        print(classification_report(test_labels, y_pred_test, target_names=class_names))

    # ── Save outputs ──────────────────────────────────────────────────
    out_dir = Path("ai/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "classification_report_val.json", "w") as f:
        json.dump(report_val, f, indent=2)
    print(f"Validation report saved to {out_dir / 'classification_report_val.json'}")

    if report_test:
        with open(out_dir / "classification_report_test.json", "w") as f:
            json.dump(report_test, f, indent=2)
        np.savetxt(
            out_dir / "confusion_matrix_test.csv",
            conf_mat_test.reshape(conf_mat_test.shape[0], -1),
            delimiter=",",
            fmt="%d",
        )
        print(f"Test report saved to {out_dir / 'classification_report_test.json'}")
        print(f"Test confusion matrix saved to {out_dir / 'confusion_matrix_test.csv'}")

    # ── Save class names for inference ────────────────────────────────
    with open(model_dir / "class_names.json", "w") as f:
        json.dump(class_names, f, indent=2)
    print(f"Class names saved to {model_dir / 'class_names.json'}")

    print("\n✅ Training complete!")


if __name__ == "__main__":
    main()

