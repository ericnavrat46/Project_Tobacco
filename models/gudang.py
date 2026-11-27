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

    def evaluate_status(self, settings=None):
        """Menentukan status evaluasi sensor berdasarkan pengaturan ambang batas dinamis"""
        if settings is None:
            try:
                from models.settings import Settings
                settings = Settings.query.get(1)
            except Exception:
                settings = None

        suhu_min = float(settings.suhu_min) if (settings and getattr(settings, 'suhu_min', None) is not None) else Config.TEMP_NORMAL_MIN
        suhu_max = float(settings.suhu_max) if (settings and hasattr(settings, 'suhu_max')) else Config.TEMP_NORMAL_MAX
        kelembapan_min = float(settings.kelembapan_min) if (settings and getattr(settings, 'kelembapan_min', None) is not None) else Config.HUMIDITY_NORMAL_MIN
        kelembapan_max = float(settings.kelembapan_max) if (settings and hasattr(settings, 'kelembapan_max')) else Config.HUMIDITY_NORMAL_MAX
        gas_min = int(settings.gas_min) if (settings and getattr(settings, 'gas_min', None) is not None) else int(Config.GAS_NORMAL_MAX)
        gas_threshold = int(settings.gas_threshold) if (settings and hasattr(settings, 'gas_threshold')) else Config.GAS_NORMAL_MAX

        # 1. Evaluasi Suhu
        if suhu_min <= self.suhu <= suhu_max:
            s_suhu = 'normal'
        elif self.suhu <= (suhu_max + 4.0) and self.suhu >= (suhu_min - 4.0):
            s_suhu = 'warning'
        else:
            s_suhu = 'danger'

        # 2. Evaluasi Kelembapan
        if kelembapan_min <= self.kelembapan <= kelembapan_max:
            s_hum = 'normal'
        elif (kelembapan_min - 10.0) <= self.kelembapan <= (kelembapan_max + 5.0):
            s_hum = 'warning'
        else:
            s_hum = 'danger'

        # 3. Evaluasi Gas
        if self.gas <= gas_min:
            s_gas = 'normal'
        elif self.gas < gas_threshold:
            s_gas = 'warning'
        else:
            s_gas = 'danger'

        overall = 'danger' if (self.status_alarm or s_suhu == 'danger' or s_hum == 'danger' or s_gas == 'danger') \
                  else ('warning' if (s_suhu == 'warning' or s_hum == 'warning' or s_gas == 'warning') else 'normal')

        return {
            'suhu': s_suhu,
            'kelembapan': s_hum,
            'gas': s_gas,
            'overall': overall,
            'thresholds': {
                'suhu_min': round(suhu_min, 1),
                'suhu_max': round(suhu_max, 1),
                'kelembapan_min': round(kelembapan_min, 1),
                'kelembapan_max': round(kelembapan_max, 1),
                'gas_min': gas_min,
                'gas_threshold': gas_threshold
            }
        }

    @property
    def status_suhu(self):
        """Menentukan status suhu: normal, warning, danger"""
        return self.evaluate_status()['suhu']

    @property
    def status_kelembapan(self):
        """Menentukan status kelembapan: normal, warning, danger"""
        return self.evaluate_status()['kelembapan']

    @property
    def status_gas(self):
        """Menentukan status gas: normal, warning, danger"""
        return self.evaluate_status()['gas']

    def to_dict(self, settings=None):
        # Format timestamp to ISO 8601 string and local display format
        ts_iso = self.timestamp.isoformat() if self.timestamp else None
        ts_display = self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None

        eval_res = self.evaluate_status(settings)

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
                'suhu': eval_res['suhu'],
                'kelembapan': eval_res['kelembapan'],
                'gas': eval_res['gas'],
                'overall': eval_res['overall']
            },
            'thresholds': eval_res['thresholds']
        }

    def __repr__(self):
        return f"<MonitoringGudang id={self.id} suhu={self.suhu}°C kelembapan={self.kelembapan}% gas={self.gas}>"
