"""
===================================================================================
TobaccoGuard AI - Inference Script Klasifikasi Mutu Daun Tembakau
===================================================================================
Penggunaan:
    python ai/inference.py --image path/ke/gambar.jpg
    python ai/inference.py --camera 0
    python ai/inference.py --camera 0 --auto 3    (auto-scan tiap 3 detik)
===================================================================================
"""

import os
import sys
import time
import argparse
import json
import cv2
import numpy as np

# Cek dependensi requests
try:
    import requests
except ImportError:
    requests = None

# Konfigurasi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KERAS_PATH = os.path.join(BASE_DIR, 'models', 'tobacco_model.keras')
DEFAULT_MODEL_PATH = DEFAULT_KERAS_PATH if os.path.exists(DEFAULT_KERAS_PATH) else os.path.join(BASE_DIR, 'models', 'tobacco_model.h5')
DEFAULT_API_URL = 'http://127.0.0.1:5000/api/conveyor'
IMG_SIZE = (224, 224)

# Pemetaan Kelas (Index 0: Filler, 1: Binder, 2: Wrapper)
CLASS_NAMES = ['filler', 'binder', 'wrapper']

LABEL_DISPLAY = {
    'wrapper': 'WRAPPER (High Quality)',
    'binder':  'BINDER (Medium Quality)',
    'filler':  'FILLER (Low Quality)',
    'unknown': 'UNKNOWN (Tidak dikenal)'
}

CLASS_COLORS = {
    'wrapper': (46, 204, 113),
    'binder':  (0, 215, 255),
    'filler':  (60, 76, 231),
    'unknown': (128, 128, 128),
    'neutral': (200, 200, 200)
}


# =============================================================================
# MUAT MODEL
# =============================================================================
_model_cache = None

def load_model(model_path=DEFAULT_MODEL_PATH):
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    if not os.path.exists(model_path):
        print(f"[ERROR] Model tidak ditemukan: {model_path}")
        return None

    import tensorflow as tf
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
    print(f"[INFO] Memuat model dari: {model_path} ...")
    keras_model = tf.keras.models.load_model(model_path)
    print("[OK] Model berhasil dimuat.")

    # Warm-up
    dummy = np.zeros((1, 224, 224, 3), dtype=np.float32)
    try:
        _ = keras_model(dummy, training=False).numpy()
    except Exception:
        _ = keras_model.predict(dummy, verbose=0)

    _model_cache = keras_model
    return keras_model


# =============================================================================
# PREDIKSI
# =============================================================================
def classify(model, img_bgr):
    """Prediksi kelas mutu dari gambar BGR. Return: (kelas, confidence, probabilitas)"""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_resized = cv2.resize(img_rgb, IMG_SIZE, interpolation=cv2.INTER_AREA)
    img_norm = img_resized.astype(np.float32) / 255.0
    img_batch = np.expand_dims(img_norm, axis=0)

    preds = model.predict(img_batch, verbose=0)[0]
    pred_idx = int(np.argmax(preds))
    confidence = float(preds[pred_idx])
    predicted_class = CLASS_NAMES[pred_idx]

    return predicted_class, confidence, preds


