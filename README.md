# Sistem Monitoring IoT Gudang Tembakau & Klasifikasi Daun Conveyor

Aplikasi web backend & dashboard terpadu berbasis **Flask**, **SQLite**, **Bootstrap 5**, dan **Chart.js** untuk memonitor kondisi lingkungan gudang tembakau (ESP32) dan hasil klasifikasi kualitas mutu daun pada conveyor (Wemos).

---

## 📁 Struktur Folder Project

```text
Tobacco/
├── run.bat                    # Launcher praktis 1-klik (Server + Simulator + Browser)
├── app.py                     # Entry point Flask & registrasi blueprint / error handlers
├── config.py                  # Konfigurasi database & batas ambang (thresholds) sensor
├── requirements.txt           # Dependensi Python (Flask, SQLAlchemy, CORS, Pandas, Openpyxl)
├── seed_data.py               # Script generator data simulasi awal (24 jam terakhir)
├── simulator.py               # Simulator Real-time IoT telemetri fluktuatif & conveyor
├── test_api.py                # Script pengujian & simulator ESP32 & Wemos
├── firmware/                  # Source code firmware mikrokontroler C++ (Arduino IDE)
│   ├── README.md              # Skema rangkaian (wiring) & tabel pinout hardware
│   ├── esp32_gudang/          # Node Monitoring Gudang (DHT22, MQ-135, Relay, Buzzer)
│   └── wemos_conveyor/        # Node Klasifikasi Daun Conveyor (IR Proximity Sensor)
├── ai/                        # ⚙️ Modul AI Klasifikasi Daun (diisi setelah dataset tersedia)
│   ├── requirements.txt       # Dependensi AI: tensorflow, opencv, scikit-learn, dll.
│   ├── train.py               # [PLACEHOLDER] Script training model klasifikasi daun
│   ├── inference.py           # [PLACEHOLDER] Script inferensi & integrasi ke /api/conveyor
│   ├── dataset/               # Folder untuk dataset gambar dari Roboflow (diisi manual)
│   └── models/                # Folder output model hasil training (.h5, .tflite)
├── models/
│   ├── __init__.py            # Inisialisasi SQLAlchemy db
│   ├── gudang.py              # Model tabel 'monitoring_gudang'
│   └── klasifikasi.py         # Model tabel 'klasifikasi_daun'
├── routes/
│   ├── __init__.py
│   ├── views.py               # Rute halaman web (Dashboard & Export)
│   ├── api_gudang.py          # REST API ESP32 (/api/gudang)
│   ├── api_conveyor.py        # REST API Wemos Conveyor (/api/conveyor)
│   └── api_export.py          # API Export Excel (.xlsx) & CSV (.csv)
├── database/
│   └── tobacco_monitoring.db  # Database SQLite (auto-generate)
├── templates/
│   ├── base.html              # Layout utama, navbar, audio alert chime, theme toggle
│   ├── dashboard.html         # Halaman dashboard real-time & grafik
│   └── export.html            # Halaman terpisah untuk ekspor data & pratinjau
└── static/
    ├── css/
    │   └── style.css          # Styling kustom, palet warna tembakau, animasi fan & dark mode
    └── js/
        ├── dashboard.js       # Auto-refresh (5s), Chart.js (Line & Donut), alarm alert
        └── export.js          # Logika filter tanggal, preview data, & unduh berkas
```

---

## 🗄️ Spesifikasi Database SQLite

### 1. Tabel `monitoring_gudang` (Data ESP32)
| Kolom | Tipe Data | Keterangan |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Auto increment ID |
| `suhu` | FLOAT | Nilai temperatur ruang gudang (°C) |
| `kelembapan` | FLOAT | Kelembapan relatif udara (RH %) |
| `gas` | INTEGER | Konsentrasi gas terdeteksi (ppm) |
| `status_fan` | BOOLEAN | Status kipas sirkulasi (`true` = ON, `false` = OFF) |
| `status_alarm` | BOOLEAN | Status alarm darurat (`true` = AKTIF, `false` = AMAN) |
| `timestamp` | DATETIME | Waktu perekaman data (UTC / ISO 8601) |

