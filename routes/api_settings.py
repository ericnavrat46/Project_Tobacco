from flask import Blueprint, jsonify, request
from models import db
from models.settings import Settings

api_settings_bp = Blueprint('api_settings', __name__, url_prefix='/api/settings')

def get_or_create_settings():
    settings = Settings.query.get(1)
    if not settings:
        settings = Settings(id=1)
        db.session.add(settings)
        db.session.commit()
    return settings

@api_settings_bp.route('', methods=['GET'])
def get_settings():
    try:
        settings = get_or_create_settings()
        return jsonify({
            "success": True,
            "data": settings.to_dict(),
            "message": "Pengaturan berhasil diambil"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Gagal mengambil pengaturan: {str(e)}"
        }), 500

@api_settings_bp.route('', methods=['PUT'])
def update_settings():
    try:
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "data": None,
                "message": "Format data tidak valid (membutuhkan JSON)"
            }), 400

        settings = get_or_create_settings()

        new_suhu_min = float(data['suhu_min']) if 'suhu_min' in data else float(settings.suhu_min)
        new_suhu_max = float(data['suhu_max']) if 'suhu_max' in data else float(settings.suhu_max)
        new_kel_min = float(data['kelembapan_min']) if 'kelembapan_min' in data else float(settings.kelembapan_min)
        new_kel_max = float(data['kelembapan_max']) if 'kelembapan_max' in data else float(settings.kelembapan_max)
        new_gas_min = int(data['gas_min']) if 'gas_min' in data else int(settings.gas_min)
        new_gas_max = int(data['gas_threshold']) if 'gas_threshold' in data else int(settings.gas_threshold)

        if new_suhu_min >= new_suhu_max:
            return jsonify({"success": False, "data": None, "message": "Batas Suhu Minimal harus lebih kecil dari Batas Suhu Maksimal"}), 400
        if new_kel_min >= new_kel_max:
            return jsonify({"success": False, "data": None, "message": "Batas Kelembapan Minimal harus lebih kecil dari Batas Kelembapan Maksimal"}), 400
        if new_gas_min >= new_gas_max:
            return jsonify({"success": False, "data": None, "message": "Batas Gas Minimal harus lebih kecil dari Batas Gas Maksimal"}), 400

        settings.suhu_min = new_suhu_min
        settings.suhu_max = new_suhu_max
        settings.kelembapan_min = new_kel_min
        settings.kelembapan_max = new_kel_max
        settings.gas_min = new_gas_min
        settings.gas_threshold = new_gas_max

        if 'mode_fan' in data:
            settings.mode_fan = str(data['mode_fan']).strip().lower()
        if 'status_fan_manual' in data:
            settings.status_fan_manual = bool(data['status_fan_manual'])

        db.session.commit()

        return jsonify({
            "success": True,
            "data": settings.to_dict(),
            "message": "Pengaturan berhasil disimpan"
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Gagal menyimpan pengaturan: {str(e)}"
        }), 500
