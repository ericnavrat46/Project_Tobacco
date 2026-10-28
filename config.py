import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-tobacco-monitoring-2026')

    # =========================================================================
    # Konfigurasi MySQL (Laragon / phpMyAdmin)
    # Ubah DB_USER, DB_PASSWORD, DB_HOST, DB_PORT jika berbeda
    # =========================================================================
    DB_HOST     = os.environ.get('DB_HOST', '127.0.0.1')
    DB_PORT     = os.environ.get('DB_PORT', '3306')
    DB_USER     = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')          # Laragon default: kosong
    DB_NAME     = os.environ.get('DB_NAME', 'tobacco_monitoring')

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,        # Recycle koneksi sebelum timeout MySQL (default 8 jam)
        'pool_pre_ping': True,      # Ping sebelum pakai koneksi (cegah "MySQL server has gone away")
        'pool_size': 5,
        'max_overflow': 10,
    }
    JSON_SORT_KEYS = False

    # Ambang batas (Thresholds) untuk Gudang Tembakau
    # Suhu ideal tembakau: 20°C - 28°C
    TEMP_NORMAL_MIN = 20.0
    TEMP_NORMAL_MAX = 28.0
    TEMP_WARNING_MAX = 32.0

    # Kelembapan ideal tembakau (RH): 60% - 70%
    HUMIDITY_NORMAL_MIN = 60.0
    HUMIDITY_NORMAL_MAX = 70.0
    HUMIDITY_WARNING_MIN = 50.0
    HUMIDITY_WARNING_MAX = 75.0

    # Ambang batas Gas (ppm / sensor raw)
    GAS_NORMAL_MAX = 150
    GAS_WARNING_MAX = 300
