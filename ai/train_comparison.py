"""
===================================================================================
TobaccoGuard AI - Pelatihan & Perbandingan Transfer Learning
MobileNetV2 vs AlexNet (Arsitektur Asli AlexNet Krizhevsky 2012)
Menggunakan Dataset Baru: data/train, data/valid, data/test (3 Kelas: filler, binder, wrapper)
Protokol Transfer Learning:
  Tahap 1: Feature Extraction (Backbone Dibekukan / Frozen)
  Tahap 2: Fine-Tuning (Unfreeze Layer Atas dengan Learning Rate Sangat Kecil)
Maksimum 50 Epochs dengan Early Stopping & Model Checkpoint
===================================================================================
"""

import os
import sys
import time
import json
from pathlib import Path

import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Konfigurasi Path
BASE_DIR = Path(r"D:\laragon\www\Tobacco")
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "ai" / "models"
OUTPUTS_DIR = BASE_DIR / "ai" / "outputs"
REPORTS_DIR = BASE_DIR / "ai" / "reports"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = ["filler", "binder", "wrapper"]
CLASS_LABELS = ["Filler (Low)", "Binder (Medium)", "Wrapper (High)"]
IMG_SIZE = (224, 224)
BATCH_SIZE = 32
MAX_EPOCHS = 50
PATIENCE = 6

def extract_primary_class(row):
    """
    Ekstraksi kelas 0 (filler), 1 (binder), 2 (wrapper) dari format CSV Roboflow.
    """
    cols = row.index
    for c in cols:
        if "wrapper" in c.lower() and row[c] == 1:
            return 2
        elif "binder" in c.lower() and row[c] == 1:
            return 1
    return 0

def load_split_data(split_name):
    split_dir = DATA_DIR / split_name
    csv_file = split_dir / "_classes.csv"
    if not csv_file.exists():
        raise FileNotFoundError(f"File CSV {csv_file} tidak ditemukan!")

    df = pd.read_csv(csv_file)
    filename_col = df.columns[0]
    label_cols = df.columns[1:]

    image_paths = []
    labels = []
    for _, row in df.iterrows():
        img_name = str(row[filename_col]).strip()
        full_path = str(split_dir / img_name)
        if os.path.exists(full_path):
            cls_idx = extract_primary_class(row[label_cols])
            image_paths.append(full_path)
            labels.append(cls_idx)

    return np.array(image_paths), np.array(labels)

def preprocess_image(path, label):
    img = tf.io.read_file(path)
    img = tf.image.decode_jpeg(img, channels=3)
    img = tf.image.resize(img, IMG_SIZE)
    img = tf.cast(img, tf.float32) / 255.0
    return img, label

def augment_image(img, label):
    img = tf.image.random_flip_left_right(img)
    img = tf.image.random_flip_up_down(img)
    img = tf.image.random_brightness(img, max_delta=0.1)
    img = tf.image.random_contrast(img, lower=0.9, upper=1.1)
    img = tf.clip_by_value(img, 0.0, 1.0)
    return img, label

def create_dataset(paths, labels, batch_size=BATCH_SIZE, shuffle=False, augment=False):
    ds = tf.data.Dataset.from_tensor_slices((paths, labels))
    ds = ds.map(preprocess_image, num_parallel_calls=tf.data.AUTOTUNE)
    if augment:
        ds = ds.map(augment_image, num_parallel_calls=tf.data.AUTOTUNE)
    if shuffle:
        ds = ds.shuffle(buffer_size=min(len(paths), 1000))
    ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds

