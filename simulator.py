#!/usr/bin/env python
"""
Tobacco IoT Monitoring - Real-Time IoT Sensor & Conveyor Simulator
Simulates:
1. ESP32 Telemetry: Suhu (°C), Kelembapan (RH%), Gas (ppm), Relay Fan (ON/OFF), Alarm (Aman/Bahaya)
2. Wemos Conveyor: Deteksi daun tembakau (Wrapper, Binder, Filler) & Confidence Score

Usage:
    python simulator.py                 # Mode normal (interval 4 detik)
    python simulator.py --interval 2    # Mode cepat (interval 2 detik)
    python simulator.py --burst 10      # Kirim 10 paket data lalu selesai
    python simulator.py --hazard        # Simulasi kondisi darurat / suhu tinggi
"""

import sys
import time
import math
import random
import argparse
import json
import urllib.request
import urllib.error
from datetime import datetime

# Warna terminal ANSI (dengan fallback otomatis jika Windows tidak mendukung)
try:
    import colorama
    colorama.init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = sys.platform != 'win32' or 'WT_SESSION' in os.environ

def c(text, color_code):
    return f"\033[{color_code}m{text}\033[0m" if HAS_COLOR else text

class TobaccoIoTSimulator:
    def __init__(self, host="http://127.0.0.1:5000", interval=4.0, hazard_mode=False):
        self.host = host.rstrip('/')
        self.interval = max(0.5, float(interval))
        self.hazard_mode = hazard_mode
        self.step = 0
        
        # Base sensor values
        self.base_temp = 25.5
        self.base_humidity = 64.0
        self.base_gas = 85
        
        # State
        self.fan_state = False
        self.alarm_state = False
        
        # Settings dari server
        self.settings = {
            "suhu_max": 25.0,
            "kelembapan_max": 70.0,
            "gas_threshold": 1500,
            "mode_fan": "auto",
            "status_fan_manual": False
        }
        
        # Conveyor categories & weight
        self.leaf_categories = ['wrapper', 'binder', 'filler']
        self.leaf_weights = [0.42, 0.35, 0.23]

    def _post_json(self, endpoint, payload):
        """Mengirim HTTP POST JSON ke backend Flask"""
        url = f"{self.host}{endpoint}"
        body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'TobaccoSimulator/1.0'
            },
            method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=4) as response:
                code = response.getcode()
                res_data = json.loads(response.read().decode('utf-8'))
                return code, res_data
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode('utf-8'))
            except Exception:
                err_data = {'message': str(e)}
            return e.code, err_data
        except Exception as e:
            return 0, {'message': str(e)}

    def _get_settings(self):
        """Mengambil pengaturan dari API settings"""
        url = f"{self.host}/api/settings"
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.getcode() == 200:
                    res_data = json.loads(response.read().decode('utf-8'))
                    if res_data.get("success"):
                        self.settings.update(res_data["data"])
        except Exception:
            pass # abaikan jika gagal, pakai nilai sebelumnya

    def generate_esp32_data(self):
        """Membuat data telemetri gudang realistis dengan kurva sinus & fluktuasi"""
        self.step += 1
        
        if self.hazard_mode:
            # Skenario bahaya / alarm aktif
            suhu = round(33.5 + random.uniform(-0.5, 1.5), 1)
            kelembapan = round(44.0 + random.uniform(-2.0, 2.0), 1)
            gas = int(320 + random.randint(0, 150))
            self.fan_state = True
            self.alarm_state = True
        else:
            # Skenario normal berfluktuasi halus
            drift_temp = math.sin(self.step * 0.1) * 1.8
            drift_hum = -math.sin(self.step * 0.1) * 2.5
            
            suhu = round(self.base_temp + drift_temp + random.uniform(-0.4, 0.4), 1)
            kelembapan = round(self.base_humidity + drift_hum + random.uniform(-0.8, 0.8), 1)
            gas = int(self.base_gas + random.randint(-15, 20))
            
            # Otomatisasi Aktuator Kipas berdasarkan settings
            if self.settings["mode_fan"] == "manual":
                self.fan_state = self.settings["status_fan_manual"]
            else:
                if suhu > self.settings["suhu_max"] or kelembapan > self.settings["kelembapan_max"]:
                    self.fan_state = True
                elif suhu < self.settings["suhu_max"] - 1.5 and kelembapan < self.settings["kelembapan_max"] - 3.0:
                    self.fan_state = False
                
            # Alarm aktif hanya jika kondisi kritis (suhu > 32°C atau gas > 300 ppm)
            self.alarm_state = (suhu > 32.0 or gas > 300 or kelembapan < 48.0)

        payload = {
            "suhu": suhu,
            "kelembapan": kelembapan,
            "gas": gas,
            "status_fan": self.fan_state,
            "status_alarm": self.alarm_state
        }
        return payload

    def generate_wemos_data(self):
        """Membuat data klasifikasi daun tembakau pada conveyor"""
        kategori = random.choices(self.leaf_categories, weights=self.leaf_weights)[0]
        # Confidence score tinggi (87% - 98.8%)
        confidence = round(random.uniform(0.875, 0.988), 4)
        return {
            "hasil_klasifikasi": kategori,
            "confidence_score": confidence
        }

    def run_cycle(self):
        """Menjalankan 1 siklus simulasi data (Gudang & Conveyor)"""
        now_str = datetime.now().strftime('%H:%M:%S')

        # 0. Ambil settings terbaru
        if self.step % 2 == 0:  # ambil tiap 2 siklus (8 detik) agar tidak terlalu sering
            self._get_settings()

        # 1. Kirim Data ESP32 (Gudang)
        gudang_payload = self.generate_esp32_data()
        status_gudang, res_gudang = self._post_json('/api/gudang', gudang_payload)

        fan_badge = c("FAN: ON", "32;1") if gudang_payload["status_fan"] else c("FAN: OFF", "90")
        alarm_badge = c("[ALARM AKTIF!]", "41;97;1") if gudang_payload["status_alarm"] else c("AMAN", "32")
        
        temp_color = "31" if gudang_payload["suhu"] > 30 else ("33" if gudang_payload["suhu"] > 28 else "32")
        hum_color = "31" if (gudang_payload["kelembapan"] < 50 or gudang_payload["kelembapan"] > 75) else "36"
        gas_color = "31" if gudang_payload["gas"] > 250 else ("33" if gudang_payload["gas"] > 150 else "32")

        if status_gudang == 201:
            print(f"[{now_str}] {c('ESP32 Gudang', '35;1')} | "
                  f"Suhu: {c(str(gudang_payload['suhu']) + '°C', temp_color)} | "
                  f"RH: {c(str(gudang_payload['kelembapan']) + '%', hum_color)} | "
                  f"Gas: {c(str(gudang_payload['gas']) + ' ppm', gas_color)} | "
                  f"{fan_badge} | {alarm_badge} "
                  f"{c('-> HTTP 201 OK', '90')}")
        else:
            print(f"[{now_str}] {c('ESP32 Gudang FAILED', '31;1')} | HTTP {status_gudang}: {res_gudang.get('message')}")

        # 2. Kirim Data Wemos Conveyor (80% kemungkinan per tick ada daun lewat di conveyor)
        if random.random() < 0.85:
            conveyor_payload = self.generate_wemos_data()
            status_conveyor, res_conveyor = self._post_json('/api/conveyor', conveyor_payload)

            cat = conveyor_payload["hasil_klasifikasi"].upper()
            cat_color = "33;1" if cat == "WRAPPER" else ("33" if cat == "BINDER" else "37")
            conf_pct = round(conveyor_payload["confidence_score"] * 100, 1)

            if status_conveyor == 201:
                print(f"[{now_str}] {c('Wemos Conveyor', '34;1')} | "
                      f"Daun Terdeteksi: {c(cat, cat_color)} | "
                      f"Akurasi: {c(str(conf_pct) + '%', '32;1')} "
                      f"{c('-> HTTP 201 OK', '90')}")
            else:
                print(f"[{now_str}] {c('Wemos Conveyor FAILED', '31;1')} | HTTP {status_conveyor}: {res_conveyor.get('message')}")

    def start(self, count=None):
        """Memulai loop simulasi"""
        print("=" * 70)
        print(c("   SIMULATOR IOT GUDANG TEMBAKAU & KLASIFIKASI DAUN CONVEYOR   ", "42;97;1"))
        print("=" * 70)
        print(f"Target Server : {c(self.host, '36;1')}")
        print(f"Interval Kirim: {c(str(self.interval) + ' detik', '33;1')}")
        print(f"Mode          : {c('HAZARD TEST', '31;1') if self.hazard_mode else c('NORMAL OPERATION', '32;1')}")
        print(f"Tekan {c('Ctrl + C', '37;1')} kapan saja untuk menghentikan simulator.")
        print("-" * 70)

        # Cek koneksi awal ke server
        try:
            urllib.request.urlopen(f"{self.host}/api/health", timeout=3)
            print(c("[OK] Terkoneksi ke server TobaccoGuard IoT!", "32;1"))
        except Exception as e:
            print(c(f"[PERINGATAN] Server di {self.host} belum terdeteksi aktif ({e}).", "33"))
            print(c("Pastikan 'python app.py' sudah dijalankan terlebih dahulu.\n", "33"))

        sent = 0
        try:
            while True:
                self.run_cycle()
                sent += 1
                if count and sent >= count:
                    print("-" * 70)
                    print(c(f"Simulasi selesai. {sent} siklus data berhasil dikirim.", "32;1"))
                    break
                time.sleep(self.interval)
        except KeyboardInterrupt:
            print("\n" + "-" * 70)
            print(c(f"Simulator dihentikan oleh pengguna. Total siklus terkirim: {sent}", "33;1"))

def main():
    parser = argparse.ArgumentParser(description="Simulator IoT Gudang Tembakau & Conveyor")
    parser.add_argument('--host', default='http://127.0.0.1:5000', help='Host server Flask (default: http://127.0.0.1:5000)')
    parser.add_argument('--interval', type=float, default=4.0, help='Interval pengiriman per detik (default: 4.0)')
    parser.add_argument('--burst', type=int, default=None, help='Kirim N data lalu berhenti (opsional)')
    parser.add_argument('--hazard', action='store_true', help='Simulasikan kondisi darurat / suhu tinggi')

    args = parser.parse_args()
    sim = TobaccoIoTSimulator(host=args.host, interval=args.interval, hazard_mode=args.hazard)
    sim.start(count=args.burst)

if __name__ == '__main__':
    main()
