"""
===================================================================================
TobaccoGuard AI - Inference Script Klasifikasi Mutu Daun Tembakau
===================================================================================

TODO: Script ini akan diisi setelah model hasil training tersedia di ai/models/

Fungsi Inference yang Direncanakan:
1. Load model .h5 atau .tflite dari folder ai/models/
2. Terima input berupa gambar path atau frame dari kamera
3. Preprocessing gambar (resize ke 224x224, normalisasi pixel 0-1)
4. Prediksi kelas daun tembakau: 'wrapper', 'binder', atau 'filler'
5. Kembalikan hasil klasifikasi beserta confidence score (0.0 - 1.0)
6. (Opsional) Kirim hasil ke endpoint POST /api/conveyor secara otomatis

Integrasi dengan Backend Flask:
    POST /api/conveyor
    Content-Type: application/json
    {
        "hasil_klasifikasi": "wrapper",   // salah satu: wrapper, binder, filler
        "confidence_score": 0.9543        // nilai 0.0 - 1.0
    }

Cara Menjalankan (setelah model tersedia):
    cd ai/
    python inference.py --image path/ke/gambar_daun.jpg
    python inference.py --camera 0   # Gunakan webcam / kamera ESP32-CAM stream

===================================================================================
"""

# TODO: Import library
# import os
# import sys
# import argparse
# import numpy as np
# import json
# import urllib.request
# from PIL import Image
# import tensorflow as tf

# TODO: Konfigurasi
# MODEL_PATH = 'models/tobacco_classifier_v1.h5'
# TFLITE_PATH = 'models/tobacco_classifier_v1.tflite'
# IMG_SIZE = (224, 224)
# CLASS_NAMES = ['binder', 'filler', 'wrapper']  # Urutan alfabetis (sesuai Keras ImageDataGenerator)
# API_ENDPOINT = 'http://127.0.0.1:5000/api/conveyor'

# TODO: Load Model
# def load_model(model_path=MODEL_PATH):
#     ...

# TODO: Preprocessing Gambar
# def preprocess_image(image_path):
#     ...

# TODO: Prediksi / Klasifikasi Daun
# def classify_leaf(image_path, model):
#     ...
#     # Return: {"hasil_klasifikasi": "wrapper", "confidence_score": 0.9543}

# TODO: Kirim Hasil ke Backend Flask (POST /api/conveyor)
# def send_to_api(hasil, confidence, endpoint=API_ENDPOINT):
#     ...

# TODO: Main Entry Point
# def main():
#     parser = argparse.ArgumentParser()
#     parser.add_argument('--image', type=str, help='Path ke gambar daun tembakau')
#     args = parser.parse_args()
#     ...

# if __name__ == '__main__':
#     main()

print("=" * 60)
print("  TobaccoGuard AI - Inference Script (Placeholder)")
print("=" * 60)
print("Model belum tersedia.")
print("Jalankan ai/train.py terlebih dahulu setelah dataset tersedia,")
print("lalu uncomment kode inference di atas.")
print()
print("Format output ke /api/conveyor:")
print('  {"hasil_klasifikasi": "wrapper|binder|filler",')
print('   "confidence_score": 0.0000 - 1.0000}')