# =====================================================================
# 1. ARSITEKTUR 1: MOBILENETV2 (TRANSFER LEARNING + FINE-TUNING)
# =====================================================================
def build_mobilenetv2_transfer(num_classes=3):
    base_model = tf.keras.applications.MobileNetV2(
        weights="imagenet",
        include_top=False,
        input_shape=(224, 224, 3)
    )
    base_model.trainable = False  # Tahap 1: Freeze

    inputs = tf.keras.Input(shape=(224, 224, 3))
    x = base_model(inputs, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    x = tf.keras.layers.Dense(128, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation="softmax", name="prediction")(x)

    model = tf.keras.Model(inputs, outputs, name="MobileNetV2_Transfer")
    return model, base_model

# =====================================================================
# 2. ARSITEKTUR 2: ALEXNET MURNI (TRANSFER LEARNING + FINE-TUNING)
# Menggunakan 5 Conv layer asli Krizhevsky dkk. (2012)
# =====================================================================
def build_alexnet_transfer(num_classes=3):
    # Backbone ekstraktor fitur AlexNet (Conv 1 sampai Conv 5)
    alexnet_backbone = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(224, 224, 3)),
        # Conv 1
        tf.keras.layers.Conv2D(96, (11, 11), strides=(4, 4), activation='relu', name='alex_conv1'),
        tf.keras.layers.BatchNormalization(name='alex_bn1'),
        tf.keras.layers.MaxPooling2D((3, 3), strides=(2, 2), name='alex_pool1'),

        # Conv 2
        tf.keras.layers.Conv2D(256, (5, 5), padding='same', activation='relu', name='alex_conv2'),
        tf.keras.layers.BatchNormalization(name='alex_bn2'),
        tf.keras.layers.MaxPooling2D((3, 3), strides=(2, 2), name='alex_pool2'),

        # Conv 3, 4, 5
        tf.keras.layers.Conv2D(384, (3, 3), padding='same', activation='relu', name='alex_conv3'),
        tf.keras.layers.Conv2D(384, (3, 3), padding='same', activation='relu', name='alex_conv4'),
        tf.keras.layers.Conv2D(256, (3, 3), padding='same', activation='relu', name='alex_conv5'),
        tf.keras.layers.BatchNormalization(name='alex_bn5'),
        tf.keras.layers.MaxPooling2D((3, 3), strides=(2, 2), name='alex_pool5'),
    ], name="AlexNet_Backbone")

    alexnet_backbone.trainable = False  # Tahap 1: Freeze

    # Kepala Klasifikasi AlexNet (Dense 1024 x 2 + Softmax)
    inputs = tf.keras.Input(shape=(224, 224, 3))
    x = alexnet_backbone(inputs, training=False)
    x = tf.keras.layers.Flatten()(x)
    x = tf.keras.layers.Dense(1024, activation="relu", name="alex_fc1")(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    x = tf.keras.layers.Dense(1024, activation="relu", name="alex_fc2")(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation="softmax", name="prediction")(x)

    model = tf.keras.Model(inputs, outputs, name="AlexNet_Transfer")
    return model, alexnet_backbone


def train_two_phase_model(model_builder, unfreeze_layers_count, model_name, train_ds, val_ds, class_weights_dict, save_path):
    print(f"\n{'='*75}")
    print(f"  MEMULAI PELATIHAN DUA TAHAP: {model_name}")
    print(f"  Maksimum Epoch: {MAX_EPOCHS} | Early Stopping Patience: {PATIENCE}")
    print(f"{'='*75}")

    model, backbone = model_builder(num_classes=3)
    start_total_time = time.time()

    # -------------------------------------------------------------
    # TAHAP 1: FEATURE EXTRACTION (Backbone Frozen)
    # -------------------------------------------------------------
    phase1_epochs = min(15, MAX_EPOCHS // 3)
    print(f"\n>>> [TAHAP 1] Feature Extraction ({phase1_epochs} Epochs, Backbone Frozen, LR=1e-3)")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )

    cb_phase1 = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5, verbose=1)
    ]

    h1 = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=phase1_epochs,
        class_weight=class_weights_dict,
        callbacks=cb_phase1,
        verbose=1
    )

    # -------------------------------------------------------------
    # TAHAP 2: FINE-TUNING (Unfreeze Top Layers)
    # -------------------------------------------------------------
    print(f"\n>>> [TAHAP 2] Fine-Tuning (Unfreeze {unfreeze_layers_count} Layer Teratas, LR=1e-5)")
    backbone.trainable = True
    # Freeze layer bawah, buka unfreeze_layers_count layer teratas
    if unfreeze_layers_count > 0:
        for layer in backbone.layers[:-unfreeze_layers_count]:
            layer.trainable = False
        for layer in backbone.layers[-unfreeze_layers_count:]:
            layer.trainable = True
    else:
        # Unfreeze semua jika unfreeze_layers_count < 0
        for layer in backbone.layers:
            layer.trainable = True

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )

    remaining_epochs = MAX_EPOCHS - len(h1.history['loss'])
    cb_phase2 = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=PATIENCE, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3, min_lr=1e-7, verbose=1),
        tf.keras.callbacks.ModelCheckpoint(str(save_path), monitor="val_loss", save_best_only=True, verbose=0)
    ]

    h2 = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=remaining_epochs,
        class_weight=class_weights_dict,
        callbacks=cb_phase2,
        verbose=1
    )

    total_time = time.time() - start_total_time

    # Gabungkan history Tahap 1 dan Tahap 2
    combined_hist = {
        'loss': h1.history['loss'] + h2.history['loss'],
        'accuracy': h1.history['accuracy'] + h2.history['accuracy'],
        'val_loss': h1.history['val_loss'] + h2.history['val_loss'],
        'val_accuracy': h1.history['val_accuracy'] + h2.history['val_accuracy'],
        'phase1_cutoff': len(h1.history['loss'])
    }

    # Muat model terbaik yang disimpan checkpoint
    if save_path.exists():
        best_model = tf.keras.models.load_model(str(save_path))
    else:
        model.save(str(save_path))
        best_model = model

    return best_model, combined_hist, total_time


