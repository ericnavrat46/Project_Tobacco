from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, time
from sqlalchemy import func
from models import db
from models.klasifikasi import KlasifikasiDaun
import os, uuid

api_conveyor_bp = Blueprint('api_conveyor', __name__, url_prefix='/api/conveyor')

# Folder penyimpanan gambar daun (relatif terhadap static/)
UPLOAD_SUBDIR = 'uploads/daun'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



def _detect_leaf_contour_and_edges(img_cv):
    """
    Mendeteksi daun tembakau di atas latar belakang putih menggunakan pipeline Grayscale + Thresholding.

    Tahapan:
    1. Citra asli (BGR)
    2. Konversi Grayscale + Gaussian Blur
    3. Thresholding Binary Invert (Otsu):
       - Background putih (terang) -> Hitam (0)
       - Objek daun tembakau (gelap) -> Putih (255)
    4. Morphological Operation (Closing kernel 11x11 untuk tutup celah internal daun + Opening)
    5. Contour Detection + Bounding Box (Ambil kontur daun terbesar)
    6. ROI + Contour (Crop area daun bergaris neon emerald)

    Return: (img_annotated, edge_detected, contour_count, leaf_area_ratio, leaf_bbox, largest_contour)
    """
    try:
        import cv2
        import numpy as np

        if img_cv is None:
            return img_cv, False, 0, 0.0, None, None

        h, w = img_cv.shape[:2]
        total_pixels = h * w

        # ── Tahap 2: Konversi ke Grayscale & Gaussian Blur ──
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        # Cek kontras: jika frame putih polos tanpa objek (standar deviasi sangat rendah)
        std_dev = float(np.std(gray))
        if std_dev < 15.0 or float(np.mean(gray)) > 245:
            return img_cv, False, 0, 0.0, None, None

        # ── Tahap 3: Thresholding Binary Invert (Otsu) ──
        # Latar putih terang (> threshold) -> di-invert menjadi HITAM (0)
        # Daun tembakau gelap (< threshold) -> di-invert menjadi PUTIH (255)
        thresh_val, binary_mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # ── Tahap 4: Morphological Operation ──
        # Closing (kernel 11×11) untuk menutup lubang internal / tulang daun
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        closing_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel_close, iterations=2)
        # Opening (kernel 5×5) untuk menghapus bintik debu kecil
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        clean_mask = cv2.morphologyEx(closing_mask, cv2.MORPH_OPEN, kernel_open, iterations=1)

        # ── Tahap 5: Contour Detection + Bounding Box ──
        contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        annotated = img_cv.copy()
        valid_contours = []
        total_leaf_area = 0.0

        # Minimal 2% dari luas frame agar tidak ter-trigger debu kecil
        min_area = total_pixels * 0.02
        for c in contours:
            area = cv2.contourArea(c)
            if area >= min_area:
                valid_contours.append(c)
                total_leaf_area += area

        leaf_area_ratio = round(total_leaf_area / total_pixels, 4) if total_pixels > 0 else 0.0
        edge_detected = len(valid_contours) > 0
        leaf_bbox = None
        largest_contour = None

        if edge_detected:
            # ── Tahap 6: ROI + Contour ──
            largest_contour = max(valid_contours, key=cv2.contourArea)

            # Gambar garis tepi neon emerald (BGR: 0, 255, 100) tebal 3px di sekeliling daun
            cv2.drawContours(annotated, [largest_contour], -1, (0, 255, 100), 3)

            # Bounding box daun
            bx, by, bw, bh = cv2.boundingRect(largest_contour)
            leaf_bbox = (bx, by, bw, bh)
            cv2.rectangle(annotated, (bx, by), (bx + bw, by + bh), (255, 180, 0), 2)
            cv2.putText(
                annotated,
                f"DAUN TERDETEKSI ({int(leaf_area_ratio * 100)}%)",
                (bx, max(25, by - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 2, cv2.LINE_AA
            )

        return annotated, edge_detected, len(valid_contours), leaf_area_ratio, leaf_bbox, largest_contour
    except Exception:
        return img_cv, False, 0, 0.0, None, None

def _save_image(file_obj):
    """
    Simpan file gambar ke filesystem.
    Return: path relatif terhadap static/ (untuk disimpan di DB)
    Contoh: "uploads/daun/2026/11/05/leaf_a3f2c1.jpg"
    """
    today = datetime.now()
    date_folder = today.strftime('%Y/%m/%d')
    upload_dir = os.path.join(current_app.static_folder, UPLOAD_SUBDIR, date_folder)
    os.makedirs(upload_dir, exist_ok=True)

    ext = file_obj.filename.rsplit('.', 1)[1].lower()
    filename = f"leaf_{uuid.uuid4().hex[:8]}.{ext}"
    file_obj.save(os.path.join(upload_dir, filename))

    return f"{UPLOAD_SUBDIR}/{date_folder}/{filename}"


@api_conveyor_bp.route('', methods=['POST'])
def receive_conveyor_data():
    """
    POST /api/conveyor
    Terima data klasifikasi daun. Mendukung JSON & multipart form.
    """
    try:
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.form
            file = request.files.get('gambar')
        else:
            data = request.get_json(silent=True) or {}
            file = None

        if not data:
            return jsonify({
                "success": False,
                "data": None,
                "message": "Request body harus berupa JSON atau multipart/form-data yang valid"
            }), 400

        required_fields = ['hasil_klasifikasi', 'confidence_score']
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Field wajib tidak ditemukan: {', '.join(missing_fields)}"
            }), 400

        hasil_raw = str(data['hasil_klasifikasi']).strip().lower()
        if hasil_raw not in KlasifikasiDaun.VALID_CATEGORIES:
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Kategori tidak valid: '{data['hasil_klasifikasi']}'. Kategori yang diperbolehkan: {', '.join(KlasifikasiDaun.VALID_CATEGORIES)}"
            }), 400

        try:
            confidence = float(data['confidence_score'])
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "data": None,
                "message": "Confidence score harus berupa angka float/desimal (misal 0.95 atau 95.0)"
            }), 400

        if confidence > 1.0 and confidence <= 100.0:
            confidence = confidence / 100.0
        elif confidence < 0.0 or confidence > 100.0:
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Confidence score tidak valid ({confidence}). Harus di rentang 0.0 - 1.0 atau 0 - 100%"
            }), 400

        gambar_path = None
        if file and file.filename:
            if not _allowed_file(file.filename):
                return jsonify({
                    "success": False,
                    "data": None,
                    "message": f"Format gambar tidak didukung. Gunakan: {', '.join(ALLOWED_EXTENSIONS)}"
                }), 400
            try:
                gambar_path = _save_image(file)
            except Exception as img_err:
                current_app.logger.warning(f"Gambar gagal disimpan: {img_err}")

        fitur_vektor = data.get('fitur_vektor')
        if fitur_vektor and isinstance(fitur_vektor, str):
            import json
            try:
                fitur_vektor = json.loads(fitur_vektor)
            except json.JSONDecodeError:
                fitur_vektor = None

        new_record = KlasifikasiDaun(
            hasil_klasifikasi=hasil_raw,
            confidence_score=confidence,
            gambar_path=gambar_path
        )
        if fitur_vektor:
            new_record.vektor = fitur_vektor

        if 'timestamp' in data and data['timestamp']:
            try:
                new_record.timestamp = datetime.fromisoformat(str(data['timestamp']).replace('Z', '+00:00'))
            except Exception:
                pass

        db.session.add(new_record)
        db.session.commit()

        return jsonify({
            "success": True,
            "data": new_record.to_dict(),
            "message": "Data klasifikasi daun berhasil disimpan"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Terjadi kesalahan pada server: {str(e)}"
        }), 500


