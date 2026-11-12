"""
===================================================================================
TobaccoGuard AI - Perbandingan Transfer Learning
MobileNetV2 vs AlexNet (Arsitektur Asli Krizhevsky 2012)

Kedua model dilatih dengan protokol Transfer Learning 2 Tahap:
  Tahap 1: Feature Extraction (Backbone Dibekukan / Frozen)
  Tahap 2: Fine-Tuning (Unfreeze Layer Atas, Learning Rate Kecil)

Maksimum 50 Epochs | Early Stopping | Model Checkpoint
===================================================================================
"""

import os
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


# =============================================================================
# KONFIGURASI
# =============================================================================
BASE_DIR    = Path(r"D:\laragon\www\Tobacco")
DATA_DIR    = BASE_DIR / "data"
MODELS_DIR  = BASE_DIR / "ai" / "models"
OUTPUTS_DIR = BASE_DIR / "ai" / "outputs"
REPORTS_DIR = BASE_DIR / "ai" / "reports"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES  = ["filler", "binder", "wrapper"]
CLASS_LABELS = ["Filler (Low)", "Binder (Medium)", "Wrapper (High)"]
IMG_SIZE     = (224, 224)
BATCH_SIZE   = 32
MAX_EPOCHS   = 50
PATIENCE     = 6


# =============================================================================
# 1. MUAT DATASET DARI CSV ROBOFLOW
# =============================================================================
print("==================================================================")
print("  TobaccoGuard AI - Pelatihan Komparasi MobileNetV2 vs AlexNet")
print("  Keduanya Menggunakan Metode Transfer Learning 2 Tahap")
print("==================================================================")

# -- Baca CSV dan gambar per split (train / valid / test) --
all_paths  = {"train": [], "valid": [], "test": []}
all_labels = {"train": [], "valid": [], "test": []}

for split in ["train", "valid", "test"]:
    csv_file = DATA_DIR / split / "_classes.csv"
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV tidak ditemukan: {csv_file}")

    df = pd.read_csv(csv_file)
    filename_col = df.columns[0]
    label_cols   = df.columns[1:]

    for _, row in df.iterrows():
        img_name  = str(row[filename_col]).strip()
        full_path = str(DATA_DIR / split / img_name)

        if not os.path.exists(full_path):
            continue

        # Tentukan kelas berdasarkan kolom aktif
        cls_idx = 0  # default filler
        for c in label_cols:
            if "wrapper" in c.lower() and row[c] == 1:
                cls_idx = 2
                break
            elif "binder" in c.lower() and row[c] == 1:
                cls_idx = 1
                break

        all_paths[split].append(full_path)
        all_labels[split].append(cls_idx)

train_paths  = np.array(all_paths["train"])
train_labels = np.array(all_labels["train"])
val_paths    = np.array(all_paths["valid"])
val_labels   = np.array(all_labels["valid"])
test_paths   = np.array(all_paths["test"])
test_labels  = np.array(all_labels["test"])

print(f"Dataset dimuat:")
print(f"  - Train : {len(train_paths)} gambar")
print(f"  - Valid : {len(val_paths)} gambar")
print(f"  - Test  : {len(test_paths)} gambar")


# =============================================================================
# 2. HITUNG CLASS WEIGHTS & BUAT TF.DATA PIPELINE
# =============================================================================
unique_classes = np.unique(train_labels)
weights = compute_class_weight('balanced', classes=unique_classes, y=train_labels)
class_weights_dict = {int(cls): float(w) for cls, w in zip(unique_classes, weights)}
print(f"Bobot Kelas: {class_weights_dict}")

# -- Fungsi pra-pemrosesan & augmentasi sebagai lambda tf --
def preprocess(path, label):
    img = tf.io.read_file(path)
    img = tf.image.decode_jpeg(img, channels=3)
    img = tf.image.resize(img, IMG_SIZE)
    img = tf.cast(img, tf.float32) / 255.0
    return img, label

