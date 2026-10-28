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

        if 'suhu_max' in data:
            settings.suhu_max = float(data['suhu_max'])
        if 'kelembapan_max' in data:
            settings.kelembapan_max = float(data['kelembapan_max'])
        if 'gas_threshold' in data:
            settings.gas_threshold = int(data['gas_threshold'])
        if 'mode_fan' in data:
            settings.mode_fan = str(data['mode_fan'])
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
