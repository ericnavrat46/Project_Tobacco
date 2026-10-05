from datetime import datetime, timezone
import json
from models import db

class KlasifikasiDaun(db.Model):
    __tablename__ = 'klasifikasi_daun'

    id                = db.Column(db.Integer, primary_key=True, autoincrement=True)
    hasil_klasifikasi = db.Column(db.String(50), nullable=False)
    confidence_score  = db.Column(db.Float, nullable=False)
    timestamp         = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # -------------------------------------------------------------------------
    # gambar_path: Path file gambar asli di filesystem (opsional).
    #   - Disimpan jika kamera mengirim gambar (untuk keperluan audit visual).
    #   - NULL jika dikirim dari Wemos tanpa kamera.
    #   - File fisik ada di: static/uploads/daun/YYYY/MM/DD/
    #   - Contoh: "uploads/daun/2026/10/02/leaf_abc123.jpg"
    # -------------------------------------------------------------------------
    gambar_path = db.Column(db.String(255), nullable=True, default=None)

    # -------------------------------------------------------------------------
    # fitur_vektor: Feature embedding vector dari CNN (MobileNetV2 / EfficientNet).
    #
    #   Mengapa vektor bukan gambar?
    #   - Gambar JPEG: 200 KB - 1 MB → berat, sulit di-query
    #   - Vektor 1280 float32: ~5 KB → ringan, bisa di-query & dibandingkan
    #
    #   Isi kolom: JSON array float, contoh: "[0.231, 0.891, 0.004, ...]"
    #   Panjang: 1280 nilai (output GlobalAveragePooling2D MobileNetV2)
    #            atau 1536 nilai (EfficientNetB2), tergantung model yang dipakai
    #
    #   Kegunaan vektor:
    #   1. Similarity search: "Temukan daun yang mirip dengan ini"
    #   2. Re-klasifikasi ulang tanpa perlu gambar asli
    #   3. Deteksi anomali: daun yang vektornya jauh dari centroid kelas
    #   4. Active learning: cari sampel yang paling informatif untuk di-label ulang
    #
    #   NULL jika inferensi dilakukan tanpa modul ekstraksi fitur
    #   (misalnya klasifikasi manual dari Wemos, confidence 1.0)
    # -------------------------------------------------------------------------
    fitur_vektor = db.Column(db.Text, nullable=True, default=None)

    VALID_CATEGORIES = ['wrapper', 'binder', 'filler']

    @property
    def gambar_url(self):
        """URL publik untuk mengakses gambar dari browser."""
        if self.gambar_path:
            return f"/static/{self.gambar_path}"
        return None

    @property
    def vektor(self):
        """Kembalikan fitur_vektor sebagai Python list of float."""
        if self.fitur_vektor:
            try:
                return json.loads(self.fitur_vektor)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    @vektor.setter
    def vektor(self, value):
        """Set vektor dari list of float atau None."""
        if value is not None:
            self.fitur_vektor = json.dumps([round(float(v), 6) for v in value])
        else:
            self.fitur_vektor = None

    def to_dict(self, include_vector=False):
        ts_iso     = self.timestamp.isoformat() if self.timestamp else None
        ts_display = self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None

        conf         = float(self.confidence_score)
        conf_percent = conf * 100 if conf <= 1.0 else conf

        result = {
            'id':                 self.id,
            'hasil_klasifikasi':  self.hasil_klasifikasi.lower(),
            'confidence_score':   round(conf, 4),
            'confidence_percent': round(conf_percent, 2),
            'gambar_url':         self.gambar_url,
            'has_vector':         self.fitur_vektor is not None,
            'timestamp':          ts_iso,
            'timestamp_display':  ts_display,
        }

        # Vektor tidak disertakan by default (terlalu besar untuk list API)
        # Gunakan include_vector=True hanya saat dibutuhkan (detail view / similarity)
        if include_vector:
            result['fitur_vektor'] = self.vektor

        return result

    def __repr__(self):
        has_vec = "✓vektor" if self.fitur_vektor else "no-vektor"
        return f"<KlasifikasiDaun id={self.id} hasil={self.hasil_klasifikasi} conf={self.confidence_score} {has_vec}>"
