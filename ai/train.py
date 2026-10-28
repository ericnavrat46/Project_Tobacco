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
DATASET_ROOT = os.path.join(BASE_DIR, 'dataset', 'dataset')
MODEL_SAVE_PATH = os.path.join(BASE_DIR, 'models', 'tobacco_model.h5')
METADATA_SAVE_PATH = os.path.join(BASE_DIR, 'models', 'model_metadata.json')

IMG_SIZE = (224, 224)
BATCH_SIZE = 16
EPOCHS = 12

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
    Membaca dataset dari split train dan valid, melakukan crop daun sesuai
    koordinat bounding box, dan melakukan oversampling khusus kelas minoritas.
    """
    print("\n[1/4] Memuat dan memproses dataset daun tembakau ...")

    all_images = []
    all_labels = []

    splits_to_load = ['train', 'valid']

    for split in splits_to_load:
        split_dir = os.path.join(DATASET_ROOT, split)
        json_path = os.path.join(split_dir, '_annotations.createml.json')

        if not os.path.exists(json_path):
            print(f"  [WARN] File anotasi tidak ditemukan di {json_path}")
            continue

        with open(json_path, 'r') as f:
            annotations = json.load(f)

        print(f"  -> Memproses split '{split}': {len(annotations)} anotasi ditemukan.")

        for item in annotations:
            img_name = item.get('image', '')
            img_path = os.path.join(split_dir, img_name)

            if not os.path.exists(img_path) or not item.get('annotations'):
                continue

            # Ambil label pertama
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

                    # Crop daun jika koordinat bounding box valid
                    if 'x' in coord and 'y' in coord and 'width' in coord and 'height' in coord:
                        cx, cy = coord['x'], coord['y']
                        bw, bh = coord['width'], coord['height']
                        x1 = max(0, int(cx - bw / 2.0))
                        y1 = max(0, int(cy - bh / 2.0))
                        x2 = min(w_img, int(cx + bw / 2.0))
                        y2 = min(h_img, int(cy + bh / 2.0))

                        # Pastikan ukuran crop rasional
                        if (x2 - x1) > 20 and (y2 - y1) > 20:
                            leaf_img = full_img.crop((x1, y1, x2, y2))
                        else:
                            leaf_img = full_img
                    else:
                        leaf_img = full_img

                    # 1. Simpan gambar asli (resized)
                    processed = leaf_img.resize(IMG_SIZE, Image.Resampling.BILINEAR)
                    img_arr = np.array(processed, dtype=np.float32) / 255.0
                    all_images.append(img_arr)
                    all_labels.append(lbl_id)

                    # 2. TARGETED OVERSAMPLING & AUGMENTASI
                    # Daun Low Quality (Filler) sangat langka (cuma ~29), perbanyak 8x variasi
                    if lbl_id == 0:  # Low Quality
                        for _ in range(8):
                            aug_pil = augment_image_pil(leaf_img)
                            aug_res = aug_pil.resize(IMG_SIZE, Image.Resampling.BILINEAR)
                            all_images.append(np.array(aug_res, dtype=np.float32) / 255.0)
                            all_labels.append(lbl_id)

                    # Daun High Quality (Wrapper), tambahkan 1x variasi augmentasi
                    elif lbl_id == 2:  # High Quality
                        if random.random() > 0.4:
                            aug_pil = augment_image_pil(leaf_img)
                            aug_res = aug_pil.resize(IMG_SIZE, Image.Resampling.BILINEAR)
                            all_images.append(np.array(aug_res, dtype=np.float32) / 255.0)
                            all_labels.append(lbl_id)

            except Exception as e:
                # Lewati file rusak
                continue

    counter = Counter(all_labels)
    print("\n  Distribusi Dataset Setelah Pemotongan & Augmentasi:")
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

    # Hitung bobot kelas seimbang (Balanced Class Weights)
    class_weights_arr = compute_class_weight('balanced', classes=np.unique(y_raw), y=y_raw)
    class_weights = {int(i): float(class_weights_arr[i]) for i in range(len(class_weights_arr))}
    print(f"\n  Bobot Kelas Penyeimbang (Class Weights): {class_weights}")

    # One-hot encoding
    y = to_categorical(y_raw, num_classes=3)

    # Split Train & Validasi (80% Train, 20% Val)
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y_raw
    )
    print(f"  Total Data Training  : {len(X_train)} sampel")
    print(f"  Total Data Validasi  : {len(X_val)} sampel")

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

    # 3. Proses Training
    print("\n[3/4] Memulai Proses Training (Epoch: %d, Batch Size: %d) ..." % (EPOCHS, BATCH_SIZE))
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=4, restore_best_weights=True, verbose=1
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.5, patience=2, min_lr=1e-5, verbose=1
        )
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        class_weight=class_weights,
        callbacks=callbacks,
        verbose=1
    )

    # 4. Evaluasi & Laporan Performa
    print("\n[4/4] Mengevaluasi Performa Model pada Data Validasi ...")
    val_loss, val_acc = model.evaluate(X_val, y_val, verbose=0)
    print(f"  -> Akurasi Validasi Akhir : {val_acc * 100:.2f}%")
    print(f"  -> Loss Validasi Akhir    : {val_loss:.4f}")

    # Laporan Klasifikasi per Kategori
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

    # 5. Simpan Model & Metadata
    model.save(MODEL_SAVE_PATH)
    print(f"\n[SUKSES] Model berhasil disimpan di: {MODEL_SAVE_PATH}")

    # Simpan Metadata JSON
    metadata = {
        "model_architecture": "MobileNetV2",
        "input_shape": [IMG_SIZE[0], IMG_SIZE[1], 3],
        "classes": CLASS_NAMES,
        "class_mapping": {
            "0": {"code": "filler", "quality": "Low Quality"},
            "1": {"code": "binder", "quality": "Medium Quality"},
            "2": {"code": "wrapper", "quality": "High Quality"}
        },
        "validation_accuracy": round(float(val_acc), 4),
        "validation_loss": round(float(val_loss), 4),
        "dataset_total_samples": len(X),
        "training_epochs": len(history.history['loss'])
    }
    with open(METADATA_SAVE_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"[SUKSES] Metadata model disimpan di: {METADATA_SAVE_PATH}")
    print("=" * 65)
    print("Selesai! Sistem siap menjalankan klasifikasi real-time via ai/inference.py.")
    print("=" * 65 + "\n")


if __name__ == '__main__':
    train_model()