### 2. Tabel `klasifikasi_daun` (Data Wemos Conveyor)
| Kolom | Tipe Data | Keterangan |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Auto increment ID |
| `hasil_klasifikasi` | VARCHAR(50) | Kategori daun: `wrapper`, `binder`, atau `filler` |
| `confidence_score` | FLOAT | Nilai keyakinan model AI (0.0000 - 1.0000) |
| `timestamp` | DATETIME | Waktu deteksi daun pada conveyor |

---

## 🌐 Dokumentasi API Endpoints

Format respon konsisten:
```json
{
  "success": true,
  "data": { ... },
  "message": "Deskripsi respon"
}
```

### 1. Monitoring Gudang (ESP32)

#### `POST /api/gudang`
Menerima kiriman data telemetri dari mikrokontroler ESP32.
- **Headers:** `Content-Type: application/json`
- **Body JSON:**
  ```json
  {
    "suhu": 26.5,
    "kelembapan": 64.2,
    "gas": 85,
    "status_fan": true,
    "status_alarm": false
  }
  ```
- **Respon Sukses (201 Created):**
  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "suhu": 26.5,
      "kelembapan": 64.2,
      "gas": 85,
      "status_fan": true,
      "status_alarm": false,
      "timestamp": "2026-10-02T09:11:08.128708",
      "timestamp_display": "2026-10-02 09:11:08",
      "status_eval": {
        "suhu": "normal",
        "kelembapan": "normal",
        "gas": "normal",
        "overall": "normal"
      }
    },
    "message": "Data monitoring gudang berhasil disimpan"
  }
  ```

#### `GET /api/gudang/latest`
Mengambil data sensor gudang paling mutakhir.

#### `GET /api/gudang/history`
Mengambil histori data sensor untuk grafik dan log.
- **Query Params:**
  - `limit`: Jumlah data maksimal (default `50`)
  - `order`: `asc` (untuk grafik berurutan) atau `desc` (default `asc`)
  - `start_date`: Filter tanggal mulai (format `YYYY-MM-DD`)
  - `end_date`: Filter tanggal selesai (format `YYYY-MM-DD`)

---

### 2. Klasifikasi Daun Conveyor (Wemos)

#### `POST /api/conveyor`
Menerima hasil klasifikasi daun tembakau dari Wemos.
- **Headers:** `Content-Type: application/json`
- **Body JSON:**
  ```json
  {
    "hasil_klasifikasi": "wrapper",
    "confidence_score": 0.954
  }
  ```
- **Kategori valid:** `wrapper` (daun luar), `binder` (daun pengikat), `filler` (daun isi).

#### `GET /api/conveyor/latest`
Mengambil data daun terakhir yang terdeteksi.

#### `GET /api/conveyor/stats`
Mengambil akumulasi statistik total daun dan rincian per kategori.
- **Respon (200 OK):**
  ```json
  {
    "success": true,
    "data": {
      "total": 63,
      "wrapper": 25,
      "binder": 19,
      "filler": 19,
      "percentages": {
        "wrapper": 39.68,
        "binder": 30.16,
        "filler": 30.16
      },
      "avg_confidence": 0.9287,
      "avg_confidence_percent": 92.87
    },
    "message": "Statistik klasifikasi daun berhasil diambil"
  }
  ```

#### `GET /api/conveyor/history`
Mengambil riwayat klasifikasi conveyor dengan dukungan filter tanggal.

---

### 3. Ekspor Data Laporan (Excel & CSV)

- **`GET /api/export/gudang?format=excel|csv&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`**
- **`GET /api/export/conveyor?format=excel|csv&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`**

---

## 🚀 Panduan Menjalankan

### Cara Paling Cepat (1-Klik via Launcher):
Cukup jalankan file batch:
```cmd
run.bat
```
Pilih opsi **[3] Jalankan SERVER + SIMULATOR Sekaligus**. Web browser akan terbuka secara otomatis di `http://localhost:5000` dan simulator langsung aktif mengirimkan data telemetri.

---

### Cara Manual via Terminal:

#### 1. Install Dependensi
```bash
pip install -r requirements.txt
```

#### 2. Isi Data Awal Simulasi (Opsional)
```bash
python seed_data.py
```