def augment(img, label):
    img = tf.image.random_flip_left_right(img)
    img = tf.image.random_flip_up_down(img)
    img = tf.image.random_brightness(img, max_delta=0.1)
    img = tf.image.random_contrast(img, lower=0.9, upper=1.1)
    img = tf.clip_by_value(img, 0.0, 1.0)
    return img, label

# Buat dataset pipeline
train_ds = tf.data.Dataset.from_tensor_slices((train_paths, train_labels))
train_ds = train_ds.map(preprocess, num_parallel_calls=tf.data.AUTOTUNE)
train_ds = train_ds.map(augment, num_parallel_calls=tf.data.AUTOTUNE)
train_ds = train_ds.shuffle(buffer_size=min(len(train_paths), 1000))
train_ds = train_ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)

val_ds = tf.data.Dataset.from_tensor_slices((val_paths, val_labels))
val_ds = val_ds.map(preprocess, num_parallel_calls=tf.data.AUTOTUNE)
val_ds = val_ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)

test_ds = tf.data.Dataset.from_tensor_slices((test_paths, test_labels))
test_ds = test_ds.map(preprocess, num_parallel_calls=tf.data.AUTOTUNE)
test_ds = test_ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)


# =============================================================================
# 3. LATIH MODEL 1: MOBILENETV2 (TRANSFER LEARNING + FINE-TUNING)
# =============================================================================
print("\n" + "=" * 75)
print("  MODEL 1: MobileNetV2 (Transfer Learning + Fine-Tuning)")
print("=" * 75)

mob_save_path = MODELS_DIR / "tobacco_model_mobilenet_cmp.keras"
mob_start_time = time.time()

# -- Bangun arsitektur MobileNetV2 --
mob_base = tf.keras.applications.MobileNetV2(
    weights="imagenet", include_top=False, input_shape=(224, 224, 3)
)
mob_base.trainable = False  # Tahap 1: Freeze

mob_inputs  = tf.keras.Input(shape=(224, 224, 3))
x = mob_base(mob_inputs, training=False)
x = tf.keras.layers.GlobalAveragePooling2D()(x)
x = tf.keras.layers.Dropout(0.3)(x)
x = tf.keras.layers.Dense(128, activation="relu")(x)
x = tf.keras.layers.Dropout(0.2)(x)
mob_outputs = tf.keras.layers.Dense(3, activation="softmax", name="prediction")(x)
mob_model   = tf.keras.Model(mob_inputs, mob_outputs, name="MobileNetV2_Transfer")

# -- TAHAP 1: Feature Extraction (15 epoch, backbone frozen, LR=1e-3) --
print("\n>>> [TAHAP 1] Feature Extraction (15 Epoch, Backbone Frozen, LR=1e-3)")
mob_model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"]
)

mob_h1 = mob_model.fit(
    train_ds, validation_data=val_ds, epochs=15,
    class_weight=class_weights_dict,
    callbacks=[
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5, verbose=1)
    ],
    verbose=1
)

# -- TAHAP 2: Fine-Tuning (Unfreeze 30 layer teratas, LR=1e-5) --
print("\n>>> [TAHAP 2] Fine-Tuning (Unfreeze 30 Layer Teratas, LR=1e-5)")
mob_base.trainable = True
for layer in mob_base.layers[:-30]:
    layer.trainable = False

mob_model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"]
)

remaining_epochs_mob = MAX_EPOCHS - len(mob_h1.history['loss'])
mob_h2 = mob_model.fit(
    train_ds, validation_data=val_ds, epochs=remaining_epochs_mob,
    class_weight=class_weights_dict,
    callbacks=[
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=PATIENCE, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3, min_lr=1e-7, verbose=1),
        tf.keras.callbacks.ModelCheckpoint(str(mob_save_path), monitor="val_loss", save_best_only=True, verbose=0)
    ],
    verbose=1
)

mob_time = time.time() - mob_start_time

