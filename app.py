from flask import Flask, jsonify, request
from flask_cors import CORS
from config import Config
from models import db
from models.gudang import MonitoringGudang
from models.klasifikasi import KlasifikasiDaun
from routes.views import views_bp
from routes.api_gudang import api_gudang_bp
from routes.api_conveyor import api_conveyor_bp
from routes.api_export import api_export_bp
from routes.api_settings import api_settings_bp
from routes.api_chatbot import api_chatbot_bp
from models.settings import Settings

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inisialisasi CORS untuk seluruh rute API
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Inisialisasi Database
    db.init_app(app)

    # Middleware untuk membersihkan spasi / baris baru accidental di URL
    class StripPathMiddleware:
        def __init__(self, wsgi_app):
            self.wsgi_app = wsgi_app
        def __call__(self, environ, start_response):
            path = environ.get('PATH_INFO', '')
            if path:
                environ['PATH_INFO'] = path.rstrip(' \r\n\t')
            return self.wsgi_app(environ, start_response)

    app.wsgi_app = StripPathMiddleware(app.wsgi_app)

    # Register Blueprints
    app.register_blueprint(views_bp)
    app.register_blueprint(api_gudang_bp)
    app.register_blueprint(api_conveyor_bp)
    app.register_blueprint(api_export_bp)
    app.register_blueprint(api_settings_bp)
    app.register_blueprint(api_chatbot_bp)

    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            "success": True,
            "data": {
                "status": "online",
                "system": "Tobacco Warehouse & Conveyor IoT Backend",
                "version": "1.0.0"
            },
            "message": "Sistem monitoring gudang tembakau berjalan normal"
        }), 200

    # Error handling standar JSON untuk request API
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Endpoint '{request.path}' tidak ditemukan"
            }), 404
        return ("<h1>404 Not Found</h1><p>Halaman tidak ditemukan.</p>", 404)

    @app.errorhandler(405)
    def method_not_allowed_error(error):
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Metode HTTP '{request.method}' tidak diizinkan untuk endpoint ini"
            }), 405
        return ("<h1>405 Method Not Allowed</h1>", 405)

    @app.errorhandler(500)
    def internal_server_error(error):
        if request.path.startswith('/api/'):
            return jsonify({
                "success": False,
                "data": None,
                "message": "Terjadi kesalahan internal server"
            }), 500
        return ("<h1>500 Internal Server Error</h1>", 500)

    # Buat tabel jika belum ada & pastikan kolom baru pada settings tersedia
    with app.app_context():
        db.create_all()
        try:
            from sqlalchemy import inspect, text
            existing_cols = {c['name'] for c in inspect(db.engine).get_columns('settings')}
            alter_stmts = []
            if 'suhu_min' not in existing_cols:
                alter_stmts.append("ALTER TABLE settings ADD COLUMN suhu_min FLOAT NOT NULL DEFAULT 20.0")
            if 'kelembapan_min' not in existing_cols:
                alter_stmts.append("ALTER TABLE settings ADD COLUMN kelembapan_min FLOAT NOT NULL DEFAULT 60.0")
            if 'gas_min' not in existing_cols:
                alter_stmts.append("ALTER TABLE settings ADD COLUMN gas_min INT NOT NULL DEFAULT 1050")
            if alter_stmts:
                with db.engine.begin() as conn:
                    for stmt in alter_stmts:
                        conn.execute(text(stmt))
        except Exception as e:
            print(f"[DB Migration Warning] {e}")

    return app

app = create_app()

if __name__ == '__main__':
    # Default host 0.0.0.0 agar bisa diakses oleh ESP32 & Wemos dalam jaringan lokal
    app.run(host='0.0.0.0', port=5000, debug=True)
