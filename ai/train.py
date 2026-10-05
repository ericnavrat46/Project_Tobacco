"""
===================================================================================
TobaccoGuard AI - Training Script Klasifikasi Mutu Daun Tembakau
===================================================================================

TODO: Script ini akan diisi setelah dataset gambar daun tembakau tersedia.

Alur Training yang Direncanakan:
1. Load dataset dari folder ai/dataset/ (format ImageFolder Keras / PyTorch)
2. Augmentasi data (rotate, flip, brightness, zoom) untuk memperbanyak variasi
3. Transfer learning menggunakan model pretrained (MobileNetV2 / EfficientNetB0)
4. Fine-tune untuk 3 kelas: 'wrapper', 'binder', 'filler'
5. Evaluasi model (accuracy, confusion matrix, classification report)
6. Export model ke format .h5 dan .tflite (untuk deploy ke ESP32-CAM)
7. Simpan hasil ke folder ai/models/

Dataset yang Dibutuhkan (Download dari Roboflow):
- Minimum 200 gambar per kelas (600 total)
- Resolusi direkomendasikan: 224x224 px
- Format folder:
    ai/dataset/train/wrapper/   -> ~160 gambar
    ai/dataset/train/binder/    -> ~160 gambar
    ai/dataset/train/filler/    -> ~160 gambar
    ai/dataset/valid/wrapper/   -> ~40 gambar
    ai/dataset/valid/binder/    -> ~40 gambar
    ai/dataset/valid/filler/    -> ~40 gambar

Cara Menjalankan (setelah dataset tersedia):
    cd ai/
    pip install -r requirements.txt
    python train.py

===================================================================================
"""

import os
import json
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.models import Model
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split

print("=" * 60)
print("  TobaccoGuard AI - Training Script (TensorFlow)")
print("=" * 60)

BASE_DIR = os.path.dirname(__file__)
DATASET_DIR = os.path.join(BASE_DIR, 'dataset', 'dataset', 'train')
JSON_PATH = os.path.join(DATASET_DIR, '_annotations.createml.json')
MODEL_SAVE_PATH = os.path.join(BASE_DIR, 'models', 'tobacco_model.h5')

# Pastikan direktori model ada
os.makedirs(os.path.join(BASE_DIR, 'models'), exist_ok=True)

if not os.path.exists(JSON_PATH):
    print(f"Error: Anotasi JSON tidak ditemukan di {JSON_PATH}")
    print("Silakan ekstrak dataset ke folder yang benar.")
    exit(1)

# 1. Parsing Dataset JSON
print("Membaca anotasi dataset...")
with open(JSON_PATH, 'r') as f:
    annotations = json.load(f)

IMG_SIZE = (224, 224)
label_map = {"Low Quality": 0, "Medium Quality": 1, "High Quality": 2}
classes_name = ["Low Quality", "Medium Quality", "High Quality"]

images = []
labels = []

print("Memuat dan memproses gambar (ini mungkin memakan waktu)...")
valid_count = 0
for item in annotations:
    img_name = item['image']
    img_path = os.path.join(DATASET_DIR, img_name)
    
    if os.path.exists(img_path) and len(item['annotations']) > 0:
        # Ambil label pertama saja
        lbl_str = item['annotations'][0]['label']
        if lbl_str in label_map:
            try:
                # Load dan resize
                img = load_img(img_path, target_size=IMG_SIZE)
                img_arr = img_to_array(img) / 255.0  # Normalisasi
                images.append(img_arr)
                labels.append(label_map[lbl_str])
                valid_count += 1
            except Exception as e:
                print(f"Gagal memuat {img_name}: {e}")

print(f"Total gambar valid dimuat: {valid_count}")

if valid_count == 0:
    print("Tidak ada data untuk ditraining. Berhenti.")
    exit(1)

X = np.array(images)
y = to_categorical(np.array(labels), num_classes=3)

X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

# 2. Membangun Model Transfer Learning (MobileNetV2)
print("Membangun model AI (MobileNetV2)...")
base_model = MobileNetV2(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
base_model.trainable = False  # Freeze base model

x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dropout(0.2)(x)
x = Dense(128, activation='relu')(x)
predictions = Dense(3, activation='softmax')(x)

model = Model(inputs=base_model.input, outputs=predictions)
model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

# 3. Training Loop
print("Memulai proses training...")
EPOCHS = 10
BATCH_SIZE = 16

history = model.fit(
    X_train, y_train,
    validation_data=(X_val, y_val),
    epochs=EPOCHS,
    batch_size=BATCH_SIZE
)

# 4. Evaluasi & Simpan
print("\nTraining selesai! Mengevaluasi model...")
loss, accuracy = model.evaluate(X_val, y_val)
print(f"Validation Accuracy: {accuracy*100:.2f}%")

model.save(MODEL_SAVE_PATH)
print(f"Model berhasil disimpan di: {MODEL_SAVE_PATH}")
print("Sistem sekarang bisa melakukan klasifikasi nyata!")


