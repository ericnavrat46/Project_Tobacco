# 🍃 TobaccoGuard AI — Sistem Cerdas Pemantauan & Klasifikasi Mutu Daun Tembakau

Sistem cerdas berbasis **Deep Learning (Transfer Learning MobileNetV2)** yang terintegrasi dengan perangkat konveyor berjalan (IoT) dan web monitoring Flask untuk mengklasifikasi mutu daun tembakau menjadi 3 kelas: **Filler (Low)**, **Binder (Medium)**, dan **Wrapper (High)** secara real-time.

---

## 📁 Struktur Direktori Proyek

```
Tobacco/
├── app.py                          # Entry point aplikasi web Flask
├── config.py                       # Konfigurasi database & environment aplikasi
├── requirements.txt                # Dependensi Python utama
├── run.bat / run.ps1               # Script eksekusi aplikasi
├── .env / .env.example             # Konfigurasi environment variables
├── .gitignore                      # Berkas filter commit Git
│
├── data/                           # 📦 Dataset Daun Tembakau (Format Roboflow)
│   ├── train/                      #   Data latih (651 gambar + _classes.csv)
│   ├── valid/                      #   Data validasi (59 gambar + _classes.csv)
│   └── test/                       #   Data uji independen (34 gambar + _classes.csv)
│
├── ai/                             # 🤖 Pipeline Kecerdasan Buatan (Deep Learning)
│   ├── models/                     #   Model tersimpan (.keras) & metadata (.json)
│   │   ├── tobacco_model.keras     #     Model produksi utama (MobileNetV2)
│   │   ├── tobacco_model_mobilenet_cmp.keras # Model evaluasi MobileNetV2
│   │   └── tobacco_model_alexnet_cmp.keras   # Model evaluasi AlexNet
│   ├── outputs/                    #   Hasil laporan metrik & evaluasi (.json)
│   ├── reports/                    #   Grafik hasil evaluasi & confusion matrix (.png)
│   ├── train.py                    #   Pelatihan model produksi utama (MobileNetV2)
│   ├── train_comparison.py         #   Pelatihan komparasi: MobileNetV2 vs AlexNet
│   ├── inference.py                #   Skrip pengujian inferensi kamera & gambar
│   ├── visualize_pipeline.py       #   Generator visualisasi pengolahan citra
│   ├── generate_samples_grid.py    #   Generator sampel visual 3 kelas mutu daun
│   └── generate_comparison_charts.py # Generator diagram perbandingan arsitektur
│
├── models/                         # 🗄️ ORM Database (Flask-SQLAlchemy)
│   ├── gudang.py                   #   Model tabel sensor gudang (suhu, kelembapan)
│   ├── klasifikasi.py              #   Model tabel histori klasifikasi & conveyor
│   └── settings.py                 #   Model tabel pengaturan sistem & threshold
│
├── routes/                         # 🌐 Endpoint REST API & Routing Web
│   ├── views.py                    #   Routing halaman antarmuka pengguna (UI)
│   ├── api_conveyor.py             #   API deteksi daun & kontrol konveyor
│   ├── api_gudang.py               #   API monitoring kondisi suhu/kelembapan gudang
│   ├── api_export.py               #   API ekspor laporan (CSV, Excel)
│   ├── api_settings.py             #   API konfigurasi & ambang batas
│   └── api_chatbot.py              #   API chatbot konsultasi tembakau
│
├── templates/                      # 📄 Antarmuka Web (HTML Jinja2)
│   ├── base.html                   #   Layout master & navigasi
│   ├── dashboard.html              #   Dashboard ringkasan metrik & statistik
│   ├── klasifikasi.html            #   Live scanner kamera & drag-and-drop klasifikasi
│   ├── settings.html               #   Panel pengaturan sistem
│   └── export.html                 #   Halaman unduh data laporan
│
├── static/                         # 🎨 File Statis Web
│   ├── css/                        #   Stylesheet tampilan
│   ├── js/                         #   Logika frontend antarmuka
│   ├── images/                     #   Aset logo & ikon
│   └── uploads/                    #   Penyimpanan berkas foto daun yang diuji
│
├── database/                       # 💾 Basis Data
│   └── tobacco_monitoring.db       #   File database SQLite
│
├── firmware/                       # ⚡ Kode Mikrokontroler IoT
│   ├── esp32_gudang/               #   Firmware ESP32 (Sensor DHT22 suhu/kelembapan)
│   └── wemos_conveyor/             #   Firmware Wemos D1 Mini (Motor konveyor & servo)
│
├── scripts/                        # 🔧 Skrip Utilitas Pendukung
│   ├── seed_data.py                #   Pengisi data awal database (seeder)
│   ├── test_api.py                 #   Automated unit test endpoint REST API
│   ├── simulator.py                #   Simulator konveyor & stream data
│   ├── generate_laporan_word.py    #   Generator laporan skripsi Word (.docx)
│   └── generate_word_report.py     #   Generator report dokumentasi (.docx)
│
└── docs/                           # 📚 Berkas Dokumentasi & Laporan
    ├── Laporan_Sistem_Cerdas_*.docx#   Naskah laporan ilmiah
    └── TobaccoGuard_Postman_Collection.json # Koleksi pengujian Postman
```