def main():
    print("==================================================================")
    print("  TobaccoGuard AI - Pelatihan Komparasi MobileNetV2 vs AlexNet")
    print("  Keduanya Menggunakan Metode Transfer Learning 2 Tahap")
    print("==================================================================")

    # 1. Load Data
    train_paths, train_labels = load_split_data("train")
    val_paths, val_labels = load_split_data("valid")
    test_paths, test_labels = load_split_data("test")

    print(f"Dataset dimuat:")
    print(f" - Train : {len(train_paths)} gambar")
    print(f" - Valid : {len(val_paths)} gambar")
    print(f" - Test  : {len(test_paths)} gambar")

    # Hitung class weights
    unique_classes = np.unique(train_labels)
    weights = compute_class_weight('balanced', classes=unique_classes, y=train_labels)
    class_weights_dict = {cls: float(w) for cls, w in zip(unique_classes, weights)}
    print(f"Bobot Kelas (Class Weights): {class_weights_dict}")

    train_ds = create_dataset(train_paths, train_labels, batch_size=BATCH_SIZE, shuffle=True, augment=True)
    val_ds = create_dataset(val_paths, val_labels, batch_size=BATCH_SIZE, shuffle=False, augment=False)
    test_ds = create_dataset(test_paths, test_labels, batch_size=BATCH_SIZE, shuffle=False, augment=False)

    # 2. Latih MobileNetV2 (Transfer Learning: Unfreeze 30 layer teratas pada Tahap 2)
    mob_path = MODELS_DIR / "tobacco_model_mobilenet_cmp.keras"
    mob_model, mob_hist, mob_time = train_two_phase_model(
        build_mobilenetv2_transfer,
        unfreeze_layers_count=30,
        model_name="MobileNetV2 (Transfer Learning + Fine-Tuning)",
        train_ds=train_ds,
        val_ds=val_ds,
        class_weights_dict=class_weights_dict,
        save_path=mob_path
    )

    # 3. Latih AlexNet Murni (Transfer Learning: Unfreeze 4 layer Conv teratas pada Tahap 2)
    alex_path = MODELS_DIR / "tobacco_model_alexnet_cmp.keras"
    alex_model, alex_hist, alex_time = train_two_phase_model(
        build_alexnet_transfer,
        unfreeze_layers_count=4,
        model_name="AlexNet Murni (Transfer Learning + Fine-Tuning)",
        train_ds=train_ds,
        val_ds=val_ds,
        class_weights_dict=class_weights_dict,
        save_path=alex_path
    )

    # 4. Evaluasi Kedua Model pada Data Testing
    print("\n" + "="*70)
    print("  EVALUASI KEDUA MODEL PADA DATA TESTING (34 SAMPEL)")
    print("="*70)

    # Prediksi Test Set
    mob_test_preds = np.argmax(mob_model.predict(test_ds), axis=1)
    alex_test_preds = np.argmax(alex_model.predict(test_ds), axis=1)

    mob_test_report = classification_report(test_labels, mob_test_preds, target_names=CLASS_NAMES, output_dict=True, zero_division=0)
    alex_test_report = classification_report(test_labels, alex_test_preds, target_names=CLASS_NAMES, output_dict=True, zero_division=0)

    mob_test_cm = confusion_matrix(test_labels, mob_test_preds, labels=[0, 1, 2])
    alex_test_cm = confusion_matrix(test_labels, alex_test_preds, labels=[0, 1, 2])

    # Prediksi Valid Set
    mob_val_preds = np.argmax(mob_model.predict(val_ds), axis=1)
    alex_val_preds = np.argmax(alex_model.predict(val_ds), axis=1)

    mob_val_report = classification_report(val_labels, mob_val_preds, target_names=CLASS_NAMES, output_dict=True, zero_division=0)
    alex_val_report = classification_report(val_labels, alex_val_preds, target_names=CLASS_NAMES, output_dict=True, zero_division=0)

    mob_val_cm = confusion_matrix(val_labels, mob_val_preds, labels=[0, 1, 2])
    alex_val_cm = confusion_matrix(val_labels, alex_val_preds, labels=[0, 1, 2])

    print(f"\n--- HASIL VALIDASI MOBILENETV2 ---")
    print(classification_report(val_labels, mob_val_preds, target_names=CLASS_NAMES, zero_division=0))

    print(f"\n--- HASIL VALIDASI ALEXNET MURNI ---")
    print(classification_report(val_labels, alex_val_preds, target_names=CLASS_NAMES, zero_division=0))

    # 5. Visualisasi & Plot Grafik Komparasi
    fig = plt.figure(figsize=(15, 16))
    fig.patch.set_facecolor('#faf8f5')
    gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1.2, 1.0], hspace=0.35, wspace=0.25)
    fig.suptitle('TobaccoGuard AI — Perbandingan Transfer Learning\nMobileNetV2 vs AlexNet (Original 2012)', fontsize=15, fontweight='bold', y=0.96)

    # --- 1. Kurva Akurasi ---
    ax_acc = fig.add_subplot(gs[0, 0])
    ax_acc.set_facecolor('#ffffff')
    ax_acc.plot(mob_hist['accuracy'], label='MobileNetV2 Train', color='#2563eb', linewidth=2)
    ax_acc.plot(mob_hist['val_accuracy'], label='MobileNetV2 Val', color='#2563eb', linestyle='--', linewidth=2)
    ax_acc.plot(alex_hist['accuracy'], label='AlexNet Train', color='#b45309', linewidth=2)
    ax_acc.plot(alex_hist['val_accuracy'], label='AlexNet Val', color='#b45309', linestyle='--', linewidth=2)
    
    mob_cutoff = mob_hist['phase1_cutoff']
    ax_acc.axvline(x=mob_cutoff, color='#6b7280', linestyle=':', label='Fase 1->2 (Fine-tune)')

    ax_acc.set_title('Kurva Akurasi Training & Validasi', fontsize=12, fontweight='bold')
    ax_acc.set_xlabel('Epoch', fontsize=10)
    ax_acc.set_ylabel('Accuracy', fontsize=10)
    ax_acc.grid(True, linestyle=':', alpha=0.6)
    ax_acc.legend(loc='lower right', fontsize=8)

    # --- 2. Kurva Loss ---
    ax_loss = fig.add_subplot(gs[0, 1])
    ax_loss.set_facecolor('#ffffff')
    ax_loss.plot(mob_hist['loss'], label='MobileNetV2 Train', color='#2563eb', linewidth=2)
    ax_loss.plot(mob_hist['val_loss'], label='MobileNetV2 Val', color='#2563eb', linestyle='--', linewidth=2)
    ax_loss.plot(alex_hist['loss'], label='AlexNet Train', color='#b45309', linewidth=2)
    ax_loss.plot(alex_hist['val_loss'], label='AlexNet Val', color='#b45309', linestyle='--', linewidth=2)
    ax_loss.axvline(x=mob_cutoff, color='#6b7280', linestyle=':', label='Fase 1->2 (Fine-tune)')

    ax_loss.set_title('Kurva Loss Training & Validasi', fontsize=12, fontweight='bold')
    ax_loss.set_xlabel('Epoch', fontsize=10)
    ax_loss.set_ylabel('Loss', fontsize=10)
    ax_loss.grid(True, linestyle=':', alpha=0.6)
    ax_loss.legend(loc='upper right', fontsize=8)

    # --- Helper Plot Confusion Matrix (Matplotlib Murni) ---
    def plot_custom_cm(ax, cm, title, cmap_name='Blues'):
        im = ax.imshow(cm, interpolation='nearest', cmap=plt.get_cmap(cmap_name))
        ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set(xticks=np.arange(cm.shape[1]),
               yticks=np.arange(cm.shape[0]),
               xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES,
               title=title,
               ylabel='Ground Truth',
               xlabel='Prediksi')
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, format(cm[i, j], 'd'),
                        ha="center", va="center",
                        color="white" if cm[i, j] > thresh else "black",
                        fontsize=9)
        ax.set_facecolor('#ffffff')

    # --- 3. Confusion Matrix MobileNetV2 (Valid) ---
    ax_cm1 = fig.add_subplot(gs[1, 0])
    mob_val_acc = mob_val_report['accuracy'] * 100
    mob_val_f1 = mob_val_report['macro avg']['f1-score']
    plot_custom_cm(ax_cm1, mob_val_cm, f'Confusion Matrix — MobileNetV2\nAcc: {mob_val_acc:.2f}% | F1: {mob_val_f1:.3f}', 'Blues')

    # --- 4. Confusion Matrix AlexNet (Valid) ---
    ax_cm2 = fig.add_subplot(gs[1, 1])
    alex_val_acc = alex_val_report['accuracy'] * 100
    alex_val_f1 = alex_val_report['macro avg']['f1-score']
    plot_custom_cm(ax_cm2, alex_val_cm, f'Confusion Matrix — AlexNet Murni\nAcc: {alex_val_acc:.2f}% | F1: {alex_val_f1:.3f}', 'YlOrBr')

    # --- 5. Bar Chart Perbandingan Kinerja ---
    ax_bar = fig.add_subplot(gs[2, :])
    ax_bar.set_facecolor('#ffffff')

    metrics_labels = [
        'Val Accuracy (%)',
        'Val Loss',
        'Macro F1-Score',
        'Params (Juta)',
        'Waktu Latih (s/10)'
    ]
    mob_params = mob_model.count_params() / 1e6
    alex_params = alex_model.count_params() / 1e6

    mob_bar_vals = [
        mob_val_acc,
        min(mob_hist['val_loss']),
        mob_val_f1,
        mob_params,
        mob_time / 10.0
    ]
    alex_bar_vals = [
        alex_val_acc,
        min(alex_hist['val_loss']),
        alex_val_f1,
        alex_params,
        alex_time / 10.0
    ]

    x = np.arange(len(metrics_labels))
    width = 0.35

    rects1 = ax_bar.bar(x - width/2, mob_bar_vals, width, label='MobileNetV2', color='#2563eb', edgecolor='white')
    rects2 = ax_bar.bar(x + width/2, alex_bar_vals, width, label='AlexNet (Original 2012)', color='#b45309', edgecolor='white')

    ax_bar.set_title('Perbandingan Metrik Kinerja — MobileNetV2 vs AlexNet', fontsize=11, fontweight='bold')
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(metrics_labels, fontsize=9, fontweight='semibold')
    ax_bar.grid(axis='y', linestyle=':', alpha=0.6)
    ax_bar.legend(loc='upper right', fontsize=9)

    for rect in rects1:
        h = rect.get_height()
        ax_bar.annotate(f'{h:.2f}' if h >= 1 else f'{h:.3f}',
                        xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, fontweight='bold')
    for rect in rects2:
        h = rect.get_height()
        ax_bar.annotate(f'{h:.2f}' if h >= 1 else f'{h:.3f}',
                        xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, fontweight='bold')

    output_fig_path = REPORTS_DIR / "perbandingan_transfer_learning_mobilenet_vs_alexnet.png"
    plt.savefig(output_fig_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"\n[SUKSES] Gambar grafik perbandingan disimpan ke: {output_fig_path}")

    # Simpan JSON Metadata Hasil Evaluasi
    summary_results = {
        "dataset_total": len(train_paths) + len(val_paths) + len(test_paths),
        "dataset_train": len(train_paths),
        "dataset_valid": len(val_paths),
        "dataset_test": len(test_paths),
        "mobilenetv2": {
            "validation_accuracy": float(mob_val_acc),
            "validation_macro_f1": float(mob_val_f1),
            "test_accuracy": float(mob_test_report['accuracy'] * 100),
            "test_macro_f1": float(mob_test_report['macro avg']['f1-score']),
            "epochs_run": len(mob_hist['loss']),
            "training_time_seconds": float(mob_time),
            "total_params": int(mob_model.count_params()),
            "val_confusion_matrix": mob_val_cm.tolist(),
            "test_confusion_matrix": mob_test_cm.tolist()
        },
        "alexnet": {
            "validation_accuracy": float(alex_val_acc),
            "validation_macro_f1": float(alex_val_f1),
            "test_accuracy": float(alex_test_report['accuracy'] * 100),
            "test_macro_f1": float(alex_test_report['macro avg']['f1-score']),
            "epochs_run": len(alex_hist['loss']),
            "training_time_seconds": float(alex_time),
            "total_params": int(alex_model.count_params()),
            "val_confusion_matrix": alex_val_cm.tolist(),
            "test_confusion_matrix": alex_test_cm.tolist()
        }
    }

    with open(OUTPUTS_DIR / "comparison_results_alexnet.json", "w") as f:
        json.dump(summary_results, f, indent=2)

    print(f"[SUKSES] Laporan JSON disimpan ke: {OUTPUTS_DIR / 'comparison_results_alexnet.json'}")
    print("\n✅ Seluruh proses pelatihan komparasi MobileNetV2 vs AlexNet selesai dengan sukses!")

if __name__ == "__main__":
    main()
