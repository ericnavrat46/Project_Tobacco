# train_from_binary_csv.py
"""Train a multi‑label classifier from a CSV where each label is a separate binary column.

Expected CSV format:
  - First column: image filename (relative to the images folder or absolute).
  - Remaining columns: binary (0/1) indicating presence of each class.
    Column headers (except the first) are used as class names.

Usage example::

    python ai\train_from_binary_csv.py \
        --csv "D:\\laragon\\www\\Tobacco\\data\\train\\_classes.csv" \
        --images "D:\\laragon\\www\\Tobacco\\data\\train" \
        --epochs 30 \
        --batch 32

Outputs:
  - Model saved to ``ai/models/tobacco_model.keras``
  - Classification report (JSON) saved to ``ai/outputs/classification_report.json``
  - Confusion matrix (CSV) saved to ``ai/outputs/confusion_matrix.csv``
"""

import argparse
import os
import json
from pathlib import Path

import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.metrics import classification_report, multilabel_confusion_matrix

def load_data(csv_path: str, images_dir: str):
    df = pd.read_csv(csv_path)
    # Ensure first column is the filename
    filename_col = df.columns[0]
    label_cols = df.columns[1:]
    class_names = [c.strip() for c in label_cols]
    # Build absolute image paths
    image_paths = df[filename_col].apply(lambda x: os.path.join(images_dir, x)).values
    # Load images lazily via tf.data
    labels = df[label_cols].astype(int).values
    return image_paths, labels, class_names

def preprocess_image(path, label, img_size=(224, 224)):
    img = tf.io.read_file(path)
    img = tf.image.decode_jpeg(img, channels=3)
    img = tf.image.resize(img, img_size)
    img = tf.cast(img, tf.float32) / 255.0
    return img, label

def build_dataset(image_paths, labels, batch_size, shuffle=True):
    ds = tf.data.Dataset.from_tensor_slices((list(image_paths), labels))
    ds = ds.map(lambda p, l: preprocess_image(p, l), num_parallel_calls=tf.data.AUTOTUNE)
    if shuffle:
        ds = ds.shuffle(buffer_size=len(image_paths))
    ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds

def create_model(num_classes: int):
    base = tf.keras.applications.MobileNetV2(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
    base.trainable = False  # fine‑tune later if needed
    inputs = tf.keras.Input(shape=(224, 224, 3))
    x = base(inputs, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    outputs = tf.keras.layers.Dense(num_classes, activation='sigmoid')(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def main():
    parser = argparse.ArgumentParser(description='Train multi‑label model from binary CSV')
    parser.add_argument('--csv', required=True, help='Path to CSV file')
    parser.add_argument('--images', required=True, help='Folder containing all images')
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--batch', type=int, default=32)
    args = parser.parse_args()

    image_paths, labels, class_names = load_data(args.csv, args.images)
    # Simple train/val split (15% validation)
    n = len(image_paths)
    idx = np.arange(n)
    np.random.shuffle(idx)
    split = int(0.85 * n)
    train_idx, val_idx = idx[:split], idx[split:]

    train_ds = build_dataset(image_paths[train_idx], labels[train_idx], batch_size=args.batch, shuffle=True)
    val_ds = build_dataset(image_paths[val_idx], labels[val_idx], batch_size=args.batch, shuffle=False)

    model = create_model(num_classes=labels.shape[1])
    model.fit(train_ds, validation_data=val_ds, epochs=args.epochs)

    # Save model
    model_dir = Path('ai/models')
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / 'tobacco_model.keras'
    model.save(str(model_path))
    print(f"Model saved to {model_path}")

    # Predictions on validation set for reporting
    y_true = labels[val_idx]
    y_pred = (model.predict(val_ds) > 0.5).astype(int)

    report = classification_report(y_true, y_pred, target_names=class_names, output_dict=True)
    conf_mat = multilabel_confusion_matrix(y_true, y_pred)

    out_dir = Path('ai/outputs')
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / 'classification_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    np.savetxt(out_dir / 'confusion_matrix.csv', conf_mat.reshape(conf_mat.shape[0], -1), delimiter=',', fmt='%d')
    print(f"Reports saved to {out_dir}")

if __name__ == '__main__':
    main()

