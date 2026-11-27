"""
===================================================================================
TobaccoGuard AI - Retraining Model Klasifikasi Mutu Daun Tembakau
===================================================================================
Fitur & Peningkatan Pipeline:
1. Parsing Anotasi Bounding Box (CreateML JSON) & Pemotongan Daun Presisi (ROI Crop).
2. Penanganan Ekstrem Class Imbalance (Low Quality hanya 29 sampel) via Targeted
   Augmentation / Oversampling (rotasi, flip, variasi brightness & contrast).
3. Augmentasi Simulasi Webcam (Random Brightness, Contrast, Saturation) agar tahan
   terhadap kondisi pencahayaan lampu gudang & auto-exposure kamera.
4. Transfer Learning MobileNetV2 (Pretrained ImageNet) + Balanced Class Weights.
5. Export Model:
   - ai/models/tobacco_model.h5
   - ai/models/model_metadata.json
===================================================================================
"""

import os
import sys
import json
import random
import numpy as np
from PIL import Image, ImageEnhance
from collections import Counter

# Konfigurasi Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('KERAS_HOME', os.path.join(BASE_DIR, '.keras_cache'))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATASET_ROOT = os.path.join(PROJECT_ROOT, 'data', 'Dataset')
MODEL_KERAS_PATH = os.path.join(BASE_DIR, 'models', 'tobacco_model.keras')
MODEL_SAVE_PATH = os.path.join(BASE_DIR, 'models', 'tobacco_model.h5')
TFLITE_SAVE_PATH = os.path.join(BASE_DIR, 'models', 'tobacco_model.tflite')
METADATA_SAVE_PATH = os.path.join(BASE_DIR, 'models', 'model_metadata.json')

IMG_SIZE = (224, 224)
BATCH_SIZE = 16
EPOCHS_PHASE1 = 8   # Tahap 1: Transfer Learning (Feature Extraction)
EPOCHS_PHASE2 = 6   # Tahap 2: Fine-Tuning 30 layer teratas

# Pemetaan Kelas Model Keras (Sesuai dengan routes/api_conveyor.py):
# 0: Low Quality  -> filler  (daun cacat/rajangan mutu rendah)
# 1: Medium Quality -> binder  (daun pengikat mutu sedang)
# 2: High Quality -> wrapper (daun mulus mutu tertinggi)
LABEL_MAP = {
    "Low Quality": 0,
    "Medium Quality": 1,
    "High Quality": 2
}
CLASS_NAMES = ["filler", "binder", "wrapper"]
QUALITY_NAMES = ["Low Quality", "Medium Quality", "High Quality"]


def augment_image_pil(img_pil):
    """
    Melakukan augmentasi simulasi pencahayaan webcam dan posisi daun:
    - Rotasi acak (90, 180, 270 atau sudut halus)
    - Flip horizontal / vertikal
    - Fluktuasi brightness (pencahayaan) & contrast
    """
    # 1. Flip
    if random.random() > 0.5:
        img_pil = img_pil.transpose(Image.FLIP_LEFT_RIGHT)
    if random.random() > 0.5:
        img_pil = img_pil.transpose(Image.FLIP_TOP_BOTTOM)

    # 2. Rotasi acak
    rot_angle = random.choice([0, 90, 180, 270]) + random.randint(-15, 15)
    img_pil = img_pil.rotate(rot_angle, expand=False, resample=Image.BICUBIC)

    # 3. Fluktuasi Brightness (Simulasi pencahayaan webcam)
    enh_bright = ImageEnhance.Brightness(img_pil)
    img_pil = enh_bright.enhance(random.uniform(0.8, 1.2))

    # 4. Fluktuasi Contrast (±20%)
    enh_contrast = ImageEnhance.Contrast(img_pil)
    img_pil = enh_contrast.enhance(random.uniform(0.8, 1.2))

    return img_pil


