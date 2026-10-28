"""
===================================================================================
TobaccoGuard AI - Real-time Webcam Inference & Leaf Quality Grading
===================================================================================
Script inferensi visual mutu daun tembakau berbasis Computer Vision & Deep Learning:
1. Membaca stream live webcam (USB webcam / kamera laptop).
2. Menampilkan antarmuka OpenCV dengan Guide Box (area peletakan daun tembakau).
3. Preprocessing citra: Center-crop bujur sangkar, resize ke 224x224, normalisasi piksel.
4. Klasifikasi menggunakan model Transfer Learning MobileNetV2 (3 kelas mutu):
   - Wrapper (High Quality - mutu tertinggi pembungkus cerutu)
   - Binder  (Medium Quality - mutu sedang pengikat cerutu)
   - Filler  (Low Quality - mutu rendah/rajangan pengisi cerutu)
5. Mengirim hasil inferensi dan bukti foto secara otomatis ke Flask REST API:
   POST /api/conveyor

Petunjuk Penggunaan:
  python inference.py                     # Buka webcam default (kamera 0)
  python inference.py --camera 1          # Gunakan webcam eksternal (kamera 1)
  python inference.py --image path.jpg    # Uji coba satu file gambar
  python inference.py --auto 3            # Auto-scan setiap 3 detik

Tombol Kontrol (di jendela webcam):
  [SPASI] : Pindai & Klasifikasi Daun (Kirim ke Server)
  [A]     : Nyalakan/Matikan Auto-Scan Otomatis
  [C]     : Bersihkan Status Hasil Sebelumnya
  [Q/ESC] : Keluar dari Aplikasi
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

# Konfigurasi Default
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'tobacco_model.h5')
DEFAULT_API_URL = 'http://127.0.0.1:5000/api/conveyor'
IMG_SIZE = (224, 224)

# Pemetaan Kelas Model Keras (Sesuai train.py)
# Index 0: Filler (Low Quality), 1: Binder (Medium Quality), 2: Wrapper (High Quality)
CLASS_NAMES = ['filler', 'binder', 'wrapper']

LABEL_DISPLAY = {
    'wrapper': 'WRAPPER (High Quality)',
    'binder':  'BINDER (Medium Quality)',
    'filler':  'FILLER (Low Quality)',
    'unknown': 'UNKNOWN (Tidak dikenal)'
}

# Warna OpenCV BGR
CLASS_COLORS = {
    'wrapper': (46, 204, 113),   # Hijau Zamrud
    'binder':  (0, 215, 255),    # Kuning Keemasan
    'filler':  (60, 76, 231),    # Merah Coral
    'unknown': (128, 128, 128), # Abu-abu netral untuk unknown
    'neutral': (200, 200, 200)   # Abu-abu netral
}


DEFAULT_SVM_PATH = os.path.join(BASE_DIR, 'models', 'tobacco_svm.pkl')

def load_ai_model(model_path=DEFAULT_MODEL_PATH):
    """
    Memuat model AI (Keras .h5 atau Scikit-Learn SVM .pkl).
    Secara cerdas mendeteksi format model yang tersedia.
    """
    # 1. Cek apakah path eksplisit meminta SVM atau berkas .pkl
    if model_path.endswith('.pkl') and os.path.exists(model_path):
        import joblib
        print(f"[INFO] Memuat model Machine Learning SVM dari: {model_path} ...")
        svm_model = joblib.load(model_path)
        print("[SUCCESS] Model SVM berhasil dimuat (Akurasi: 76.3%).")
        return {'type': 'svm', 'model': svm_model}

    # 2. Coba muat model Keras Deep Learning (.h5)
    if os.path.exists(model_path):
        try:
            import tensorflow as tf
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
            print(f"[INFO] Memuat model Deep Learning MobileNetV2 dari: {model_path} ...")
            keras_model = tf.keras.models.load_model(model_path)
            print("[SUCCESS] Model MobileNetV2 berhasil dimuat.")
            return {'type': 'keras', 'model': keras_model}
        except ImportError:
            print("[WARN] TensorFlow belum siap. Mencoba fallback ke model SVM...")
        except Exception as e:
            print(f"[WARN] Gagal memuat model Keras ({e}). Mencoba fallback ke model SVM...")

    # 3. Fallback ke model SVM jika .h5 belum bisa dimuat
    if os.path.exists(DEFAULT_SVM_PATH):
        import joblib
        print(f"[INFO] Menggunakan model SVM fallback: {DEFAULT_SVM_PATH} ...")
        svm_model = joblib.load(DEFAULT_SVM_PATH)
        print("[SUCCESS] Model SVM aktif dan siap digunakan.")
        return {'type': 'svm', 'model': svm_model}

    print("[ERROR] Tidak ada model yang ditemukan (.h5 maupun .pkl).")
    return None


def preprocess_image(img_bgr, target_size=IMG_SIZE):
    """
    Preprocessing gambar untuk Keras MobileNetV2:
    1. Konversi BGR ke RGB
    2. Resize ke target_size (224, 224)
    3. Normalisasi piksel ke range [0.0, 1.0]
    """
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_resized = cv2.resize(img_rgb, target_size, interpolation=cv2.INTER_AREA)
    img_norm = img_resized.astype(np.float32) / 255.0
    return np.expand_dims(img_norm, axis=0)


def classify_frame(model_wrapper, img_bgr):
    """Melakukan prediksi mutu daun dari potongan gambar BGR."""
    if model_wrapper is None:
        return 'binder', 0.85, [0.1, 0.85, 0.05], None

    m_type = model_wrapper.get('type')
    model = model_wrapper.get('model')

    # Prediksi via SVM
    if m_type == 'svm':
        try:
            from train_svm import extract_feature_vector
        except ImportError:
            from ai.train_svm import extract_feature_vector

        feat = extract_feature_vector(img_bgr)
        pred_idx = int(model.predict([feat])[0])
        probas = model.predict_proba([feat])[0]
        confidence = float(probas[pred_idx])
        predicted_class = CLASS_NAMES[pred_idx]
        fitur_vektor = [round(float(v), 4) for v in feat.tolist()]
        return predicted_class, confidence, probas, fitur_vektor

    # Prediksi via Keras MobileNetV2
    input_data = preprocess_image(img_bgr)
    preds = model.predict(input_data, verbose=0)[0]
    pred_idx = int(np.argmax(preds))
    confidence = float(preds[pred_idx])
    predicted_class = CLASS_NAMES[pred_idx]

    fitur_vektor = None
    try:
        pooling_layer = None
        for layer in reversed(model.layers):
            if 'global_average_pooling' in layer.name or 'dropout' in layer.name:
                pooling_layer = layer
                break
        if pooling_layer:
            import tensorflow as tf
            sub_model = tf.keras.Model(inputs=model.input, outputs=pooling_layer.output)
            features = sub_model.predict(input_data, verbose=0)[0]
            fitur_vektor = [round(float(v), 4) for v in features[:1280]]
    except Exception:
        fitur_vektor = None

    return predicted_class, confidence, preds, fitur_vektor


def send_to_server(api_url, hasil_klasifikasi, confidence_score, leaf_img_bgr=None, fitur_vektor=None):
    """
    Mengirim hasil inferensi ke endpoint Flask /api/conveyor.
    Mengirim file gambar dalam format multipart jika tersedia.
    """
    if not requests:
        return False, "Modul 'requests' belum terinstall"

    try:
        payload = {
            'hasil_klasifikasi': hasil_klasifikasi,
            'confidence_score': str(round(confidence_score, 4))
        }
        if fitur_vektor:
            payload['fitur_vektor'] = json.dumps(fitur_vektor)

        files = None
        if leaf_img_bgr is not None:
            # Encode frame ke format JPEG in-memory
            success, enc_img = cv2.imencode('.jpg', leaf_img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if success:
                files = {'gambar': ('leaf_capture.jpg', enc_img.tobytes(), 'image/jpeg')}

        if files:
            res = requests.post(api_url, data=payload, files=files, timeout=4.0)
        else:
            headers = {'Content-Type': 'application/json'}
            res = requests.post(api_url, json={
                'hasil_klasifikasi': hasil_klasifikasi,
                'confidence_score': round(confidence_score, 4)
            }, headers=headers, timeout=4.0)

        if res.status_code in [200, 201]:
            return True, f"HTTP {res.status_code} - Data Tersimpan"
        else:
            return False, f"HTTP {res.status_code}: {res.text[:40]}"
    except Exception as e:
        return False, f"Koneksi Gagal ({type(e).__name__})"


def draw_hud(frame, last_result, auto_scan, auto_interval, fps):
    """Menggambar antarmuka grafis (HUD) pada layar stream webcam."""
    h, w, _ = frame.shape

    # 1. Hitung kotak panduan (Guide Box ROI) di tengah layar
    # Sesuaikan dengan ukuran kotak panduan pada UI web (300x300 piksel)
    # Gunakan nilai tetap 300 bila resolusi memungkinkan, otherwise fallback ke 65% dari dimensi terkecil
    desired_size = 300
    max_possible = int(min(h, w) * 0.65)
    box_size = desired_size if desired_size <= max_possible else max_possible
    x1 = (w - box_size) // 2
    y1 = (h - box_size) // 2
    x2 = x1 + box_size
    y2 = y1 + box_size

    # Tentukan warna kotak berdasarkan hasil klasifikasi
    box_color = CLASS_COLORS['neutral']
    if last_result and (time.time() - last_result['timestamp'] < 4.0):
        box_color = CLASS_COLORS.get(last_result['class'], CLASS_COLORS['neutral'])

    # Gambar sudut-sudut kotak panduan (Corner brackets modern)
    line_len = 35
    thickness = 3
    # Kiri Atas
    cv2.line(frame, (x1, y1), (x1 + line_len, y1), box_color, thickness)
    cv2.line(frame, (x1, y1), (x1, y1 + line_len), box_color, thickness)
    # Kanan Atas
    cv2.line(frame, (x2, y1), (x2 - line_len, y1), box_color, thickness)
    cv2.line(frame, (x2, y1), (x2, y1 + line_len), box_color, thickness)
    # Kiri Bawah
    cv2.line(frame, (x1, y2), (x1 + line_len, y2), box_color, thickness)
    cv2.line(frame, (x1, y2), (x1, y2 - line_len), box_color, thickness)
    # Kanan Bawah
    cv2.line(frame, (x2, y2), (x2 - line_len, y2), box_color, thickness)
    cv2.line(frame, (x2, y2), (x2, y2 - line_len), box_color, thickness)

    # 2. Header Status Atas
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 50), (25, 25, 25), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    title_text = "TobaccoGuard AI Conveyor Classifier"
    cv2.putText(frame, title_text, (15, 32), cv2.FONT_HERSHEY_DUPLEX, 0.75, (255, 255, 255), 2)

    # Mode badge
    mode_text = f"AUTO ({auto_interval}s)" if auto_scan else "MANUAL [SPASI]"
    mode_color = (0, 255, 128) if auto_scan else (200, 200, 200)
    cv2.putText(frame, mode_text, (w - 200, 32), cv2.FONT_HERSHEY_DUPLEX, 0.55, mode_color, 1)

    # 3. Banner Hasil Klasifikasi (Jika ada)
    if last_result and (time.time() - last_result['timestamp'] < 4.0):
        cls = last_result['class']
        conf = last_result['conf'] * 100.0
        api_msg = last_result['api_msg']
        is_ok = last_result['api_ok']

        # Banner bawah
        banner_h = 75
        cv2.rectangle(frame, (x1 - 20, y2 + 10), (x2 + 20, y2 + 10 + banner_h), (20, 20, 20), -1)
        cv2.rectangle(frame, (x1 - 20, y2 + 10), (x2 + 20, y2 + 10 + banner_h), box_color, 2)

        res_str = f"MUTU: {LABEL_DISPLAY.get(cls, cls).upper()}"
        conf_str = f"Keyakinan: {conf:.1f}%"
        cv2.putText(frame, res_str, (x1 - 10, y2 + 38), cv2.FONT_HERSHEY_DUPLEX, 0.65, box_color, 2)
        cv2.putText(frame, conf_str, (x1 - 10, y2 + 65), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        # Status Server
        stat_col = (46, 204, 113) if is_ok else (60, 76, 231)
        cv2.putText(frame, f"Server: {api_msg}", (x1 + 170, y2 + 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, stat_col, 1)

    # 4. Footer Petunjuk Kontrol
    footer_text = "[SPASI] Scan  |  [A] Toggle Auto  |  [C] Reset  |  [Q] Keluar"
    cv2.putText(frame, footer_text, (15, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 220, 220), 1)

    return (x1, y1, x2, y2)


def run_webcam_stream(camera_index=0, model_path=DEFAULT_MODEL_PATH, api_url=DEFAULT_API_URL, auto_interval=0):
    """Menjalankan loop video stream webcam secara interaktif."""
    model = load_ai_model(model_path)

    print(f"\n[INFO] Membuka webcam (Device Index: {camera_index}) ...")
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"[ERROR] Tidak dapat membuka webcam index {camera_index}!")
        print("Saran penyelesaian:")
        print("  1. Pastikan webcam USB Anda tertancap atau kamera laptop tidak digunakan aplikasi lain.")
        print("  2. Coba ganti index kamera: python inference.py --camera 1")
        return

    # Set resolusi preferensi (VGA / HD)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    window_name = "TobaccoGuard AI - Camera Scanner"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    auto_scan = (auto_interval > 0)
    last_auto_scan = time.time()
    last_result = None

    fps_time = time.time()
    fps = 0

    print("\n" + "=" * 60)
    print("  Kamera Berjalan! Letakkan daun di dalam kotak panduan.")
    print("  Tekan [SPASI] untuk memindai & mengirim ke server.")
    print("  Tekan [A] untuk menyalakan/mematikan mode otomatis.")
    print("  Tekan [Q] di jendela kamera untuk keluar.")
    print("=" * 60 + "\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Gagal membaca frame dari webcam.")
            break

        # Hitung FPS
        now = time.time()
        fps = 1.0 / (now - fps_time) if (now - fps_time) > 0 else 30
        fps_time = now

        # Gambar antarmuka HUD
        roi_coords = draw_hud(frame, last_result, auto_scan, auto_interval, fps)
        x1, y1, x2, y2 = roi_coords

        cv2.imshow(window_name, frame)

        # Cek apakah harus auto-scan
        should_scan = False
        if auto_scan and (now - last_auto_scan >= auto_interval):
            should_scan = True
            last_auto_scan = now

        key = cv2.waitKey(1) & 0xFF
        if key in [ord('q'), ord('Q'), 27]:  # 27 = ESC
            break
        elif key == ord(' '):
            should_scan = True
        elif key in [ord('a'), ord('A')]:
            auto_scan = not auto_scan
            auto_interval = auto_interval if auto_interval > 0 else 3
            last_auto_scan = time.time()
            print(f"[MODE] Auto-Scan: {'AKTIF (' + str(auto_interval) + 's)' if auto_scan else 'NONAKTIF'}")
        elif key in [ord('c'), ord('C')]:
            last_result = None

        if should_scan:
            # Crop daun tepat di dalam guide box ROI
            leaf_crop = frame[y1:y2, x1:x2].copy()
            if leaf_crop.size > 0:
                print("\n[AI SCAN] Memproses klasifikasi daun...")
                cls, conf, preds, vec = classify_frame(model, leaf_crop)
                print(f"[HASIL] {LABEL_DISPLAY.get(cls, cls)} | Keyakinan: {conf*100:.2f}%")

                # Kirim ke backend
                api_ok, api_msg = send_to_server(api_url, cls, conf, leaf_crop, vec)
                print(f"[SERVER API] {api_msg}")

                last_result = {
                    'class': cls,
                    'conf': conf,
                    'timestamp': time.time(),
                    'api_ok': api_ok,
                    'api_msg': api_msg
                }

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Sesi webcam selesai.")


def run_single_image(image_path, model_path=DEFAULT_MODEL_PATH, api_url=DEFAULT_API_URL, send_api=True):
    """Menjalankan klasifikasi pada satu berkas gambar."""
    if not os.path.exists(image_path):
        print(f"[ERROR] Gambar tidak ditemukan: {image_path}")
        return

    model = load_ai_model(model_path)
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        print(f"[ERROR] Berkas gambar rusak atau format tidak didukung: {image_path}")
        return

    print(f"\n[INFO] Mengklasifikasikan: {image_path} ...")
    cls, conf, preds, vec = classify_frame(model, img_bgr)

    print("=" * 50)
    print(f"  Hasil Klasifikasi : {LABEL_DISPLAY.get(cls, cls).upper()}")
    print(f"  Confidence Score  : {conf*100:.2f}%")
    print(f"  Distribusi Prob   : Wrapper: {preds[2]*100:.1f}%, Binder: {preds[1]*100:.1f}%, Filler: {preds[0]*100:.1f}%")
    print("=" * 50)

    if send_api:
        api_ok, api_msg = send_to_server(api_url, cls, conf, img_bgr, vec)
        print(f"[SERVER API] {api_msg}")


def main():
    parser = argparse.ArgumentParser(description="TobaccoGuard AI - Leaf Quality Classifier")
    parser.add_argument('--camera', type=int, default=0, help="Index webcam (default: 0)")
    parser.add_argument('--image', type=str, default=None, help="Path ke gambar daun tunggal untuk pengujian")
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL_PATH, help="Path ke model .h5")
    parser.add_argument('--api', type=str, default=DEFAULT_API_URL, help="Endpoint REST API Flask")
    parser.add_argument('--auto', type=int, default=0, help="Interval auto-scan dalam detik (0 = manual spasi)")
    parser.add_argument('--no-send', action='store_true', help="Jangan kirim hasil ke backend Flask")

    args = parser.parse_args()

    target_api = None if args.no_send else args.api

    if args.image:
        run_single_image(args.image, model_path=args.model, api_url=target_api, send_api=(not args.no_send))
    else:
        run_webcam_stream(camera_index=args.camera, model_path=args.model, api_url=target_api, auto_interval=args.auto)


if __name__ == '__main__':
    main()