---

## 🤖 Perbedaan Skrip Pelatihan (Training Scripts)

Dalam direktori `ai/`, terdapat 2 skrip pelatihan resmi dengan fungsi spesifik:

1. **`ai/train.py` (Model Utama Produksi)**
   * **Tujuan:** Melatih model utama (`ai/models/tobacco_model.keras`) yang digunakan langsung oleh aplikasi web dan sistem konveyor.
   * **Arsitektur:** MobileNetV2 dengan Transfer Learning 2 Tahap (Feature Extraction + Fine-Tuning 30 layer teratas).
   * **Fitur:** Dilengkapi augmentasi robust, ekspor metadata JSON, dan konversi format model.

2. **`ai/train_comparison.py` (Eksperimen Komparasi Ilmiah)**
   * **Tujuan:** Melatih dua arsitektur sekaligus secara komparatif untuk keperluan laporan/skripsi: **MobileNetV2** vs **AlexNet Murni (Arsitektur Asli 2012)**.
   * **Metodologi:** Kedua model diuji menggunakan protokol transfer learning 2 tahap, dataset yang sama persis, dan *early stopping*.
   * **Output:** Menghasilkan grafik komparasi kurva akurasi/loss, matriks kebingungan (dual confusion matrix), serta metrik perbandingan (`ai/reports/perbandingan_transfer_learning_mobilenet_vs_alexnet.png` dan `ai/outputs/comparison_results_alexnet.json`).

*(Catatan: File `train_alexnet.py` sebelumnya telah dihapus karena fungsinya sudah disatukan secara rapi ke dalam `train_comparison.py`)*.

---

## 📊 Hasil Komparasi Performa Model

Berdasarkan pengujian pada data validasi dan testing independen:

| Parameter Evaluasi | MobileNetV2 (Transfer Learning) | AlexNet Murni (Arsitektur Asli 2012) | Keterangan / Keunggulan |
| :--- | :---: | :---: | :--- |
| **Akurasi Validasi** | **100.00%** | **72.88%** | MobileNetV2 unggul telak (+27.12%) |
| **Akurasi Data Uji (Test)** | **100.00%** | **79.41%** | 34 sampel uji terprediksi sempurna |
| **Macro F1-Score** | **1.000** | **0.653** | Seimbang di seluruh kelas mutu |
| **Jumlah Parameter** | **2.42 Juta** (~9.3 MB) | **11.36 Juta** (~43.3 MB) | MobileNetV2 **4.7x lebih ringan** |
| **Kecepatan Inferensi** | **< 30 ms** (Real-time) | ~70 ms | Optimal untuk integrasi konveyor |

---

## 🚀 Panduan Menjalankan Sistem

### 1. Menjalankan Aplikasi Web
```bash
# Menjalankan server Flask
python app.py
```
Akses sistem monitoring melalui browser di: `http://localhost:5000`

### 2. Menjalankan Pelatihan Ulang Model
```bash
# Melatih model produksi utama:
python ai/train.py

# Melatih dan menghasilkan grafik komparasi (MobileNetV2 vs AlexNet):
python ai/train_comparison.py
```

### 3. Menjalankan Uji Inferensi (Kamera / Gambar)
```bash
# Uji inferensi pada satu berkas gambar:
python ai/inference.py --image path/ke/gambar.jpg

# Uji inferensi live menggunakan kamera / webcam:
python ai/inference.py --camera 0
```