#### 3. Jalankan Server Flask
```bash
python app.py
```
Akses web dashboard di peramban: **`http://localhost:5000`**

#### 4. Menjalankan Simulator Real-time IoT
Jalankan simulator pengiriman data ESP32 & Wemos secara langsung:
```bash
python simulator.py
```
*Atau opsi parameter tambahan:*
- `python simulator.py --interval 2` (interval lebih cepat tiap 2 detik)
- `python simulator.py --hazard` (simulasi kondisi darurat / suhu tinggi & gas)

---

## 🎨 Fitur Dashboard

1. **Auto-refresh Real-time (Tiap 5 Detik)**: Dashboard otomatis mengambil data terkini via Fetch API tanpa me-reload halaman browser.
2. **Indikator Warna Ambang Batas (Threshold)**:
   - 🟢 **Hijau (Normal)**: Suhu 20°-28°C, Kelembapan 60-70%, Gas < 150 ppm.
   - 🟡 **Kuning (Warning)**: Suhu 28°-32°C atau 16°-20°C, Kelembapan 50-60% atau 70-75%, Gas 150-300 ppm.
   - 🔴 **Merah (Bahaya)**: Suhu > 32°C, Kelembapan < 50% / > 75%, Gas > 300 ppm, atau `status_alarm = true`.
3. **Grafik Interaktif (Chart.js)**:
   - Line Chart dual-axis (Suhu °C & Kelembapan %)
   - Donut Chart distribusi Wrapper, Binder, Filler
4. **Notifikasi Alarm & Suara Chime Web Audio**:
   - Jika `status_alarm = true`, banner darurat merah menyala dan suara peringatan berbunyi otomatis.
   - Terintegrasi dengan Web Browser Native Notification.
5. **Halaman Terpisah Export Data**:
   - Filter tanggal dengan tombol cepat (Hari Ini, 7 Hari, 30 Hari, Semua).
   - Fitur Pratinjau (Preview) tabel data sebelum mengunduh.
   - Unduh langsung format `.xlsx` (Excel) dan `.csv`.
6. **Dark Mode Toggle**: Tombol mode gelap dengan penyimpanan status di `localStorage`.

---

## 🤖 Modul AI Klasifikasi Daun Tembakau (Coming Soon)

> **Catatan:** Folder `/ai/` telah disiapkan sebagai kerangka (*placeholder*) untuk sistem klasifikasi cerdas berbasis Computer Vision. Script training dan inference **belum diaktifkan** karena dataset gambar daun tembakau belum tersedia. Folder ini akan diisi setelah dataset dimasukkan secara manual oleh pengguna.

### Rencana Arsitektur AI
- **Framework**: TensorFlow / Keras
- **Metode**: Transfer Learning (MobileNetV2 / EfficientNetB0)
- **Kelas Target**: `wrapper` (pembungkus luar), `binder` (pengikat), `filler` (pengisi)
- **Sumber Dataset**: Roboflow (download manual → simpan ke `ai/dataset/`)

### Langkah Aktivasi (Setelah Dataset Tersedia)
```bash
# 1. Masukkan dataset ke dalam folder
#    ai/dataset/train/wrapper/, ai/dataset/train/binder/, ai/dataset/train/filler/
#    ai/dataset/valid/wrapper/, ai/dataset/valid/binder/, ai/dataset/valid/filler/

# 2. Install dependensi AI
pip install -r ai/requirements.txt

# 3. Jalankan training
python ai/train.py

# 4. Jalankan inferensi (setelah model tersimpan di ai/models/)
python ai/inference.py --image path/ke/gambar_daun.jpg
```

### Format Integrasi ke Backend (Endpoint Terverifikasi)
Endpoint `POST /api/conveyor` sudah siap menerima hasil inferensi AI dengan format:
```json
{
  "hasil_klasifikasi": "wrapper",
  "confidence_score": 0.9543
}
```
**Respon Sukses (HTTP 201):**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "hasil_klasifikasi": "wrapper",
    "confidence_score": 0.9543,
    "confidence_percent": 95.43,
    "timestamp": "2026-10-02T13:28:16.056583"
  },
  "message": "Data klasifikasi daun berhasil disimpan"
}
```
