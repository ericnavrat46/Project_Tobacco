from datetime import datetime, timezone
from models import db

class Settings(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    suhu_min = db.Column(db.Float, nullable=False, default=20.0)
    suhu_max = db.Column(db.Float, nullable=False, default=25.0)
    kelembapan_min = db.Column(db.Float, nullable=False, default=60.0)
    kelembapan_max = db.Column(db.Float, nullable=False, default=70.0)
    gas_min = db.Column(db.Integer, nullable=False, default=1050)
    gas_threshold = db.Column(db.Integer, nullable=False, default=1500)
    mode_fan = db.Column(db.String(20), nullable=False, default="auto") # "auto" or "manual"
    status_fan_manual = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'suhu_min': round(float(self.suhu_min), 2),
            'suhu_max': round(float(self.suhu_max), 2),
            'kelembapan_min': round(float(self.kelembapan_min), 2),
            'kelembapan_max': round(float(self.kelembapan_max), 2),
            'gas_min': int(self.gas_min),
            'gas_threshold': int(self.gas_threshold),
            'mode_fan': self.mode_fan,
            'status_fan_manual': bool(self.status_fan_manual),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Settings id={self.id} mode={self.mode_fan}>"