def load_dataset():
    """
    Membaca dataset daun tembakau dari folder DATASET_ROOT.
    Mendukung struktur folder per kelas (Filler/, Binder/, Wrapper/) tanpa CSV,
    serta fallback format _classes.csv / CreateML JSON.
    """
    print(f"\n[1/4] Memuat dan memproses dataset daun tembakau dari: {DATASET_ROOT}")

    all_images = []
    all_labels = []
    valid_exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')

    folder_label_map = {
        'filler': 0,
        'binder': 1,
        'wrapper': 2,
    }

    # -----------------------------------------------------------------
    # METODE 0: STRUKTUR FOLDER PER KELAS (Filler/, Binder/, Wrapper/)
    # -----------------------------------------------------------------
    if os.path.exists(DATASET_ROOT):
        subdirs = [d for d in os.listdir(DATASET_ROOT) if os.path.isdir(os.path.join(DATASET_ROOT, d))]
        matched_dirs = [d for d in subdirs if d.lower() in folder_label_map]
        if matched_dirs:
            for d in sorted(matched_dirs):
                lbl_id = folder_label_map[d.lower()]
                class_dir = os.path.join(DATASET_ROOT, d)
                files = [f for f in os.listdir(class_dir) if f.lower().endswith(valid_exts)]
                print(f"  -> Memuat folder '{d}' (kelas {CLASS_NAMES[lbl_id]}): {len(files)} gambar.")
                for fname in files:
                    img_path = os.path.join(class_dir, fname)
                    try:
                        with Image.open(img_path) as img:
                            img = img.convert('RGB')
                            processed = img.resize(IMG_SIZE, Image.Resampling.BILINEAR)
                            img_arr = np.array(processed, dtype=np.float32) / 255.0
                            all_images.append(img_arr)
                            all_labels.append(lbl_id)
                    except Exception:
                        continue

            counter = Counter(all_labels)
            print("\n  Distribusi Dataset yang Dimuat:")
            for lbl_id, count in sorted(counter.items()):
                print(f"    - Kelas {lbl_id} ({CLASS_NAMES[lbl_id].upper()} / {QUALITY_NAMES[lbl_id]}): {count} gambar")
            return np.array(all_images, dtype=np.float32), np.array(all_labels, dtype=np.int32)

    splits_to_load = ['train', 'valid', 'test']

    for split in splits_to_load:
        split_dir = os.path.join(DATASET_ROOT, split)
        if not os.path.exists(split_dir):
            continue

        csv_path = os.path.join(split_dir, '_classes.csv')
        json_path = os.path.join(split_dir, '_annotations.createml.json')

        # -------------------------------------------------------------
        # METODE 1: FORMAT MULTICLASS CLASSIFICATION (_classes.csv)
        # -------------------------------------------------------------
        if os.path.exists(csv_path):
            import pandas as pd
            df = pd.read_csv(csv_path)
            print(f"  -> Memproses split '{split}': {len(df)} entri ditemukan (_classes.csv).")

            for _, row in df.iterrows():
                fname = row['filename']
                img_path = os.path.join(split_dir, fname)
                if not os.path.exists(img_path):
                    continue

                active = [c.strip() for c in df.columns[1:] if row[c] == 1]
                act_str = ' '.join(active).lower()

                lbl_id = None
                if 'filler' in act_str or 'low' in act_str:
                    lbl_id = 0
                elif 'binder' in act_str or 'medium' in act_str:
                    lbl_id = 1
                elif 'wrapper' in act_str or 'high' in act_str:
                    lbl_id = 2

                if lbl_id is None:
                    continue

                try:
                    with Image.open(img_path) as img:
                        img = img.convert('RGB')
                        processed = img.resize(IMG_SIZE, Image.Resampling.BILINEAR)
                        img_arr = np.array(processed, dtype=np.float32) / 255.0
                        all_images.append(img_arr)
                        all_labels.append(lbl_id)
                except Exception:
                    continue

        # -------------------------------------------------------------
        # METODE 2: FORMAT CREATEML JSON (Legacy Fallback)
        # -------------------------------------------------------------
        elif os.path.exists(json_path):
            with open(json_path, 'r') as f:
                annotations = json.load(f)

            print(f"  -> Memproses split '{split}': {len(annotations)} anotasi ditemukan (_annotations.createml.json).")

            for item in annotations:
                img_name = item.get('image', '')
                img_path = os.path.join(split_dir, img_name)

                if not os.path.exists(img_path) or not item.get('annotations'):
                    continue

                ann = item['annotations'][0]
                lbl_str = ann.get('label')
                if lbl_str not in LABEL_MAP:
                    continue

                lbl_id = LABEL_MAP[lbl_str]
                coord = ann.get('coordinates', {})

                try:
                    with Image.open(img_path) as full_img:
                        full_img = full_img.convert('RGB')
                        w_img, h_img = full_img.size

                        if 'x' in coord and 'y' in coord and 'width' in coord and 'height' in coord:
                            cx, cy = coord['x'], coord['y']
                            bw, bh = coord['width'], coord['height']
                            x1 = max(0, int(cx - bw / 2.0))
                            y1 = max(0, int(cy - bh / 2.0))
                            x2 = min(w_img, int(cx + bw / 2.0))
                            y2 = min(h_img, int(cy + bh / 2.0))

                            if (x2 - x1) > 20 and (y2 - y1) > 20:
                                leaf_img = full_img.crop((x1, y1, x2, y2))
                            else:
                                leaf_img = full_img
                        else:
                            leaf_img = full_img

                        processed = leaf_img.resize(IMG_SIZE, Image.Resampling.BILINEAR)
                        img_arr = np.array(processed, dtype=np.float32) / 255.0
                        all_images.append(img_arr)
                        all_labels.append(lbl_id)
                except Exception:
                    continue

    counter = Counter(all_labels)
    print("\n  Distribusi Dataset yang Dimuat:")
    for lbl_id, count in sorted(counter.items()):
        print(f"    - Kelas {lbl_id} ({CLASS_NAMES[lbl_id].upper()} / {QUALITY_NAMES[lbl_id]}): {count} gambar")

    return np.array(all_images, dtype=np.float32), np.array(all_labels, dtype=np.int32)