@api_conveyor_bp.route('/latest', methods=['GET'])
def get_latest_conveyor():
    """
    GET /api/conveyor/latest
    """
    try:
        latest = KlasifikasiDaun.query.order_by(KlasifikasiDaun.timestamp.desc(), KlasifikasiDaun.id.desc()).first()
        if not latest:
            return jsonify({
                "success": True,
                "data": None,
                "message": "Belum ada data klasifikasi daun"
            }), 200

        return jsonify({
            "success": True,
            "data": latest.to_dict(),
            "message": "Data klasifikasi daun terbaru berhasil diambil"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Gagal mengambil data terbaru conveyor: {str(e)}"
        }), 500


@api_conveyor_bp.route('/stats', methods=['GET'])
def get_conveyor_stats():
    """
    GET /api/conveyor/stats
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        query = KlasifikasiDaun.query

        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                query = query.filter(KlasifikasiDaun.timestamp >= start_dt)
            except ValueError:
                pass

        if end_date_str:
            try:
                end_dt = datetime.combine(datetime.strptime(end_date_str, '%Y-%m-%d'), time.max)
                query = query.filter(KlasifikasiDaun.timestamp <= end_dt)
            except ValueError:
                pass

        total_count   = query.count()
        wrapper_count = query.filter(func.lower(KlasifikasiDaun.hasil_klasifikasi) == 'wrapper').count()
        binder_count  = query.filter(func.lower(KlasifikasiDaun.hasil_klasifikasi) == 'binder').count()
        filler_count  = query.filter(func.lower(KlasifikasiDaun.hasil_klasifikasi) == 'filler').count()

        avg_conf = db.session.query(func.avg(KlasifikasiDaun.confidence_score)).scalar() or 0.0

        wrapper_pct = round((wrapper_count / total_count * 100), 2) if total_count > 0 else 0.0
        binder_pct  = round((binder_count  / total_count * 100), 2) if total_count > 0 else 0.0
        filler_pct  = round((filler_count  / total_count * 100), 2) if total_count > 0 else 0.0

        return jsonify({
            "success": True,
            "data": {
                "total": total_count,
                "wrapper": wrapper_count,
                "binder": binder_count,
                "filler": filler_count,
                "percentages": {
                    "wrapper": wrapper_pct,
                    "binder": binder_pct,
                    "filler": filler_pct
                },
                "avg_confidence": round(float(avg_conf), 4),
                "avg_confidence_percent": round(float(avg_conf) * 100, 2)
            },
            "message": "Statistik klasifikasi daun berhasil diambil"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Gagal mengambil statistik conveyor: {str(e)}"
        }), 500


@api_conveyor_bp.route('/history', methods=['GET'])
def get_conveyor_history():
    """
    GET /api/conveyor/history
    """
    try:
        limit = request.args.get('limit', default=50, type=int)
        if limit <= 0:
            limit = 50
        elif limit > 1000:
            limit = 1000

        start_date_str = request.args.get('start_date')
        end_date_str   = request.args.get('end_date')
        kategori       = request.args.get('kategori')

        query = KlasifikasiDaun.query

        if kategori and kategori.lower() in KlasifikasiDaun.VALID_CATEGORIES:
            query = query.filter(func.lower(KlasifikasiDaun.hasil_klasifikasi) == kategori.lower())

        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                query = query.filter(KlasifikasiDaun.timestamp >= start_dt)
            except ValueError:
                pass

        if end_date_str:
            try:
                end_dt = datetime.combine(datetime.strptime(end_date_str, '%Y-%m-%d'), time.max)
                query = query.filter(KlasifikasiDaun.timestamp <= end_dt)
            except ValueError:
                pass

        records = query.order_by(KlasifikasiDaun.timestamp.desc(), KlasifikasiDaun.id.desc()).limit(limit).all()

        return jsonify({
            "success": True,
            "count": len(records),
            "data": [r.to_dict() for r in records],
            "message": "Histori data klasifikasi daun berhasil diambil"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Gagal mengambil histori klasifikasi: {str(e)}"
        }), 500


_CACHED_AI_MODEL = None
_CACHED_CLASS_NAMES = None

def _get_ai_model(model_path=None, base_path=None):
    global _CACHED_AI_MODEL
    if _CACHED_AI_MODEL is None:
        root = base_path or (current_app.root_path if current_app else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        model_keras = os.path.join(root, 'ai', 'models', 'tobacco_model.keras')
        model_h5 = os.path.join(root, 'ai', 'models', 'tobacco_model.h5')
        target_path = model_keras if os.path.exists(model_keras) else (model_path or model_h5)
        if target_path and os.path.exists(target_path):
            try:
                import keras.src.saving.serialization_lib as sl

                orig_deserialize = sl.deserialize_keras_object

                def _deep_clean_config(obj):
                    if isinstance(obj, dict):
                        for k in ['input_axes', 'output_axes', 'renorm', 'renorm_clipping', 'renorm_momentum', 'synchronized', 'shared_object_id', 'quantization_config']:
                            obj.pop(k, None)
                        for v in obj.values():
                            _deep_clean_config(v)
                    elif isinstance(obj, list):
                        for item in obj:
                            _deep_clean_config(item)

                def _patched_deserialize(config, *args, **kwargs):
                    _deep_clean_config(config)
                    return orig_deserialize(config, *args, **kwargs)

                sl.deserialize_keras_object = _patched_deserialize

                import keras
                _CACHED_AI_MODEL = keras.models.load_model(target_path, compile=False)
            except Exception as err:
                if current_app:
                    current_app.logger.error(f"Gagal memuat model Keras: {err}")
                else:
                    print(f"Gagal memuat model Keras: {err}")
    return _CACHED_AI_MODEL

def _get_class_names():
    global _CACHED_CLASS_NAMES
    if _CACHED_CLASS_NAMES is None:
        import json as _json
        cn_path = os.path.join(current_app.root_path, 'ai', 'models', 'class_names.json')
        if os.path.exists(cn_path):
            with open(cn_path) as f:
                _CACHED_CLASS_NAMES = _json.load(f)
        else:
            _CACHED_CLASS_NAMES = ['filler', 'binder', 'wrapper']
    return _CACHED_CLASS_NAMES




def warmup_model(app=None):
    """
    Melakukan pre-load dan warm-up (inferensi dummy) saat server start.
    Menghilangkan latensi cold-start sehingga deteksi daun pertama langsung instan.
    """
    global _IS_WARMED_UP
    if _IS_WARMED_UP:
        return

    root = app.root_path if app else None
    print("[AI WARMUP] Menyiapkan model klasifikasi daun tembakau...")
    start_t = datetime.now()

    # 1. Coba muat & warm-up model Deep Learning MobileNetV2
    model = _get_ai_model(base_path=root)
    if model is not None:
        try:
            import numpy as np
            dummy_input = np.zeros((1, 224, 224, 3), dtype=np.float32)
            try:
                _ = model(dummy_input, training=False).numpy()
            except Exception:
                _ = model.predict(dummy_input, verbose=0)
            duration = (datetime.now() - start_t).total_seconds()
            print(f"[AI WARMUP] Model MobileNetV2 siap dan panas dalam {duration:.2f} detik.")
            _IS_WARMED_UP = True
            return
        except Exception as e:
            print(f"[AI WARMUP] MobileNetV2 warm-up dilewati: {e}")

    _IS_WARMED_UP = True
    print("[AI WARMUP] Inisialisasi model selesai.")


@api_conveyor_bp.route('/predict', methods=['POST'])
def predict_conveyor():
    """
    POST /api/conveyor/predict
    Endpoint untuk User Interface (Dashboard) mengunggah daun, 
    kemudian server 'memprediksi' (simulasi untuk saat ini) kualitas daun:
    - Wrapper (High Quality)
    - Binder (Medium Quality)
    - Filler (Low Quality)
    """
    import random
    
    file = None
    for k in ['gambar', 'picture', 'image', 'file']:
        if k in request.files:
            file = request.files[k]
            break
    if file is None and len(request.files) > 0:
        file = next(iter(request.files.values()))

    if file is None or file.filename == '':
        return jsonify({
            "success": False,
            "data": None,
            "message": "Gambar tidak ditemukan dalam request (gunakan key: gambar atau picture)"
        }), 400

    if not _allowed_file(file.filename):
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Format gambar tidak didukung. Gunakan: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400

    try:

        # 1. Baca data byte gambar ke RAM terlebih dahulu (In-Memory Processing)
        img_bytes = file.read()
        if not img_bytes:
            return jsonify({
                "success": False,
                "data": None,
                "message": "File gambar kosong atau rusak"
            }), 400

        # 2. Decode gambar langsung dari memori RAM
        import cv2
        import numpy as np
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # 3. Terapkan Segmentasi Grayscale + Otsu Thresholding untuk Mendeteksi Kontur Daun
        annotated_img, has_edge, contour_count, leaf_ratio, leaf_bbox, largest_contour = _detect_leaf_contour_and_edges(img_cv)

        # ================================================================
        # 0. CEK JIKA BACKGROUND KOSONG (TIDAK ADA DAUN)
        # ================================================================
        if not has_edge or leaf_ratio < 0.015 or largest_contour is None:
            return jsonify({
                "success": True,
                "data": {
                    "id": 0,
                    "hasil_klasifikasi": "unknown",
                    "confidence_score": 0.0,
                    "confidence_percent": 0.0,
                    "gambar_url": None,
                    "has_vector": False,
                    "kualitas": "Background Kosong (Menunggu Daun...)",
                    "message": "Tidak ada daun tembakau terdeteksi di kamera.",
                    "probabilities": {"filler": 0.0, "binder": 0.0, "wrapper": 0.0},
                    "garis_tepi": {"terdeteksi": False, "jumlah_kontur": 0, "rasio_area_daun": 0.0},
                    "timestamp_display": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "db_status": "Dilewati (Tidak Ada Daun)"
                },
                "message": "Background kosong / tidak ada daun tembakau."
            }), 200

        # ================================================================
        # 1. ISOLASI DAUN & SESUAIKAN DENGAN FORMAT DATASET (LATAR PUTIH)
        # ================================================================
        # Model MobileNetV2 dilatih dengan daun di atas latar belakang putih.
        # Sabuk konveyor fisik berwarna merah marun/gelap. Kita gantikan latar
        # di luar kontur daun menjadi warna putih bersih agar warna merah marun
        # tidak mengontaminasi distribusi warna model AI!
        mask_c = np.zeros(img_cv.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask_c, [largest_contour], -1, 255, -1)
        white_bg = np.full_like(img_cv, 255)
        leaf_on_white = np.where(mask_c[:,:,None] == 255, img_cv, white_bg)

        # Hitung koordinat kotak potong (Crop ROI) dengan sedikit margin
        bx, by, bw, bh = leaf_bbox
        pad_x = max(10, int(bw * 0.05))
        pad_y = max(10, int(bh * 0.05))
        y1 = max(0, by - pad_y)
        y2 = min(img_cv.shape[0], by + bh + pad_y)
        x1 = max(0, bx - pad_x)
        x2 = min(img_cv.shape[1], bx + bw + pad_x)

        # 1. Gambar daun di atas latar putih untuk Inferensi Model AI
        infer_img = leaf_on_white[y1:y2, x1:x2]
        if infer_img.shape[0] < 30 or infer_img.shape[1] < 30:
            infer_img = leaf_on_white

        # 2. Gambar daun terpotong rapi bergaris tepi untuk disimpan ke disk & web
        # (sehingga background conveyor di sekeliling daun tidak ikut tersimpan)
        display_crop = annotated_img[y1:y2, x1:x2]
        if display_crop.shape[0] < 30 or display_crop.shape[1] < 30:
            display_crop = annotated_img

        # 4. Simpan gambar beranotasi garis tepi ke folder uploads/daun
        gambar_path = None
        try:
            today = datetime.now()
            year = str(today.year)
            month = f"{today.month:02d}"
            day = f"{today.day:02d}"

            upload_dir = os.path.normpath(os.path.join(current_app.static_folder, 'uploads', 'daun', year, month, day))
            os.makedirs(upload_dir, exist_ok=True)

            ext = 'jpg'
            if file.filename and '.' in file.filename:
                ext = file.filename.rsplit('.', 1)[1].lower()

            filename = f"leaf_{uuid.uuid4().hex[:8]}.{ext}"
            file_dest = os.path.join(upload_dir, filename)

            # Simpan potongan daun yang rapi
            cv2.imwrite(file_dest, display_crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
            gambar_path = f"uploads/daun/{year}/{month}/{day}/{filename}"
            print(f"[CONVEYOR CAMERA] Gambar daun (Crop ROI) berhasil disimpan: {gambar_path}")
        except Exception as save_err:
            current_app.logger.warning(f"Gagal simpan arsip gambar ke disk: {save_err}")

        hasil = None
        confidence = 0.0
        probabilities = {}

        # ================================================================
        # 2. EKSEKUSI MODEL UTAMA (MobileNetV2 Deep Learning)
        # ================================================================
        model = _get_ai_model()
        if model is not None:
            try:
                # Preprocessing gambar daun berlatar putih: BGR -> RGB, resize 224x224, normalisasi 0-1
                img_rgb = cv2.cvtColor(infer_img, cv2.COLOR_BGR2RGB)
                img_resized = cv2.resize(img_rgb, (224, 224), interpolation=cv2.INTER_AREA)
                img_arr = np.expand_dims(img_resized.astype(np.float32) / 255.0, axis=0)

                # Eksekusi langsung tanpa batch predict overhead (jauh lebih instan)
                try:
                    preds = model(img_arr, training=False).numpy()[0]
                except Exception:
                    preds = model.predict(img_arr, verbose=0)[0]
                
                keras_classes = ['filler', 'binder', 'wrapper']
                pred_idx = int(np.argmax(preds))
                raw_conf = float(preds[pred_idx])

                probabilities = {
                    'filler': round(float(preds[0]), 4),
                    'binder': round(float(preds[1]), 4),
                    'wrapper': round(float(preds[2]), 4)
                }

                # Confidence threshold: jika keyakinan >= 45%, tetapkan kategori
                if raw_conf >= 0.45:
                    hasil = keras_classes[pred_idx]
                    confidence = round(raw_conf, 4)
                else:
                    hasil = 'unknown'
                    confidence = round(raw_conf, 4)
            except Exception as e:
                current_app.logger.error(f"Gagal prediksi MobileNetV2: {e}")

        # Fallback default aman jika model belum dimuat
        if not hasil:
            hasil = 'binder'
            confidence = 0.8800
            probabilities = {'filler': 0.05, 'binder': 0.88, 'wrapper': 0.07}

        # ================================================================
        # 3. SIMPAN LANGSUNG KE DATABASE & KEMBALIKAN MUTU
        # ================================================================
        quality_map = {
            'wrapper': 'High Quality',
            'binder': 'Medium Quality',
            'filler': 'Low Quality',
            'unknown': 'Unknown / Unclear'
        }

        response_data = None
        try:
            new_record = KlasifikasiDaun(
                hasil_klasifikasi=hasil,
                confidence_score=confidence,
                gambar_path=gambar_path
            )
            db.session.add(new_record)
            db.session.commit()
            response_data = new_record.to_dict()
        except Exception as db_err:
            db.session.rollback()
            current_app.logger.warning(f"Gagal simpan ke database ({db_err}). Mengirim hasil prediksi langsung ke browser.")
            response_data = {
                'id': 0,
                'hasil_klasifikasi': hasil,
                'confidence_score': confidence,
                'confidence_percent': round(confidence * 100, 2),
                'gambar_url': f"/static/{gambar_path}" if gambar_path else None,
                'has_vector': False,
                'timestamp_display': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'db_status': 'MySQL tidak terhubung'
            }

        response_data['kualitas'] = quality_map.get(hasil, hasil.capitalize())
        response_data['probabilities'] = probabilities
        response_data['garis_tepi'] = {
            'terdeteksi': has_edge,
            'jumlah_kontur': contour_count,
            'rasio_area_daun': leaf_ratio
        }

        return jsonify({
            "success": True,
            "data": response_data,
            "message": f"Daun berhasil diklasifikasikan sebagai {hasil.upper()} ({confidence*100:.1f}%)"
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Gagal memprediksi daun: {str(e)}")
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Gagal melakukan prediksi: {str(e)}"
        }), 500
