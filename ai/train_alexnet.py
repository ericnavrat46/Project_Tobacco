"""
===================================================================================
TobaccoGuard AI - Pelatihan Model AlexNet (Pembanding Klasik Deep Learning)
===================================================================================
Tujuan:
Membandingkan arsitektur CNN klasik (AlexNet, 2012) dengan arsitektur CNN modern 
hemat komputasi (MobileNetV2, 2018) untuk klasifikasi mutu daun tembakau.

Karakteristik Arsitektur AlexNet:
- Lapisan Konvolusi Standar (Kernel besar: 11x11, 5x5, 3x3)
- Batch Normalization & Max Pooling (3x3, stride 2)
- Lapisan Fully Connected (Dense 1024) dengan Dropout 50%
- Output Softmax 3 kelas: Filler (Low), Binder (Medium), Wrapper (High)
===================================================================================
"""

import os
import sys
import json
import time
import numpy as np
from collections import Counter

# Konfigurasi Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_SAVE_PATH = os.path.join(BASE_DIR, 'models', 'tobacco_alexnet.h5')
METADATA_SAVE_PATH = os.path.join(BASE_DIR, 'models', 'alexnet_metadata.json')

IMG_SIZE = (224, 224)
BATCH_SIZE = 16
EPOCHS = 10

CLASS_NAMES = ["filler", "binder", "wrapper"]
QUALITY_NAMES = ["Low Quality", "Medium Quality", "High Quality"]


def build_alexnet(input_shape=(224, 224, 3), num_classes=3):
    """
    Membangun arsitektur AlexNet yang disesuaikan untuk citra 224x224x3
    dan 3 kelas mutu daun tembakau.
    """
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import Conv2D, MaxPooling2D, BatchNormalization, Flatten, Dense, Dropout

    model = Sequential([
        # 1st Convolutional Layer
        Conv2D(filters=96, kernel_size=(11, 11), strides=(4, 4), padding='valid', activation='relu', input_shape=input_shape, name='conv1'),
        BatchNormalization(name='bn1'),
        MaxPooling2D(pool_size=(3, 3), strides=(2, 2), name='pool1'),

        # 2nd Convolutional Layer
        Conv2D(filters=256, kernel_size=(5, 5), strides=(1, 1), padding='same', activation='relu', name='conv2'),
        BatchNormalization(name='bn2'),
        MaxPooling2D(pool_size=(3, 3), strides=(2, 2), name='pool2'),

        # 3rd Convolutional Layer
        Conv2D(filters=384, kernel_size=(3, 3), strides=(1, 1), padding='same', activation='relu', name='conv3'),

        # 4th Convolutional Layer
        Conv2D(filters=384, kernel_size=(3, 3), strides=(1, 1), padding='same', activation='relu', name='conv4'),

        # 5th Convolutional Layer
        Conv2D(filters=256, kernel_size=(3, 3), strides=(1, 1), padding='same', activation='relu', name='conv5'),
        BatchNormalization(name='bn5'),
        MaxPooling2D(pool_size=(3, 3), strides=(2, 2), name='pool5'),

        # Fully Connected Classifier
        Flatten(name='flatten'),
        Dense(1024, activation='relu', name='fc1'),
        Dropout(0.5, name='dropout1'),
        Dense(1024, activation='relu', name='fc2'),
        Dropout(0.5, name='dropout2'),
        Dense(num_classes, activation='softmax', name='quality_prediction')
    ], name='AlexNet_Tobacco')

    return model


def train_alexnet_model():
    try:
        import tensorflow as tf
        from sklearn.model_selection import train_test_split
        from sklearn.utils.class_weight import compute_class_weight
        from sklearn.metrics import classification_report, accuracy_score
    except ImportError as e:
        print(f"[ERROR] Dependensi TensorFlow / Scikit-learn belum lengkap: {e}")
        sys.exit(1)

    print("=" * 70)
    print("  TobaccoGuard AI - Pelatihan Model AlexNet (CNN Klasik Pembanding)")
    print("=" * 70)

    # 1. Muat dataset menggunakan pipeline pra-pemrosesan yang sama dengan train.py
    sys.path.append(BASE_DIR)
    from train import load_dataset

    X, y_raw = load_dataset()
    if len(X) == 0:
        print("[ERROR] Dataset tidak ditemukan.")
        sys.exit(1)

    # Bobot kelas seimbang
    class_weights_arr = compute_class_weight('balanced', classes=np.unique(y_raw), y=y_raw)
    class_weights = {int(i): float(class_weights_arr[i]) for i in range(len(class_weights_arr))}
    print(f"\n  Bobot Kelas Penyeimbang: {class_weights}")

    # One-hot encoding
    y = tf.keras.utils.to_categorical(y_raw, num_classes=3)

    # Split 80% train, 20% validation
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y_raw
    )
    print(f"  Sampel Train : {len(X_train)}")
    print(f"  Sampel Valid : {len(X_val)}")

    # 2. Bangun Model AlexNet
    print("\n[2/4] Menyusun Arsitektur AlexNet...")
    model = build_alexnet(input_shape=(IMG_SIZE[0], IMG_SIZE[1], 3), num_classes=3)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    model.summary()

    # 3. Training
    print("\n[3/4] Memulai Pelatihan AlexNet (Epoch: %d, Batch: %d)..." % (EPOCHS, BATCH_SIZE))
    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=4, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=2, min_lr=1e-6, verbose=1)
    ]

    start_time = time.time()
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        class_weight=class_weights,
        callbacks=callbacks,
        verbose=1
    )
    training_duration = round(time.time() - start_time, 2)

    # 4. Evaluasi
    print("\n[4/4] Evaluasi Kinerja Model AlexNet...")
    val_loss, val_acc = model.evaluate(X_val, y_val, verbose=0)
    print(f"  -> Akurasi Validasi AlexNet: {val_acc * 100:.2f}% | Loss: {val_loss:.4f}")

    y_val_pred_probs = model.predict(X_val, verbose=0)
    y_val_pred = np.argmax(y_val_pred_probs, axis=1)
    y_val_true = np.argmax(y_val, axis=1)

    report_dict = classification_report(
        y_val_true, y_val_pred,
        target_names=CLASS_NAMES,
        output_dict=True
    )
    print("\nClassification Report:")
    print(classification_report(y_val_true, y_val_pred, target_names=CLASS_NAMES))

    # Simpan Model
    os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)
    model.save(MODEL_SAVE_PATH)
    print(f"\n[SUCCESS] Model AlexNet tersimpan di: {MODEL_SAVE_PATH}")

    metadata = {
        "model_architecture": "AlexNet",
        "input_shape": [IMG_SIZE[0], IMG_SIZE[1], 3],
        "classes": CLASS_NAMES,
        "class_mapping": {
            "0": {"code": "filler", "quality": "Low Quality"},
            "1": {"code": "binder", "quality": "Medium Quality"},
            "2": {"code": "wrapper", "quality": "High Quality"}
        },
        "total_parameters": int(model.count_params()),
        "validation_accuracy": round(float(val_acc), 4),
        "validation_loss": round(float(val_loss), 4),
        "training_duration_seconds": training_duration,
        "classification_report": report_dict,
        "epochs_trained": len(history.history['loss'])
    }

    with open(METADATA_SAVE_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"[SUCCESS] Metadata AlexNet tersimpan di: {METADATA_SAVE_PATH}")


if __name__ == '__main__':
    train_alexnet_model()