def train_model():
    # Pastikan dependensi TensorFlow terpasang
    try:
        import tensorflow as tf
        from tensorflow.keras.applications import MobileNetV2
        from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout, BatchNormalization
        from tensorflow.keras.models import Model
        from tensorflow.keras.utils import to_categorical
        from sklearn.model_selection import train_test_split
        from sklearn.utils.class_weight import compute_class_weight
        from sklearn.metrics import classification_report
    except ImportError as e:
        print(f"\n[FATAL ERROR] TensorFlow / Scikit-learn belum terpasang: {e}")
        print("Silakan jalankan: pip install tensorflow scikit-learn")
        sys.exit(1)

    print("=" * 65)
    print("  TobaccoGuard AI - Pelatihan Model MobileNetV2 Daun Tembakau")
    print("=" * 65)

    os.makedirs(os.path.join(BASE_DIR, 'models'), exist_ok=True)

    # 1. Load dan Augmentasi Data
    X, y_raw = load_dataset()

    if len(X) == 0:
        print("[ERROR] Tidak ada dataset yang berhasil dimuat. Periksa folder ai/dataset/.")
        sys.exit(1)

    # Split Train & Validasi (80% Train, 20% Val) SEBELUM augmentasi agar validasi murni
    X_train, X_val, y_train_idx, y_val_idx = train_test_split(
        X, y_raw, test_size=0.20, random_state=42, stratify=y_raw
    )

    # Oversampling + Augmentasi khusus data TRAINING agar seimbang (terutama Wrapper)
    train_counts = Counter(y_train_idx)
    max_train_count = max(train_counts.values())
    aug_images = list(X_train)
    aug_labels = list(y_train_idx)

    for cls_id, count in sorted(train_counts.items()):
        needed = max_train_count - count
        if needed > 0:
            cls_indices = [i for i, lbl in enumerate(y_train_idx) if lbl == cls_id]
            print(f"  -> Augmentasi kelas {CLASS_NAMES[cls_id].upper()}: +{needed} gambar (dari {count} -> {max_train_count})")
            for _ in range(needed):
                src_idx = random.choice(cls_indices)
                pil_img = Image.fromarray((X_train[src_idx] * 255.0).astype(np.uint8))
                aug_pil = augment_image_pil(pil_img)
                aug_images.append(np.array(aug_pil, dtype=np.float32) / 255.0)
                aug_labels.append(cls_id)

    X_train = np.array(aug_images, dtype=np.float32)
    y_train_idx = np.array(aug_labels, dtype=np.int32)

    # Shuffle data training setelah augmentasi
    perm = np.random.RandomState(42).permutation(len(X_train))
    X_train = X_train[perm]
    y_train_idx = y_train_idx[perm]

    # Hitung ulang class_weights setelah balancing (seimbang = ~1.0)
    class_weights_arr = compute_class_weight('balanced', classes=np.unique(y_train_idx), y=y_train_idx)
    class_weights = {int(i): float(class_weights_arr[i]) for i in range(len(class_weights_arr))}
    print(f"\n  Bobot Kelas Penyeimbang (Class Weights): {class_weights}")

    y_train = to_categorical(y_train_idx, num_classes=3)
    y_val = to_categorical(y_val_idx, num_classes=3)
    print(f"  Total Data Training (setelah seimbang): {len(X_train)} sampel")
    print(f"  Total Data Validasi (murni asli)     : {len(X_val)} sampel")

    # 2. Bangun Model Transfer Learning (MobileNetV2)
    print("\n[2/4] Membangun Arsitektur Model (MobileNetV2 Transfer Learning) ...")
    base_model = MobileNetV2(
        weights='imagenet',
        include_top=False,
        input_shape=(IMG_SIZE[0], IMG_SIZE[1], 3)
    )
    base_model.trainable = False  # Freeze layer dasar MobileNetV2

    # Top classification head
    x = base_model.output
    x = GlobalAveragePooling2D(name='global_average_pooling')(x)
    x = BatchNormalization()(x)
    x = Dropout(0.3)(x)
    x = Dense(128, activation='relu', name='feature_dense')(x)
    x = Dropout(0.2)(x)
    predictions = Dense(3, activation='softmax', name='quality_prediction')(x)

    model = Model(inputs=base_model.input, outputs=predictions)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )

    # =========================================================================
    # 3. PROSES PELATIHAN 2 TAHAP (TRANSFER LEARNING + FINE-TUNING)
    # =========================================================================
    print("\n" + "=" * 65)
    print("  TAHAP 1: FEATURE EXTRACTION (Base Model Frozen)")
    print("  Epoch: %d, Batch Size: %d, Learning Rate: 0.001" % (EPOCHS_PHASE1, BATCH_SIZE))
    print("=" * 65)

    callbacks_p1 = [
        tf.keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=3, restore_best_weights=True, verbose=1
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.5, patience=2, min_lr=1e-5, verbose=1
        )
    ]

    history_p1 = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=EPOCHS_PHASE1,
        batch_size=BATCH_SIZE,
        class_weight=class_weights,
        callbacks=callbacks_p1,
        verbose=1
    )

    # -------------------------------------------------------------------------
    # TAHAP 2: FINE-TUNING (Unfreeze 30 Layer Teratas MobileNetV2)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("  TAHAP 2: FINE-TUNING (Membuka 30 Lapisan Teratas MobileNetV2)")
    print("  Epoch: %d, Learning Rate: 1e-5 (Preservasi Bobot ImageNet)" % EPOCHS_PHASE2)
    print("=" * 65)

    base_model.trainable = True
    # Bekukan semua layer kecuali 30 layer terakhir
    for layer in base_model.layers[:-30]:
        layer.trainable = False

    unfrozen_count = sum(1 for layer in base_model.layers if layer.trainable)
    print(f"  -> Total Layer MobileNetV2: {len(base_model.layers)}")
    print(f"  -> Layer yang dibuka untuk Fine-Tuning: {unfrozen_count} layer teratas")

    # Re-compile dengan learning rate SANGAT KECIL (1e-5)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )

    callbacks_p2 = [
        tf.keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=3, restore_best_weights=True, verbose=1
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.5, patience=2, min_lr=1e-6, verbose=1
        )
    ]

    history_p2 = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=EPOCHS_PHASE2,
        batch_size=BATCH_SIZE,
        class_weight=class_weights,
        callbacks=callbacks_p2,
        verbose=1
    )

    # =========================================================================
    # 4. EVALUASI & LAPORAN PERFORMA
    # =========================================================================
    print("\n" + "=" * 65)
    print("[4/4] Mengevaluasi Performa Model pada Data Validasi...")
    val_loss, val_acc = model.evaluate(X_val, y_val, verbose=0)
    print(f"  -> Akurasi Validasi Akhir : {val_acc * 100:.2f}%")
    print(f"  -> Loss Validasi Akhir    : {val_loss:.4f}")

    # Prediksi data validasi
    y_val_pred = model.predict(X_val, verbose=0)
    y_true_indices = np.argmax(y_val, axis=1)
    y_pred_indices = np.argmax(y_val_pred, axis=1)

    report = classification_report(
        y_true_indices, y_pred_indices,
        target_names=CLASS_NAMES,
        output_dict=True
    )

    print("\n  Laporan Klasifikasi Mutu (Precision / Recall / F1-Score):")
    for cls in CLASS_NAMES:
        cls_data = report.get(cls, {})
        print(f"    - {cls.upper():<8} : Precision={cls_data.get('precision', 0)*100:.1f}%, Recall={cls_data.get('recall', 0)*100:.1f}%, F1={cls_data.get('f1-score', 0)*100:.1f}%")

    # Buat grafik evaluasi & Confusion Matrix
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from sklearn.metrics import confusion_matrix
        import itertools

        reports_dir = os.path.join(BASE_DIR, 'reports')
        os.makedirs(reports_dir, exist_ok=True)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
        fig.suptitle('Evaluasi Model MobileNetV2 (Transfer Learning & Fine-Tuning)', fontsize=14, fontweight='bold')

        # 1. Confusion Matrix
        cm = confusion_matrix(y_true_indices, y_pred_indices)
        im = ax1.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        ax1.set_title('Confusion Matrix 3x3', fontsize=12, fontweight='bold')
        plt.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
        tick_marks = np.arange(len(CLASS_NAMES))
        ax1.set_xticks(tick_marks)
        ax1.set_xticklabels([c.upper() for c in CLASS_NAMES])
        ax1.set_yticks(tick_marks)
        ax1.set_yticklabels([c.upper() for c in CLASS_NAMES])

        thresh = cm.max() / 2.
        for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
            ax1.text(j, i, format(cm[i, j], 'd'),
                     horizontalalignment="center",
                     color="white" if cm[i, j] > thresh else "black",
                     fontweight='bold', fontsize=12)
        ax1.set_ylabel('Label Sebenarnya (Ground Truth)', fontsize=10)
        ax1.set_xlabel('Hasil Prediksi Model', fontsize=10)

        # 2. Kurva Akurasi Gabungan
        acc_combined = history_p1.history['accuracy'] + history_p2.history['accuracy']
        val_acc_combined = history_p1.history['val_accuracy'] + history_p2.history['val_accuracy']
        epochs_range = range(1, len(acc_combined) + 1)

        ax2.plot(epochs_range, acc_combined, 'b-o', label='Training Accuracy', linewidth=2)
        ax2.plot(epochs_range, val_acc_combined, 'g-s', label='Validation Accuracy', linewidth=2)
        ax2.axvline(x=len(history_p1.history['accuracy']), color='r', linestyle='--', label='Batas Fine-Tuning')
        ax2.set_title('Kurva Akurasi (Tahap 1 vs Tahap 2)', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Epoch', fontsize=10)
        ax2.set_ylabel('Akurasi', fontsize=10)
        ax2.set_ylim([0.4, 1.02])
        ax2.legend(loc='lower right')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        eval_chart_path = os.path.join(reports_dir, 'model_evaluation.png')
        plt.savefig(eval_chart_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"  -> Grafik evaluasi tersimpan di: {eval_chart_path}")
    except Exception as e:
        print(f"  [WARN] Gagal membuat plot evaluasi: {e}")

    # =========================================================================
    # 5. SIMPAN MODEL (.KERAS, .H5 & .TFLITE) & METADATA
    # =========================================================================
    model.save(MODEL_KERAS_PATH)
    print(f"\n[SUKSES] Model Keras (.keras) berhasil disimpan di: {MODEL_KERAS_PATH}")
    model.save(MODEL_SAVE_PATH)
    print(f"[SUKSES] Model Keras (.h5) berhasil disimpan di: {MODEL_SAVE_PATH}")

    # Ekspor ke TensorFlow Lite (.tflite) untuk Edge/IoT (Poin 7)
    try:
        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        tflite_model = converter.convert()
        with open(TFLITE_SAVE_PATH, 'wb') as f:
            f.write(tflite_model)
        tflite_size_mb = os.path.getsize(TFLITE_SAVE_PATH) / (1024 * 1024)
        print(f"[SUKSES] Model Edge/IoT (.tflite) berhasil disimpan di: {TFLITE_SAVE_PATH} ({tflite_size_mb:.2f} MB)")
    except Exception as e:
        print(f"[WARN] Konversi TFLite dilewati: {e}")

    # Simpan Metadata JSON Lengkap
    metadata = {
        "model_architecture": "MobileNetV2 (Fine-Tuned)",
        "input_shape": [IMG_SIZE[0], IMG_SIZE[1], 3],
        "classes": CLASS_NAMES,
        "class_mapping": {
            "0": {"code": "filler", "quality": "Low Quality"},
            "1": {"code": "binder", "quality": "Medium Quality"},
            "2": {"code": "wrapper", "quality": "High Quality"}
        },
        "total_parameters": int(model.count_params()),
        "fine_tuning": {
            "enabled": True,
            "unfrozen_layers": unfrozen_count,
            "phase1_epochs": len(history_p1.history['loss']),
            "phase2_epochs": len(history_p2.history['loss']),
            "learning_rate_phase2": 1e-5
        },
        "validation_accuracy": round(float(val_acc), 4),
        "validation_loss": round(float(val_loss), 4),
        "classification_report": report,
        "dataset_total_samples": len(X),
        "training_epochs": len(history_p1.history['loss']) + len(history_p2.history['loss'])
    }
    with open(METADATA_SAVE_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"[SUKSES] Metadata model disimpan di: {METADATA_SAVE_PATH}")
    print("=" * 65)
    print("Selesai! Model Fine-Tuned & TFLite siap digunakan.")
    print("=" * 65 + "\n")


if __name__ == '__main__':
    train_model()
