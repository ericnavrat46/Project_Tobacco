import random
from datetime import datetime, timedelta, timezone
from app import create_app
from models import db
from models.gudang import MonitoringGudang
from models.klasifikasi import KlasifikasiDaun

app = create_app()

def seed():
    with app.app_context():
        # Jangan hapus jika sudah ada banyak data, tapi jika kosong, tambahkan data awal
        count_gudang = MonitoringGudang.query.count()
        count_klasifikasi = KlasifikasiDaun.query.count()

        print(f"Current records - Gudang: {count_gudang}, Klasifikasi: {count_klasifikasi}")

        now = datetime.now(timezone.utc)

        # 1. Seed data monitoring gudang (48 data points, 1 setiap 30 menit selama 24 jam terakhir)
        if count_gudang == 0:
            print("Seeding data monitoring gudang (24 jam terakhir)...")
            gudang_records = []
            base_temp = 25.5
            base_humidity = 65.0
            base_gas = 85

            for i in range(48, -1, -1):
                t = now - timedelta(minutes=i * 30)
                
                # Simulasi fluktuasi siang-malam
                hour = t.hour
                temp_variance = 2.0 if (11 <= hour <= 15) else (-1.5 if (2 <= hour <= 6) else 0.5)
                suhu = round(base_temp + temp_variance + random.uniform(-0.8, 0.8), 2)
                
                hum_variance = -3.0 if (11 <= hour <= 15) else (2.0 if (2 <= hour <= 6) else -0.5)
                kelembapan = round(base_humidity + hum_variance + random.uniform(-1.5, 1.5), 2)
                
                gas = int(base_gas + random.randint(-20, 25))
                
                # Fan menyala jika suhu > 27 atau kelembapan > 67
                status_fan = (suhu > 27.0 or kelembapan > 67.0)
                status_alarm = False

                record = MonitoringGudang(
                    suhu=suhu,
                    kelembapan=kelembapan,
                    gas=gas,
                    status_fan=status_fan,
                    status_alarm=status_alarm,
                    timestamp=t
                )
                gudang_records.append(record)

            db.session.bulk_save_objects(gudang_records)
            db.session.commit()
            print(f"Berhasil menambahkan {len(gudang_records)} data monitoring gudang.")

        # 2. Seed data klasifikasi daun (60 data points)
        if count_klasifikasi == 0:
            print("Seeding data klasifikasi daun conveyor...")
            categories = ['wrapper', 'binder', 'filler']
            # Bobot: wrapper 40%, binder 35%, filler 25%
            weights = [0.40, 0.35, 0.25]
            
            klasifikasi_records = []
            for i in range(60, -1, -1):
                t = now - timedelta(minutes=i * 18 + random.randint(0, 10))
                kategori = random.choices(categories, weights=weights)[0]
                conf = round(random.uniform(0.85, 0.99), 4)

                record = KlasifikasiDaun(
                    hasil_klasifikasi=kategori,
                    confidence_score=conf,
                    timestamp=t
                )
                klasifikasi_records.append(record)

            db.session.bulk_save_objects(klasifikasi_records)
            db.session.commit()
            print(f"Berhasil menambahkan {len(klasifikasi_records)} data klasifikasi daun.")

        print("Seeding selesai dengan sukses!")

if __name__ == '__main__':
    seed()