# Gabungkan history kedua tahap
mob_hist = {
    'loss':         mob_h1.history['loss']         + mob_h2.history['loss'],
    'accuracy':     mob_h1.history['accuracy']     + mob_h2.history['accuracy'],
    'val_loss':     mob_h1.history['val_loss']     + mob_h2.history['val_loss'],
    'val_accuracy': mob_h1.history['val_accuracy'] + mob_h2.history['val_accuracy'],
    'phase1_cutoff': len(mob_h1.history['loss'])
}

# Muat model terbaik
if mob_save_path.exists():
    mob_model = tf.keras.models.load_model(str(mob_save_path))


# =============================================================================
# 4. LATIH MODEL 2: ALEXNET MURNI (TRANSFER LEARNING + FINE-TUNING)
# =============================================================================
print("\n" + "=" * 75)
print("  MODEL 2: AlexNet Murni / Krizhevsky 2012 (Transfer Learning + Fine-Tuning)")
print("=" * 75)

alex_save_path = MODELS_DIR / "tobacco_model_alexnet_cmp.keras"
alex_start_time = time.time()

# -- Bangun backbone AlexNet (5 Conv layers) --
alex_backbone = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(224, 224, 3)),
    # Conv 1: Kernel 11x11, stride 4
    tf.keras.layers.Conv2D(96, (11, 11), strides=(4, 4), activation='relu', name='alex_conv1'),
    tf.keras.layers.BatchNormalization(name='alex_bn1'),
    tf.keras.layers.MaxPooling2D((3, 3), strides=(2, 2), name='alex_pool1'),
    # Conv 2: Kernel 5x5
    tf.keras.layers.Conv2D(256, (5, 5), padding='same', activation='relu', name='alex_conv2'),
    tf.keras.layers.BatchNormalization(name='alex_bn2'),
    tf.keras.layers.MaxPooling2D((3, 3), strides=(2, 2), name='alex_pool2'),
    # Conv 3, 4, 5: Kernel 3x3
    tf.keras.layers.Conv2D(384, (3, 3), padding='same', activation='relu', name='alex_conv3'),
    tf.keras.layers.Conv2D(384, (3, 3), padding='same', activation='relu', name='alex_conv4'),
    tf.keras.layers.Conv2D(256, (3, 3), padding='same', activation='relu', name='alex_conv5'),
    tf.keras.layers.BatchNormalization(name='alex_bn5'),
    tf.keras.layers.MaxPooling2D((3, 3), strides=(2, 2), name='alex_pool5'),
], name="AlexNet_Backbone")

alex_backbone.trainable = False  # Tahap 1: Freeze

# -- Kepala klasifikasi AlexNet (2x Dense 1024 + Softmax) --
alex_inputs = tf.keras.Input(shape=(224, 224, 3))
x = alex_backbone(alex_inputs, training=False)
x = tf.keras.layers.Flatten()(x)
x = tf.keras.layers.Dense(1024, activation="relu", name="alex_fc1")(x)
x = tf.keras.layers.Dropout(0.5)(x)
x = tf.keras.layers.Dense(1024, activation="relu", name="alex_fc2")(x)
x = tf.keras.layers.Dropout(0.5)(x)
alex_outputs = tf.keras.layers.Dense(3, activation="softmax", name="prediction")(x)
alex_model = tf.keras.Model(alex_inputs, alex_outputs, name="AlexNet_Transfer")

# -- TAHAP 1: Feature Extraction (15 epoch, backbone frozen, LR=1e-3) --
print("\n>>> [TAHAP 1] Feature Extraction (15 Epoch, Backbone Frozen, LR=1e-3)")
alex_model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"]
)

alex_h1 = alex_model.fit(
    train_ds, validation_data=val_ds, epochs=15,
    class_weight=class_weights_dict,
    callbacks=[
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5, verbose=1)
    ],
    verbose=1
)

# -- TAHAP 2: Fine-Tuning (Unfreeze 4 layer teratas, LR=1e-5) --
print("\n>>> [TAHAP 2] Fine-Tuning (Unfreeze 4 Layer Teratas, LR=1e-5)")
alex_backbone.trainable = True
for layer in alex_backbone.layers[:-4]:
    layer.trainable = False
