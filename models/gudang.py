from datetime import datetime, timezone
from models import db
from config import Config

class MonitoringGudang(db.Model):
    __tablename__ = 'monitoring_gudang'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    suhu = db.Column(db.Float, nullable=False)
    kelembapan = db.Column(db.Float, nullable=False)
    gas = db.Column(db.Integer, nullable=False)
    status_fan = db.Column(db.Boolean, nullable=False, default=False)
    status_alarm = db.Column(db.Boolean, nullable=False, default=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    @property
    def status_suhu(self):
        """Menentukan status suhu: normal, warning, danger"""
        if Config.TEMP_NORMAL_MIN <= self.suhu <= Config.TEMP_NORMAL_MAX:
            return 'normal'
        elif self.suhu <= Config.TEMP_WARNING_MAX and self.suhu >= (Config.TEMP_NORMAL_MIN - 4.0):
            return 'warning'
        return 'danger'

    @property
    def status_kelembapan(self):
        """Menentukan status kelembapan: normal, warning, danger"""
        if Config.HUMIDITY_NORMAL_MIN <= self.kelembapan <= Config.HUMIDITY_NORMAL_MAX:
            return 'normal'
        elif Config.HUMIDITY_WARNING_MIN <= self.kelembapan <= Config.HUMIDITY_WARNING_MAX:
            return 'warning'
        return 'danger'

    @property
    def status_gas(self):
        """Menentukan status gas: normal, warning, danger"""
        if self.gas <= Config.GAS_NORMAL_MAX:
            return 'normal'
        elif self.gas <= Config.GAS_WARNING_MAX:
            return 'warning'
        return 'danger'

    def to_dict(self):
        # Format timestamp to ISO 8601 string and local display format
        ts_iso = self.timestamp.isoformat() if self.timestamp else None
        ts_display = self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None

        return {
            'id': self.id,
            'suhu': round(float(self.suhu), 2),
            'kelembapan': round(float(self.kelembapan), 2),
            'gas': int(self.gas),
            'status_fan': bool(self.status_fan),
            'status_alarm': bool(self.status_alarm),
            'timestamp': ts_iso,
            'timestamp_display': ts_display,
            'status_eval': {
                'suhu': self.status_suhu,
                'kelembapan': self.status_kelembapan,
                'gas': self.status_gas,
                'overall': 'danger' if (self.status_alarm or self.status_suhu == 'danger' or self.status_gas == 'danger' or self.status_kelembapan == 'danger')
                           else ('warning' if (self.status_suhu == 'warning' or self.status_gas == 'warning' or self.status_kelembapan == 'warning')
                           else 'normal')
            }
        }

    def __repr__(self):
        return f"<MonitoringGudang id={self.id} suhu={self.suhu}°C kelembapan={self.kelembapan}% gas={self.gas}>"