# =============================================================================
# KIRIM KE SERVER
# =============================================================================
def send_to_server(api_url, hasil, confidence, img_bgr=None):
    if not requests or not api_url:
        return False, "API tidak aktif"

    try:
        payload = {'hasil_klasifikasi': hasil, 'confidence_score': str(round(confidence, 4))}
        files = None
        if img_bgr is not None:
            ok, enc = cv2.imencode('.jpg', img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if ok:
                files = {'gambar': ('leaf.jpg', enc.tobytes(), 'image/jpeg')}

        if files:
            res = requests.post(api_url, data=payload, files=files, timeout=4.0)
        else:
            res = requests.post(api_url, json={'hasil_klasifikasi': hasil, 'confidence_score': round(confidence, 4)}, timeout=4.0)

        return res.status_code in [200, 201], f"HTTP {res.status_code}"
    except Exception as e:
        return False, f"Gagal ({type(e).__name__})"


# =============================================================================
# MODE GAMBAR TUNGGAL
# =============================================================================
def run_image(image_path, model_path, api_url):
    if not os.path.exists(image_path):
        print(f"[ERROR] Gambar tidak ditemukan: {image_path}")
        return

    model = load_model(model_path)
    img = cv2.imread(image_path)
    if img is None:
        print(f"[ERROR] Gambar rusak: {image_path}")
        return

    cls, conf, preds = classify(model, img)
    print("=" * 50)
    print(f"  Hasil  : {LABEL_DISPLAY.get(cls, cls)}")
    print(f"  Confidence : {conf*100:.2f}%")
    print(f"  Distribusi : Filler={preds[0]*100:.1f}% | Binder={preds[1]*100:.1f}% | Wrapper={preds[2]*100:.1f}%")
    print("=" * 50)

    if api_url:
        ok, msg = send_to_server(api_url, cls, conf, img)
        print(f"[SERVER] {msg}")


# =============================================================================
# MODE WEBCAM / KAMERA
# =============================================================================
def run_camera(camera_index, model_path, api_url, auto_interval):
    model = load_model(model_path)
    if model is None:
        return

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[ERROR] Tidak dapat membuka webcam index {camera_index}")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    auto_scan = (auto_interval > 0)
    last_scan = time.time()
    last_result = None

    print("\n  Kamera aktif! [SPASI] Scan | [A] Toggle Auto | [Q] Keluar\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        box_size = min(300, int(min(h, w) * 0.65))
        x1, y1 = (w - box_size) // 2, (h - box_size) // 2
        x2, y2 = x1 + box_size, y1 + box_size

        # Gambar kotak panduan
        color = CLASS_COLORS.get(last_result['class'], CLASS_COLORS['neutral']) if last_result and (time.time() - last_result['t'] < 4) else CLASS_COLORS['neutral']
        for corner in [(x1, y1, x1+35, y1, x1, y1+35), (x2, y1, x2-35, y1, x2, y1+35),
                       (x1, y2, x1+35, y2, x1, y2-35), (x2, y2, x2-35, y2, x2, y2-35)]:
            cv2.line(frame, (corner[0], corner[1]), (corner[2], corner[3]), color, 3)
            cv2.line(frame, (corner[0], corner[1]), (corner[4], corner[5]), color, 3)

        # Banner hasil
        if last_result and (time.time() - last_result['t'] < 4):
            cv2.putText(frame, f"MUTU: {LABEL_DISPLAY.get(last_result['class'], '').upper()} ({last_result['conf']*100:.1f}%)",
                        (x1 - 10, y2 + 30), cv2.FONT_HERSHEY_DUPLEX, 0.6, color, 2)

        cv2.imshow("TobaccoGuard AI", frame)

        # Cek scan
        should_scan = False
        now = time.time()
        if auto_scan and (now - last_scan >= auto_interval):
            should_scan = True
            last_scan = now

        key = cv2.waitKey(1) & 0xFF
        if key in [ord('q'), 27]:
            break
        elif key == ord(' '):
            should_scan = True
        elif key == ord('a'):
            auto_scan = not auto_scan
            print(f"[MODE] Auto: {'ON' if auto_scan else 'OFF'}")

        if should_scan:
            crop = frame[y1:y2, x1:x2].copy()
            if crop.size > 0:
                cls, conf, _ = classify(model, crop)
                print(f"[SCAN] {LABEL_DISPLAY.get(cls)} | {conf*100:.1f}%")
                if api_url:
                    send_to_server(api_url, cls, conf, crop)
                last_result = {'class': cls, 'conf': conf, 't': time.time()}

    cap.release()
    cv2.destroyAllWindows()


# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="TobaccoGuard AI Classifier")
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--image', type=str, default=None)
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL_PATH)
    parser.add_argument('--api', type=str, default=DEFAULT_API_URL)
    parser.add_argument('--auto', type=int, default=0)
    parser.add_argument('--no-send', action='store_true')
    args = parser.parse_args()

    api = None if args.no_send else args.api

    if args.image:
        run_image(args.image, args.model, api)
    else:
        run_camera(args.camera, args.model, api, args.auto)