for layer in alex_backbone.layers[-4:]:
    layer.trainable = True

alex_model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"]
)

remaining_epochs_alex = MAX_EPOCHS - len(alex_h1.history['loss'])
alex_h2 = alex_model.fit(
    train_ds, validation_data=val_ds, epochs=remaining_epochs_alex,
    class_weight=class_weights_dict,
    callbacks=[
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=PATIENCE, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3, min_lr=1e-7, verbose=1),
        tf.keras.callbacks.ModelCheckpoint(str(alex_save_path), monitor="val_loss", save_best_only=True, verbose=0)
    ],
    verbose=1
)

alex_time = time.time() - alex_start_time

# Gabungkan history kedua tahap
alex_hist = {
    'loss':         alex_h1.history['loss']         + alex_h2.history['loss'],
    'accuracy':     alex_h1.history['accuracy']     + alex_h2.history['accuracy'],
    'val_loss':     alex_h1.history['val_loss']     + alex_h2.history['val_loss'],
    'val_accuracy': alex_h1.history['val_accuracy'] + alex_h2.history['val_accuracy'],
    'phase1_cutoff': len(alex_h1.history['loss'])
}

# Muat model terbaik
if alex_save_path.exists():
    alex_model = tf.keras.models.load_model(str(alex_save_path))


# =============================================================================
# 5. EVALUASI KEDUA MODEL
# =============================================================================
print("\n" + "=" * 70)
print("  EVALUASI KEDUA MODEL")
print("=" * 70)

# Prediksi
mob_val_preds   = np.argmax(mob_model.predict(val_ds), axis=1)
mob_test_preds  = np.argmax(mob_model.predict(test_ds), axis=1)
alex_val_preds  = np.argmax(alex_model.predict(val_ds), axis=1)
alex_test_preds = np.argmax(alex_model.predict(test_ds), axis=1)

# Classification Report
mob_val_report  = classification_report(val_labels, mob_val_preds, target_names=CLASS_NAMES, output_dict=True, zero_division=0)
mob_test_report = classification_report(test_labels, mob_test_preds, target_names=CLASS_NAMES, output_dict=True, zero_division=0)
alex_val_report  = classification_report(val_labels, alex_val_preds, target_names=CLASS_NAMES, output_dict=True, zero_division=0)
alex_test_report = classification_report(test_labels, alex_test_preds, target_names=CLASS_NAMES, output_dict=True, zero_division=0)

# Confusion Matrix
mob_val_cm  = confusion_matrix(val_labels, mob_val_preds, labels=[0, 1, 2])
alex_val_cm = confusion_matrix(val_labels, alex_val_preds, labels=[0, 1, 2])
mob_test_cm  = confusion_matrix(test_labels, mob_test_preds, labels=[0, 1, 2])
alex_test_cm = confusion_matrix(test_labels, alex_test_preds, labels=[0, 1, 2])

# Metrik ringkasan
mob_val_acc  = mob_val_report['accuracy'] * 100
mob_val_f1   = mob_val_report['macro avg']['f1-score']
alex_val_acc = alex_val_report['accuracy'] * 100
alex_val_f1  = alex_val_report['macro avg']['f1-score']

print(f"\n--- HASIL VALIDASI MOBILENETV2 ---")
print(classification_report(val_labels, mob_val_preds, target_names=CLASS_NAMES, zero_division=0))

print(f"\n--- HASIL VALIDASI ALEXNET MURNI ---")
print(classification_report(val_labels, alex_val_preds, target_names=CLASS_NAMES, zero_division=0))


# =============================================================================
# 6. VISUALISASI GRAFIK PERBANDINGAN
# =============================================================================
fig = plt.figure(figsize=(15, 16))
fig.patch.set_facecolor('#faf8f5')
gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1.2, 1.0], hspace=0.35, wspace=0.25)
fig.suptitle('TobaccoGuard AI — Perbandingan Transfer Learning\nMobileNetV2 vs AlexNet (Original 2012)',
             fontsize=15, fontweight='bold', y=0.96)

