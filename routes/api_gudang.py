from flask import Blueprint, request, jsonify
from datetime import datetime, time
from models import db
from models.gudang import MonitoringGudang
from models.settings import Settings

api_gudang_bp = Blueprint('api_gudang', __name__, url_prefix='/api/gudang')


# ==================================================================
# GET /api/gudang/fan_state
# Endpoint yang di-polling ESP32 setiap 2 detik untuk mengetahui
# perintah fan (ON/OFF) dan mode (AUTO/MANUAL) dari web UI.
# ==================================================================
@api_gudang_bp.route('/fan_state', methods=['GET'])
def get_fan_state():
    """
    Mengembalikan status fan, mode, dan threshold dari tabel Settings.
    Response JSON:
    {
        "fan": "ON" | "OFF",
        "mode": "AUTO" | "MANUAL",
        "suhu_min": 20.0,
        "suhu_max": 25.0,
        "kelembapan_min": 60.0,
        "kelembapan_max": 70.0,
        "gas_min": 1050,
        "gas_threshold": 1500
    }
    """
    try:
        db.session.expire_all()
        settings = Settings.query.get(1)
        if not settings:
            return jsonify({
                "fan": "OFF",
                "mode": "AUTO",
                "suhu_min": 20.0,
                "suhu_max": 25.0,
                "kelembapan_min": 60.0,
                "kelembapan_max": 70.0,
                "gas_min": 1050,
                "gas_threshold": 1500
            }), 200

        mode = settings.mode_fan.strip().upper() if settings.mode_fan else "AUTO"
        fan = "ON" if settings.status_fan_manual else "OFF"

        return jsonify({
            "fan": fan,
            "mode": mode,
            "suhu_min": round(float(settings.suhu_min), 2),
            "suhu_max": round(float(settings.suhu_max), 2),
            "kelembapan_min": round(float(settings.kelembapan_min), 2),
            "kelembapan_max": round(float(settings.kelembapan_max), 2),
            "gas_min": int(settings.gas_min),
            "gas_threshold": int(settings.gas_threshold)
        }), 200
    except Exception:
        return jsonify({
            "fan": "OFF",
            "mode": "AUTO",
            "suhu_min": 20.0,
            "suhu_max": 25.0,
            "kelembapan_min": 60.0,
            "kelembapan_max": 70.0,
            "gas_min": 1050,
            "gas_threshold": 1500
        }), 200

@api_gudang_bp.route('', methods=['POST'])
def receive_gudang_data():
    """
    POST /api/gudang
    Terima data JSON dari ESP32, simpan ke database.
    Payload contoh:
    {
        "suhu": 26.5,
        "kelembapan": 64.0,
        "gas": 85,
        "status_fan": true,
        "status_alarm": false
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                "success": False,
                "data": None,
                "message": "Request body harus berupa JSON yang valid"
            }), 400

        # Validasi field yang wajib
        required_fields = ['suhu', 'kelembapan', 'gas']
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Field wajib tidak ditemukan: {', '.join(missing_fields)}"
            }), 400

        # Validasi dan konversi tipe data
        try:
            suhu = float(data['suhu'])
            kelembapan = float(data['kelembapan'])
            gas = int(data['gas'])
        except (ValueError, TypeError) as e:
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Tipe data tidak valid. Suhu & kelembapan harus angka, gas harus integer: {str(e)}"
            }), 400

        # Validasi rentang logis sensor
        if not (-20.0 <= suhu <= 80.0):
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Nilai suhu di luar batas wajar (-20 hingga 80 °C): {suhu}"
            }), 400

        if not (0.0 <= kelembapan <= 100.0):
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Nilai kelembapan di luar batas wajar (0 hingga 100 %): {kelembapan}"
            }), 400

        if gas < 0:
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Nilai gas tidak boleh negatif: {gas}"
            }), 400

        # Parsing boolean status fan & alarm
        def parse_bool(val, default=False):
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return val != 0
            if isinstance(val, str):
                return val.strip().lower() in ['true', '1', 'on', 'yes']
            return default

        status_fan = parse_bool(data.get('status_fan'), False)
        status_alarm = parse_bool(data.get('status_alarm'), False)

        # Buat instance record baru
        new_record = MonitoringGudang(
            suhu=suhu,
            kelembapan=kelembapan,
            gas=gas,
            status_fan=status_fan,
            status_alarm=status_alarm
        )

        # Optional timestamp manual jika dikirim dari ESP32 NTP
        if 'timestamp' in data and data['timestamp']:
            try:
                # Coba parse ISO format
                new_record.timestamp = datetime.fromisoformat(str(data['timestamp']).replace('Z', '+00:00'))
            except Exception:
                pass # Gunakan default utcnow jika gagal parse

        db.session.add(new_record)
        db.session.commit()

        return jsonify({
            "success": True,
            "data": new_record.to_dict(),
            "message": "Data monitoring gudang berhasil disimpan"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Terjadi kesalahan pada server: {str(e)}"
        }), 500


@api_gudang_bp.route('/latest', methods=['GET'])
def get_latest_gudang():
    """
    GET /api/gudang/latest
    Ambil data terbaru monitoring gudang
    """
    try:
        latest = MonitoringGudang.query.order_by(MonitoringGudang.timestamp.desc(), MonitoringGudang.id.desc()).first()
        if not latest:
            return jsonify({
                "success": True,
                "data": None,
                "message": "Belum ada data monitoring gudang"
            }), 200

        return jsonify({
            "success": True,
            "data": latest.to_dict(),
            "message": "Data monitoring gudang terbaru berhasil diambil"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Gagal mengambil data terbaru: {str(e)}"
        }), 500


@api_gudang_bp.route('/history', methods=['GET'])
def get_gudang_history():
    """
    GET /api/gudang/history
    Query params:
      - limit: int (default 50, max 1000)
      - start_date: YYYY-MM-DD
      - end_date: YYYY-MM-DD
      - order: 'asc' atau 'desc' (default: 'asc' untuk grafik, atau 'desc')
    """
    try:
        limit = request.args.get('limit', default=50, type=int)
        if limit <= 0:
            limit = 50
        elif limit > 1000:
            limit = 1000

        order_param = request.args.get('order', default='asc').lower()
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        query = MonitoringGudang.query

        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                query = query.filter(MonitoringGudang.timestamp >= start_dt)
            except ValueError:
                pass

        if end_date_str:
            try:
                end_dt = datetime.combine(datetime.strptime(end_date_str, '%Y-%m-%d'), time.max)
                query = query.filter(MonitoringGudang.timestamp <= end_dt)
            except ValueError:
                pass

        # Sort order
        if order_param == 'desc':
            records = query.order_by(MonitoringGudang.timestamp.desc(), MonitoringGudang.id.desc()).limit(limit).all()
        else:
            # Default asc untuk plotting grafik berurutan
            # Jika menggunakan limit, ambil N terakhir lalu urutkan kronologis
            records = query.order_by(MonitoringGudang.timestamp.desc(), MonitoringGudang.id.desc()).limit(limit).all()
            records.reverse()

        try:
            from models.settings import Settings
            settings = Settings.query.get(1)
        except Exception:
            settings = None

        return jsonify({
            "success": True,
            "count": len(records),
            "data": [r.to_dict(settings=settings) for r in records],
            "message": "Histori data monitoring gudang berhasil diambil"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Gagal mengambil histori gudang: {str(e)}"
        }), 500
