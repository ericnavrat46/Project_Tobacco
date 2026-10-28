"""
===================================================================================
TobaccoGuard AI - Pelatihan Model SVM (Support Vector Machine) Klasifikasi Daun
===================================================================================
Pendekatan Machine Learning Klasik berbasis Ekstraksi Fitur Vektor:
1. Pemotongan Region of Interest (ROI) daun tembakau berdasarkan anotasi Bounding Box.
2. Ekstraksi Vektor Fitur Komprehensif:
   - Warna (HSV & Lab color space: mean, std, skewness) -> mendeteksi kematangan daun
   - Tekstur (Gradien Sobel & statistik intensitas) -> mendeteksi kehalusan serat
3. Normalisasi Vektor menggunakan StandardScaler.
4. Klasifikasi menggunakan Support Vector Classifier (RBF Kernel, Class Weight Balanced).
5. Output Model: ai/models/tobacco_svm.pkl & metadata JSON.
===================================================================================
"""

import os
import sys
import json
import random
import joblib
import cv2
import numpy as np
from PIL import Image, ImageEnhance
from collections import Counter
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_ROOT = os.path.join(BASE_DIR, 'dataset', 'dataset')
SVM_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'tobacco_svm.pkl')
SVM_METADATA_PATH = os.path.join(BASE_DIR, 'models', 'svm_metadata.json')

LABEL_MAP = {
    "Low Quality": 0,      # filler
    "Medium Quality": 1,   # binder
    "High Quality": 2      # wrapper
}
CLASS_NAMES = ["filler", "binder", "wrapper"]