# --- Kurva Akurasi ---
ax_acc = fig.add_subplot(gs[0, 0])
ax_acc.set_facecolor('#ffffff')
ax_acc.plot(mob_hist['accuracy'],     label='MobileNetV2 Train',  color='#2563eb', linewidth=2)
ax_acc.plot(mob_hist['val_accuracy'], label='MobileNetV2 Val',    color='#2563eb', linestyle='--', linewidth=2)
ax_acc.plot(alex_hist['accuracy'],     label='AlexNet Train',     color='#b45309', linewidth=2)
ax_acc.plot(alex_hist['val_accuracy'], label='AlexNet Val',       color='#b45309', linestyle='--', linewidth=2)
ax_acc.axvline(x=mob_hist['phase1_cutoff'], color='#6b7280', linestyle=':', label='Fase 1->2 (Fine-tune)')
ax_acc.set_title('Kurva Akurasi Training & Validasi', fontsize=12, fontweight='bold')
ax_acc.set_xlabel('Epoch'); ax_acc.set_ylabel('Accuracy')
ax_acc.grid(True, linestyle=':', alpha=0.6); ax_acc.legend(loc='lower right', fontsize=8)

# --- Kurva Loss ---
ax_loss = fig.add_subplot(gs[0, 1])
ax_loss.set_facecolor('#ffffff')
ax_loss.plot(mob_hist['loss'],     label='MobileNetV2 Train',  color='#2563eb', linewidth=2)
ax_loss.plot(mob_hist['val_loss'], label='MobileNetV2 Val',    color='#2563eb', linestyle='--', linewidth=2)
ax_loss.plot(alex_hist['loss'],     label='AlexNet Train',     color='#b45309', linewidth=2)
ax_loss.plot(alex_hist['val_loss'], label='AlexNet Val',       color='#b45309', linestyle='--', linewidth=2)
ax_loss.axvline(x=mob_hist['phase1_cutoff'], color='#6b7280', linestyle=':', label='Fase 1->2 (Fine-tune)')
ax_loss.set_title('Kurva Loss Training & Validasi', fontsize=12, fontweight='bold')
ax_loss.set_xlabel('Epoch'); ax_loss.set_ylabel('Loss')
ax_loss.grid(True, linestyle=':', alpha=0.6); ax_loss.legend(loc='upper right', fontsize=8)

# --- Confusion Matrix MobileNetV2 ---
ax_cm1 = fig.add_subplot(gs[1, 0])
im1 = ax_cm1.imshow(mob_val_cm, interpolation='nearest', cmap='Blues')
fig.colorbar(im1, ax=ax_cm1, fraction=0.046, pad=0.04)
ax_cm1.set(xticks=np.arange(3), yticks=np.arange(3), xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES,
           title=f'Confusion Matrix — MobileNetV2\nAcc: {mob_val_acc:.2f}% | F1: {mob_val_f1:.3f}',
           ylabel='Ground Truth', xlabel='Prediksi')
for i in range(3):
    for j in range(3):
        ax_cm1.text(j, i, str(mob_val_cm[i, j]), ha="center", va="center",
                    color="white" if mob_val_cm[i, j] > mob_val_cm.max() / 2 else "black", fontsize=9)

# --- Confusion Matrix AlexNet ---
ax_cm2 = fig.add_subplot(gs[1, 1])
im2 = ax_cm2.imshow(alex_val_cm, interpolation='nearest', cmap='YlOrBr')
fig.colorbar(im2, ax=ax_cm2, fraction=0.046, pad=0.04)
ax_cm2.set(xticks=np.arange(3), yticks=np.arange(3), xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES,
           title=f'Confusion Matrix — AlexNet Murni\nAcc: {alex_val_acc:.2f}% | F1: {alex_val_f1:.3f}',
           ylabel='Ground Truth', xlabel='Prediksi')
