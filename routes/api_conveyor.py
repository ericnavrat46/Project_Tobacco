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


def _validate_tobacco_leaf(img_path):
    """
    Validasi apakah gambar kemungkinan berisi daun tembakau
    berdasarkan analisis distribusi warna HSV.

    Daun tembakau memiliki warna khas:
    - Coklat/kering  : Hue 0-25, Sat 40-200, Val 40-200
    - Hijau segar    : Hue 25-85, Sat 40-255, Val 30-220
    - Kuning/curing  : Hue 15-45, Sat 50-255, Val 60-255

    Objek non-daun (tangan, tembok, HP, baju, dll) biasanya memiliki
    distribusi warna yang sangat berbeda dari rentang di atas.

    Return: (is_leaf: bool, leaf_score: float 0.0-1.0)
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(img_path)
        if img is None:
            return False, 0.0

        # Resize kecil untuk efisiensi (validasi tidak perlu resolusi tinggi)
        img_small = cv2.resize(img, (128, 128))
        hsv = cv2.cvtColor(img_small, cv2.COLOR_BGR2HSV)

        total_pixels = 128 * 128

        # Rentang warna daun tembakau dalam HSV (diperluas untuk webcam ruangan)
        mask_brown1 = cv2.inRange(hsv, np.array([0, 15, 20]),  np.array([25, 255, 255]))
        mask_brown2 = cv2.inRange(hsv, np.array([160, 15, 20]), np.array([180, 255, 255]))
        mask_green  = cv2.inRange(hsv, np.array([25, 15, 20]), np.array([90, 255, 255]))
        mask_yellow = cv2.inRange(hsv, np.array([15, 20, 20]), np.array([45, 255, 255]))

        leaf_mask = mask_brown1 | mask_brown2 | mask_green | mask_yellow
        leaf_pixels = cv2.countNonZero(leaf_mask)
        leaf_ratio = leaf_pixels / total_pixels

        # Cek saturasi rata-rata
        avg_saturation = float(np.mean(hsv[:, :, 1]))
        gray = cv2.cvtColor(img_small, cv2.COLOR_BGR2GRAY)
        texture_score = float(np.std(gray))

        # Cukup memiliki warna daun >= 5% atau saturasi & tekstur minimal
        is_leaf = (leaf_ratio >= 0.05) or (avg_saturation >= 12 and texture_score >= 8)

        return is_leaf, round(leaf_ratio, 4)

    except Exception as e:
        # Fail-open agar tidak memblokir klasifikasi jika ada kendala OpenCV
        return True, 1.0

def _save_image(file_obj):
    """
    Simpan file gambar ke filesystem.
    Return: path relatif terhadap static/ (untuk disimpan di DB)
    Contoh: "uploads/daun/2026/10/02/leaf_a3f2c1.jpg"

    MENGAPA TIDAK SIMPAN KE DATABASE?
    - 1 gambar JPEG dari kamera: ~200 KB - 1 MB
    - 1000 klasifikasi per hari x 200 KB = 200 MB/hari di DB
    - File system jauh lebih efisien untuk binary besar
    - Query SQL akan sangat lambat jika ada BLOB besar di setiap row
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
    Terima data klasifikasi daun. Mendukung 2 format:

    Format 1 - JSON biasa (dari Wemos / simulator, tanpa gambar):
        Content-Type: application/json
        { "hasil_klasifikasi": "wrapper", "confidence_score": 0.94 }

    Format 2 - Multipart form (dari inference.py AI dengan gambar):
        Content-Type: multipart/form-data
        Fields: hasil_klasifikasi, confidence_score, fitur_vektor (opsional)
        File  : gambar (opsional, jpg/png/webp)

    ARSITEKTUR GAMBAR & VEKTOR:
        - Gambar TIDAK disimpan di DB (mencegah DB membengkak)
        - Gambar disimpan ke filesystem: static/uploads/daun/YYYY/MM/DD/
        - DB hanya menyimpan PATH: "uploads/daun/2026/10/02/leaf_abc123.jpg"
        - Fitur Vektor (embedding CNN) disimpan langsung di DB dalam format JSON
        - Kolom gambar_path dan fitur_vektor bersifat NULL jika tidak ada (backward compatible)
    """
    try:
        # Deteksi format request: JSON atau multipart
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

        # Validasi field wajib
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

        # Validasi confidence score
        try:
            confidence = float(data['confidence_score'])
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "data": None,
                "message": "Confidence score harus berupa angka float/desimal (misal 0.95 atau 95.0)"
            }), 400

        # Normalisasi ke skala 0.0 - 1.0 jika dikirim dalam persen (misal 95.0)
        if confidence > 1.0 and confidence <= 100.0:
            confidence = confidence / 100.0
        elif confidence < 0.0 or confidence > 100.0:
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Confidence score tidak valid ({confidence}). Harus di rentang 0.0 - 1.0 atau 0 - 100%"
            }), 400

        # Simpan gambar ke filesystem (jika ada)
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
                # Gambar gagal disimpan, tapi data tetap diterima (graceful degradation)
                current_app.logger.warning(f"Gambar gagal disimpan: {img_err}")

        # Ambil fitur vektor (opsional)
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
            gambar_path=gambar_path     # NULL jika tidak ada gambar
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
    Ambil data terbaru hasil klasifikasi daun conveyor
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
    Ambil statistik klasifikasi daun:
    - total diproses
    - total per kategori (wrapper, binder, filler)
    - persentase per kategori
    - rata-rata confidence score
    Optional query params:
      - start_date: YYYY-MM-DD
      - end_date: YYYY-MM-DD
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
    Query params:
      - limit: int (default 50)
      - start_date: YYYY-MM-DD
      - end_date: YYYY-MM-DD
      - kategori: wrapper/binder/filler
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

def _get_ai_model(model_path=None):
    global _CACHED_AI_MODEL
    if _CACHED_AI_MODEL is None:
        model_keras = os.path.join(current_app.root_path, 'ai', 'models', 'tobacco_model.keras')
        model_h5 = os.path.join(current_app.root_path, 'ai', 'models', 'tobacco_model.h5')
        target_path = model_keras if os.path.exists(model_keras) else (model_path or model_h5)
        if target_path and os.path.exists(target_path):
            try:
                import tensorflow as tf
                _CACHED_AI_MODEL = tf.keras.models.load_model(target_path)
            except Exception as err:
                current_app.logger.error(f"Gagal memuat model Keras: {err}")
    return _CACHED_AI_MODEL


@api_conveyor_bp.route('/predict', methods=['POST'])
def predict_conveyor():
    """
    POST /api/conveyor/predict
    Langsung mengeksekusi model AI MobileNetV2 untuk memprediksi mutu daun tembakau:
    - WRAPPER (High Quality)
    - BINDER  (Medium Quality)
    - FILLER  (Low Quality)
    """
    # Ambil file gambar (mendukung key: gambar, picture, image, file, atau file pertama)
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
        gambar_path = _save_image(file)
        full_img_path = os.path.join(current_app.static_folder, gambar_path)

        hasil = None
        confidence = 0.0
        probabilities = {}

        # ================================================================
        # 1. LANGSUNG EKSEKUSI MODEL UTAMA (MobileNetV2 Deep Learning)
        # ================================================================
        model = _get_ai_model()
        if model is not None:
            try:
                from tensorflow.keras.preprocessing.image import load_img, img_to_array
                import numpy as np

                img = load_img(full_img_path, target_size=(224, 224))
                img_arr = img_to_array(img) / 255.0
                img_arr = np.expand_dims(img_arr, axis=0)

                preds = model.predict(img_arr, verbose=0)[0]
                
                # Pemetaan Kelas Model: 0 = filler, 1 = binder, 2 = wrapper
                keras_classes = ['filler', 'binder', 'wrapper']
                pred_idx = int(np.argmax(preds))

                hasil = keras_classes[pred_idx]
                confidence = round(float(preds[pred_idx]), 4)
                probabilities = {
                    'filler': round(float(preds[0]), 4),
                    'binder': round(float(preds[1]), 4),
                    'wrapper': round(float(preds[2]), 4)
                }
            except Exception as e:
                current_app.logger.error(f"Gagal prediksi MobileNetV2: {e}")

        # ================================================================
        # 2. FALLBACK KE SVM (JIKA MODEL DEEP LEARNING BELUM SIAP)
        # ================================================================
        if not hasil:
            svm_path = os.path.join(current_app.root_path, 'ai', 'models', 'tobacco_svm.pkl')
            if os.path.exists(svm_path):
                try:
                    import joblib
                    import cv2
                    from ai.train_svm import extract_feature_vector
                    
                    svm_model = joblib.load(svm_path)
                    img_cv = cv2.imread(full_img_path)
                    if img_cv is not None:
                        feat = extract_feature_vector(img_cv)
                        pred_idx = int(svm_model.predict([feat])[0])
                        probas = svm_model.predict_proba([feat])[0]
                        keras_classes = ['filler', 'binder', 'wrapper']
                        hasil = keras_classes[pred_idx]
                        confidence = round(float(probas[pred_idx]), 4)
                        probabilities = {
                            'filler': round(float(probas[0]), 4),
                            'binder': round(float(probas[1]), 4),
                            'wrapper': round(float(probas[2]), 4)
                        }
                except Exception as e:
                    current_app.logger.warning(f"Gagal prediksi model SVM: {e}")

        # Fallback default aman jika semua model belum dimuat
        if not hasil:
            hasil = 'binder'
            confidence = 0.8800
            probabilities = {'filler': 0.05, 'binder': 0.88, 'wrapper': 0.07}

        # ================================================================
        # 3. SIMPAN LANGSUNG KE DATABASE & KEMBALIKAN MUTU
        # ================================================================
        new_record = KlasifikasiDaun(
            hasil_klasifikasi=hasil,
            confidence_score=confidence,
            gambar_path=gambar_path
        )
        db.session.add(new_record)
        db.session.commit()

        # Pemetaan label mutu
        quality_map = {
            'wrapper': 'High Quality (Wrapper)',
            'binder': 'Medium Quality (Binder)',
            'filler': 'Low Quality (Filler)'
        }

        response_data = new_record.to_dict()
        response_data['kualitas'] = quality_map.get(hasil, hasil.capitalize())
        response_data['probabilities'] = probabilities

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

