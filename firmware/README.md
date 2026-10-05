# 🔌 Panduan Hardware & Firmware Mikrokontroler

Dokumentasi skema rangkaian kabel (wiring), konfigurasi pinout, dan panduan upload firmware Arduino untuk node sensor ESP32 dan node conveyor Wemos D1 Mini.

---

## 1. Node 1: Monitoring Gudang Tembakau (ESP32)

### A. Tabel Koneksi Pinout (Wiring Table)

| Komponen | Pin Komponen | Pin ESP32 DevKit | Keterangan & Rangkaian |
|---|---|---|---|
| **DHT22** (Suhu & RH) | VCC | 3.3V / 5V | Sumber daya sensor |
| | GND | GND | Ground bersama |
| | DATA | **GPIO 4** | Pasang pull-up resistor 10kΩ ke 3.3V jika modul tanpa resistor bawaan |
| **MQ-135** (Gas Quality) | VCC | 5V (VIN) | Sensor gas membutuhkan daya 5V untuk pemanas heater |
| | GND | GND | Ground bersama |
| | A0 (Analog Out) | **GPIO 34** | Terhubung ke pin ADC1_CH6 ESP32 (input only) |
| | D0 | *Tidak terhubung* | Output digital tidak dipakai |
| **Relay Module** (Kipas) | VCC | 5V (VIN) | Daya coil relay |
| | GND | GND | Ground bersama |
| | IN | **GPIO 18** | Kontrol switching relay (Active LOW) |
| | COM & NO | Ke Motor Kipas / Adaptor 12V | Memutus/menyambung jalur fase kipas angin |
| **Buzzer Aktif** (Alarm) | Positif (+) | **GPIO 19** | Bunyi saat kondisi darurat |
| | Negatif (-) | GND | Ground |
| **Built-in LED** | Internal | **GPIO 2** | Indikator status koneksi WiFi |

### B. Library yang Diperlukan (Arduino IDE)
1. Buka Arduino IDE -> **Tools** -> **Manage Libraries...**
2. Cari dan install:
   - **DHT sensor library** oleh *Adafruit*
   - **Adafruit Unified Sensor** oleh *Adafruit*
   - **ArduinoJson** oleh *Benoit Blanchon* (versi 6.x atau 7.x)

### C. Langkah Konfigurasi & Upload
1. Buka file `firmware/esp32_gudang/esp32_gudang.ino`.
2. Ubah `WIFI_SSID` dan `WIFI_PASSWORD` sesuai jaringan WiFi Anda.
3. Ubah `SERVER_URL` dengan alamat IP komputer server Anda (contoh: `http://192.168.1.8:5000/api/gudang`).
4. Pilih Board: **ESP32 Dev Module** pada port COM yang sesuai.
5. Klik tombol **Upload**. Buka Serial Monitor pada baud rate `115200` untuk memantau data telemetri.

---

## 2. Node 2: Klasifikasi Daun Conveyor (Wemos D1 Mini / ESP8266)

### A. Tabel Koneksi Pinout (Wiring Table)

| Komponen | Pin Komponen | Pin Wemos D1 Mini | Keterangan |
|---|---|---|---|
| **Sensor IR Proximity** | VCC | 5V / 3.3V | Daya sensor inframerah penghalang |
| | GND | G (GND) | Ground bersama |
| | OUT | **D5 (GPIO 14)** | Sinyal deteksi saat daun melintas (Active LOW) |
| **Built-in LED** | Internal | **D4 (GPIO 2)** | Kedip konfirmasi saat daun terdeteksi |

> **Catatan untuk ESP32 (Opsional):** Jika Anda menggunakan ESP32 untuk node conveyor alih-alih Wemos D1 Mini, sambungkan Pin OUT sensor ke **GPIO 14**.

### B. Library yang Diperlukan
- **ArduinoJson** oleh *Benoit Blanchon*
- Board package **esp8266** oleh *ESP8266 Community*

### C. Langkah Konfigurasi & Upload
1. Buka file `firmware/wemos_conveyor/wemos_conveyor.ino`.
2. Atur SSID, Password WiFi, dan `SERVER_URL` (`http://<IP_KOMPUTER>:5000/api/conveyor`).
3. Pilih Board: **LOLIN(WEMOS) D1 R2 & mini**.
4. Upload firmware dan pantau deteksi daun pada Serial Monitor (Baud: `115200`).

---

## 3. Alur Komunikasi Sistem

```text
[ Sensor DHT22 + MQ-135 ] ---> (ESP32) ---> [ WiFi HTTP POST ] ---> [ /api/gudang ] ---> [ SQLite DB ]
                                                                                           |
[ Sensor Proximity/IR ]  ---> (Wemos) ---> [ WiFi HTTP POST ] ---> [ /api/conveyor ] ----+
                                                                                           |
                                                                                           v
                                                                             [ Web Dashboard (Flask) ]
                                                                             - Real-time Chart.js
                                                                             - Auto-refresh 5s
                                                                             - Audio Alert & Export
```