for i in range(3):
    for j in range(3):
        ax_cm2.text(j, i, str(alex_val_cm[i, j]), ha="center", va="center",
                    color="white" if alex_val_cm[i, j] > alex_val_cm.max() / 2 else "black", fontsize=9)

# --- Bar Chart Perbandingan ---
ax_bar = fig.add_subplot(gs[2, :])
ax_bar.set_facecolor('#ffffff')

mob_params  = mob_model.count_params() / 1e6
alex_params = alex_model.count_params() / 1e6

labels_bar = ['Val Accuracy (%)', 'Val Loss', 'Macro F1-Score', 'Params (Juta)', 'Waktu Latih (s/10)']
mob_vals   = [mob_val_acc,  min(mob_hist['val_loss']),  mob_val_f1,  mob_params,  mob_time / 10.0]
alex_vals  = [alex_val_acc, min(alex_hist['val_loss']), alex_val_f1, alex_params, alex_time / 10.0]

x = np.arange(len(labels_bar))
width = 0.35
bars1 = ax_bar.bar(x - width/2, mob_vals,  width, label='MobileNetV2',           color='#2563eb', edgecolor='white')
bars2 = ax_bar.bar(x + width/2, alex_vals, width, label='AlexNet (Original 2012)', color='#b45309', edgecolor='white')

ax_bar.set_title('Perbandingan Metrik Kinerja — MobileNetV2 vs AlexNet', fontsize=11, fontweight='bold')
ax_bar.set_xticks(x); ax_bar.set_xticklabels(labels_bar, fontsize=9, fontweight='semibold')
ax_bar.grid(axis='y', linestyle=':', alpha=0.6); ax_bar.legend(loc='upper right', fontsize=9)

for rect in list(bars1) + list(bars2):
    h = rect.get_height()
    ax_bar.annotate(f'{h:.2f}' if h >= 1 else f'{h:.3f}',
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=8, fontweight='bold')

output_fig = REPORTS_DIR / "perbandingan_transfer_learning_mobilenet_vs_alexnet.png"
plt.savefig(output_fig, dpi=200, bbox_inches='tight')
plt.close()
print(f"\n[SUKSES] Grafik disimpan ke: {output_fig}")


# =============================================================================
# 7. SIMPAN LAPORAN JSON
# =============================================================================
summary = {
    "dataset_total": len(train_paths) + len(val_paths) + len(test_paths),
    "dataset_train": len(train_paths),
    "dataset_valid": len(val_paths),
    "dataset_test":  len(test_paths),
    "mobilenetv2": {
        "validation_accuracy":  float(mob_val_acc),
        "validation_macro_f1":  float(mob_val_f1),
        "test_accuracy":        float(mob_test_report['accuracy'] * 100),
        "test_macro_f1":        float(mob_test_report['macro avg']['f1-score']),
        "epochs_run":           len(mob_hist['loss']),
        "training_time_seconds": float(mob_time),
        "total_params":         int(mob_model.count_params()),
        "val_confusion_matrix": mob_val_cm.tolist(),
        "test_confusion_matrix": mob_test_cm.tolist()
    },
    "alexnet": {
        "validation_accuracy":  float(alex_val_acc),
        "validation_macro_f1":  float(alex_val_f1),
        "test_accuracy":        float(alex_test_report['accuracy'] * 100),
        "test_macro_f1":        float(alex_test_report['macro avg']['f1-score']),
        "epochs_run":           len(alex_hist['loss']),
        "training_time_seconds": float(alex_time),
        "total_params":         int(alex_model.count_params()),
        "val_confusion_matrix": alex_val_cm.tolist(),
        "test_confusion_matrix": alex_test_cm.tolist()
    }
}

json_path = OUTPUTS_DIR / "comparison_results_alexnet.json"
with open(json_path, "w") as f:
    json.dump(summary, f, indent=2)

print(f"[SUKSES] Laporan JSON disimpan ke: {json_path}")
print("\n✅ Seluruh proses pelatihan komparasi MobileNetV2 vs AlexNet selesai!")