def extract_feature_vector(img_bgr):
    """
    Mengekstrak vektor fitur numerik (warna & tekstur) dari potongan daun:
    - Dimensi: 36 nilai float (vektor fitur)
    """
    img_resized = cv2.resize(img_bgr, (128, 128))
    
    # 1. Konversi Ruang Warna
    img_hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)
    img_lab = cv2.cvtColor(img_resized, cv2.COLOR_BGR2Lab)
    img_gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
    
    features = []
    
    # 2. Fitur Statistik Warna (BGR, HSV, Lab)
    for space in [img_resized, img_hsv, img_lab]:
        for ch in range(3):
            channel = space[:, :, ch]
            features.append(np.mean(channel))
            features.append(np.std(channel))
            features.append(np.percentile(channel, 25))
            features.append(np.percentile(channel, 75))
            
    # 3. Fitur Tekstur & Urat Daun (Sobel Edge Magnitude)
    sobel_x = cv2.Sobel(img_gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(img_gray, cv2.CV_64F, 0, 1, ksize=3)
    edge_mag = np.sqrt(sobel_x**2 + sobel_y**2)
    
    features.append(np.mean(edge_mag))
    features.append(np.std(edge_mag))
    features.append(np.max(edge_mag))
    
    # Histogram Intensitas Grayscale (4 bin)
    hist = cv2.calcHist([img_gray], [0], None, [4], [0, 256]).flatten()
    hist_norm = hist / (hist.sum() + 1e-6)
    features.extend(hist_norm.tolist())
    
    return np.array(features, dtype=np.float32)


def load_dataset_for_svm():
    print("[1/3] Membaca dataset & mengekstrak vektor fitur daun ...")
    X_features = []
    y_labels = []
    
    splits = ['train', 'valid']
    for split in splits:
        split_dir = os.path.join(DATASET_ROOT, split)
        json_path = os.path.join(split_dir, '_annotations.createml.json')
        if not os.path.exists(json_path):
            continue
            
        with open(json_path, 'r') as f:
            annotations = json.load(f)
            
        print(f"  -> Memproses split '{split}': {len(annotations)} gambar...")
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
            
            img_full = cv2.imread(img_path)
            if img_full is None:
                continue
                
            h_img, w_img, _ = img_full.shape
            
            # Crop ROI
            if 'x' in coord and 'y' in coord and 'width' in coord and 'height' in coord:
                cx, cy = coord['x'], coord['y']
                bw, bh = coord['width'], coord['height']
                x1 = max(0, int(cx - bw / 2.0))
                y1 = max(0, int(cy - bh / 2.0))
                x2 = min(w_img, int(cx + bw / 2.0))
                y2 = min(h_img, int(cy + bh / 2.0))
                if (x2 - x1) > 20 and (y2 - y1) > 20:
                    leaf_crop = img_full[y1:y2, x1:x2]
                else:
                    leaf_crop = img_full
            else:
                leaf_crop = img_full
                
            vec = extract_feature_vector(leaf_crop)
            X_features.append(vec)
            y_labels.append(lbl_id)
            
            # Oversampling kelas Low Quality (Filler) agar seimbang
            if lbl_id == 0:
                for _ in range(8):
                    # Variasi sedikit kontras/brightness
                    mult = random.uniform(0.85, 1.15)
                    aug_crop = np.clip(leaf_crop.astype(np.float32) * mult, 0, 255).astype(np.uint8)
                    aug_vec = extract_feature_vector(aug_crop)
                    X_features.append(aug_vec)
                    y_labels.append(lbl_id)
                    
            elif lbl_id == 2:
                if random.random() > 0.5:
                    mult = random.uniform(0.9, 1.1)
                    aug_crop = np.clip(leaf_crop.astype(np.float32) * mult, 0, 255).astype(np.uint8)
                    X_features.append(extract_feature_vector(aug_crop))
                    y_labels.append(lbl_id)

    counter = Counter(y_labels)
    print("\n  Distribusi Vektor Fitur Dataset:")
    for lbl_id, count in sorted(counter.items()):
        print(f"    - Kelas {lbl_id} ({CLASS_NAMES[lbl_id].upper()}): {count} vektor (panjang vektor: {len(X_features[0])})")
        
    return np.array(X_features, dtype=np.float32), np.array(y_labels, dtype=np.int32)


def train_svm():
    os.makedirs(os.path.join(BASE_DIR, 'models'), exist_ok=True)
    
    print("=" * 65)
    print("  TobaccoGuard AI - Pelatihan Model SVM (Support Vector Machine)")
    print("=" * 65)
    
    X, y = load_dataset_for_svm()
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    
    print(f"\n[2/3] Melatih Classifier SVM (RBF Kernel + StandardScaler) ...")
    
    # Pipeline: StandardScaler -> SVM RBF
    svm_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', SVC(
            kernel='rbf',
            C=5.0,
            gamma='scale',
            probability=True,
            class_weight='balanced',
            random_state=42
        ))
    ])
    
    svm_pipeline.fit(X_train, y_train)
    
    print("\n[3/3] Mengevaluasi Performa Model SVM ...")
    y_pred = svm_pipeline.predict(X_test)
    y_pred_proba = svm_pipeline.predict_proba(X_test)
    acc = accuracy_score(y_test, y_pred)
    
    print(f"  -> Akurasi Pengujian (Accuracy Score) : {acc * 100:.2f}%\n")
    print("  Laporan Klasifikasi per Kelas:")
    print(classification_report(y_test, y_pred, target_names=CLASS_NAMES))
    
    # Simpan model pipeline (Scaler + SVM)
    joblib.dump(svm_pipeline, SVM_MODEL_PATH)
    print(f"[SUKSES] Model SVM berhasil disimpan di: {SVM_MODEL_PATH}")
    
    metadata = {
        "model_type": "Support Vector Machine (SVM)",
        "kernel": "rbf",
        "feature_vector_dimension": int(X.shape[1]),
        "classes": CLASS_NAMES,
        "test_accuracy": round(float(acc), 4),
        "total_samples": len(X)
    }
    with open(SVM_METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)
        
    print(f"[SUKSES] Metadata SVM disimpan di: {SVM_METADATA_PATH}")
    print("=" * 65 + "\n")


if __name__ == '__main__':
    train_svm()
