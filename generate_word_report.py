import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    """Memberikan background warna pada sel tabel"""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Mengatur padding sel tabel"""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def create_report():
    doc = Document()

    # Page setup: A4, margin 2.54 cm (1 inch)
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Base styling
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    normal_style.paragraph_format.line_spacing = 1.18
    normal_style.paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # JUDUL DOKUMEN
    # -------------------------------------------------------------
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.add_run("DOKUMEN TEKNIS & PANDUAN SIDANG / UJIAN\nSISTEM CERDAS & PENGOLAHAN CITRA DIGITAL")
    title_run.font.name = 'Calibri'
    title_run.font.size = Pt(16)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0x11, 0x18, 0x27)

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = sub_p.add_run("Klasifikasi Mutu Daun Tembakau Konveyor Berbasis MobileNetV2 dan IoT Monitoring Gudang\n(TobaccoGuard Intelligent System)")
    sub_run.font.name = 'Calibri'
    sub_run.font.size = Pt(12)
    sub_run.font.italic = True
    sub_run.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

    # Garis pemisah
    doc.add_paragraph("―" * 55).alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Kata Pengantar Ringkas
    intro = doc.add_paragraph()
    intro_r = intro.add_run("Catatan untuk Mahasiswa: ")
    intro_r.bold = True
    intro.add_run(
        "Dokumen ini disusun menggunakan bahasa ilmiah yang runtut, tegas, dan mudah dipahami, "
        "serta dirancang khusus untuk menutup semua potensi 'celah pertanyaan kritis' yang biasa diuji oleh dosen penguji "
        "(seperti: alasan pemilihan dataset, penanganan data tidak seimbang, justifikasi arsitektur MobileNetV2 dibanding model lain, "
        "alasan metrik evaluasi F1-Score, dan integrasi end-to-end ke sistem IoT)."
    )

    # -------------------------------------------------------------
    # 1. DESKRIPSI DATASET SECARA RINCI
    # -------------------------------------------------------------
    h1 = doc.add_heading("1. Deskripsi Dataset dan Karakteristik Data", level=1)
    h1.runs[0].font.color.rgb = RGBColor(0x0F, 0x29, 0x4A)

    p1 = doc.add_paragraph(
        "Sistem cerdas ini menggunakan data berbasis penglihatan komputer (Computer Vision) "
        "untuk mengotomatisasi penyortiran mutu daun tembakau pada laju konveyor. "
        "Berikut adalah spesifikasi lengkap dataset yang digunakan:"
    )

    # Tabel Spesifikasi Dataset
    table1 = doc.add_table(rows=1, cols=2)
    table1.alignment = WD_TABLE_ALIGNMENT.CENTER
    table1.autofit = False

    hdr_cells = table1.rows[0].cells
    hdr_cells[0].text = "Parameter Data"
    hdr_cells[1].text = "Deskripsi Rinci Proyek"
    hdr_cells[0].paragraphs[0].runs[0].font.bold = True
    hdr_cells[1].paragraphs[0].runs[0].font.bold = True
    hdr_cells[0].paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    hdr_cells[1].paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    set_cell_background(hdr_cells[0], "1E3A8A")
    set_cell_background(hdr_cells[1], "1E3A8A")
    hdr_cells[0].width = Inches(2.2)
    hdr_cells[1].width = Inches(4.3)

    data_rows = [
        ("Jenis Data", "Citra Digital (RGB Image / Visual Data) berformat JPEG/PNG."),
        ("Sumber Dataset", "Dataset publik 'Tobacco Grader' yang diekspor melalui platform Roboflow Universe dengan anotasi terstandarisasi format CreateML JSON (_annotations.createml.json)."),
        ("Jumlah Sampel Awal", "1.436 citra daun tembakau asli yang terbagi ke dalam folder train, valid, dan test."),
        ("Jumlah Sampel Setelah Preprocessing & Augmentasi", "1.829 sampel teraugmentasi untuk pelatihan Deep Learning MobileNetV2 (Transfer Learning) dan AlexNet (CNN klasik dari nol)."),
        ("Pembagian Data (Splitting)", "Menggunakan metode Stratified Hold-out Splitting: 80% Data Latih (Train: 1.463 sampel) dan 20% Data Uji/Validasi (Validation: 366 sampel). Rasio tiap kelas dipertahankan identik."),
        ("Kelas Mutu yang Diklasifikasikan", "3 Kelas Mutu Standar Industri Cerutu Internasional:\n1. Low Quality / Filler (Label 0): Daun cacat, robek, atau berurat tebal kasar; diperuntukkan bagi tembakau rajangan/pengisi cerutu.\n2. Medium Quality / Binder (Label 1): Daun dengan elastisitas cukup dan urat sedang; dipakai sebagai pembungkus dalam/pengikat cerutu.\n3. High Quality / Wrapper (Label 2): Daun sempurna tanpa cacat, warna curing matang merata, urat daun sangat halus; dipakai sebagai pembungkus luar cerutu mutu ekspor."),
        ("Kondisi Ketidakseimbangan (Class Imbalance)", "Dataset mentah mengalami ketimpangan kelas yang signifikan (kelas Low Quality/Filler hanya memiliki ~29 sampel asli). Ketimpangan ini diselesaikan melalui Targeted Oversampling 8x dan Balanced Class Weights."),
        ("Resolusi & Dimensi Masukan", "Citra masukan mentah berukuran bervariasi dipotong (crop) pada area daun, kemudian di-resize ke 224 × 224 piksel dengan 3 kanal warna (RGB) dan dinormalisasi ke rentang nilai [0.0, 1.0].")
    ]

    for param, desc in data_rows:
        row_cells = table1.add_row().cells
        row_cells[0].text = param
        row_cells[1].text = desc
        row_cells[0].paragraphs[0].runs[0].font.bold = True
        row_cells[0].width = Inches(2.2)
        row_cells[1].width = Inches(4.3)
        set_cell_background(row_cells[0], "F3F4F6")
        set_cell_background(row_cells[1], "FAFAFA")
        set_cell_margins(row_cells[0], 80, 80, 100, 100)
        set_cell_margins(row_cells[1], 80, 80, 100, 100)

    # Embed Gambar Perbandingan Mutu Daun jika ada
    img_compare = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai", "reports", "quality_classes_comparison.png")
    if os.path.exists(img_compare):
        doc.add_paragraph().paragraph_format.space_before = Pt(6)
        p_img1 = doc.add_paragraph()
        p_img1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(img_compare, width=Inches(5.8))
        cap1 = doc.add_paragraph("Gambar 1. Perbandingan Karakteristik Visual Tiga Kelas Mutu Daun Tembakau (Wrapper, Binder, Filler)")
        cap1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap1.runs[0].font.size = Pt(9.5)
        cap1.runs[0].font.italic = True
        cap1.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    # Embed Gambar Pipeline Tahapan PCV
    img_pipe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai", "reports", "pipeline_stages.png")
    if os.path.exists(img_pipe):
        doc.add_paragraph().paragraph_format.space_before = Pt(6)
        p_img2 = doc.add_paragraph()
        p_img2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(img_pipe, width=Inches(5.8))
        cap2 = doc.add_paragraph("Gambar 2. Tahapan Alur Pengolahan Citra Digital (Raw -> Bounding Box -> ROI -> HSV -> Sobel -> Output AI)")
        cap2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap2.runs[0].font.size = Pt(9.5)
        cap2.runs[0].font.italic = True
        cap2.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    # Argumen Antisipasi Celah Dosen
    doc.add_paragraph().paragraph_format.space_before = Pt(8)
    callout1 = doc.add_paragraph()
    c1_run = callout1.add_run("💡 Kunci Jawaban Antisipasi Penguji (Dataset): ")
    c1_run.bold = True
    c1_run.font.color.rgb = RGBColor(0x92, 0x40, 0x0E)
    callout1.add_run(
        "Jika dosen bertanya 'Kenapa data kelas Low Quality cuma sedikit dan bagaimana mengatasinya?', "
        "jawablah: 'Secara operasional di lapangan, daun tembakau yang dipetik umumnya sudah melalui sortasi awal petani sehingga daun afkir/rusak memang lebih sedikit di alam. "
        "Untuk mencegah model bias terhadap kelas mayoritas, kami menerapkan dua lapis solusi ilmiah: (1) Targeted Data Augmentation sebanyak 8 kali lipat khusus pada kelas Low Quality berupa variasi rotasi acak, pembalikan horizontal/vertikal, dan simulasi fluktuasi pencahayaan, serta (2) Balanced Class Weights pada fungsi loss sehingga model memberikan sanksi penalti lebih berat jika keliru memprediksi kelas minoritas.'"
    )

    # -------------------------------------------------------------
    # 2. LIST MODEL UTAMA & DASAR ALASAN PEMILIHAN
    # -------------------------------------------------------------
    doc.add_page_break()
    h2 = doc.add_heading("2. Model Utama dan Dasar Alasan Pemilihan Algoritma", level=1)
    h2.runs[0].font.color.rgb = RGBColor(0x0F, 0x29, 0x4A)

    p2 = doc.add_paragraph(
        "Penelitian ini menerapkan studi perbandingan empiris antara dua generasi arsitektur Convolutional Neural Network (CNN) terkemuka: "
        "Arsitektur Modern Hemat Komputasi (MobileNetV2, 2018) sebagai Model Utama dan Arsitektur Klasik Pelopor Deep Learning (AlexNet, 2012) sebagai Model Pembanding. "
        "Perbandingan ini sangat esensial secara akademis untuk menguji apakah arsitektur modern berbasis Depthwise Separable Convolution "
        "benar-benar lebih optimal untuk diterapkan pada sistem konveyor industri real-time dibanding arsitektur CNN konvensional yang padat parameter."
    )

    doc.add_heading("A. Model Utama: MobileNetV2 (Modern Edge CNN - Transfer Learning)", level=2)
    doc.add_paragraph(
        "MobileNetV2 dirancang khusus oleh Google untuk perangkat edge, mobile, dan IoT dengan keterbatasan daya. "
        "Karakteristik dan keunggulannya dalam penelitian ini adalah:\n"
        "1. Depthwise Separable Convolution:\n"
        "   Menggantikan operasi konvolusi spasial standar 2D dengan dua tahap efisien: Depthwise Convolution (menyaring per-kanal) "
        "   dan Pointwise Convolution 1x1 (menggabungkan antar-kanal). Hasilnya, komputasi (FLOPs) berkurang hingga 8 - 9 kali lebih hemat.\n"
        "2. Inverted Residuals & Linear Bottlenecks:\n"
        "   Mempertahankan manifold fitur berdimensi rendah tanpa kehilangan informasi penting daun akibat aktivasi non-linier.\n"
        "3. Efisiensi Parameter & Kecepatan:\n"
        "   Hanya memiliki sekitar 2.42 juta parameter dengan ukuran berkas model 11.5 MB. "
        "   Dapat berjalan stabil di atas 30 FPS pada prosesor CPU laptop/edge tanpa memerlukan GPU industri terpisah.\n"
        "4. Kinerja Empiris:\n"
        "   Menghasilkan Akurasi Validasi 86.61% dan loss 0.3191."
    )

    doc.add_heading("B. Model Pembanding: AlexNet (Classical Deep CNN - Standard Convolutions)", level=2)
    doc.add_paragraph(
        "AlexNet (Krizhevsky et al., 2012) merupakan arsitektur pelopor kebangkitan Deep Learning modern. "
        "Model ini dihadirkan sebagai pembanding langsung berbobot setara (CNN vs CNN) dengan karakteristik:\n"
        "1. Arsitektur Konvolusi Standar Berfilter Besar:\n"
        "   AlexNet mengandalkan 5 lapisan konvolusi standar dengan kernel berukuran besar (11x11 pada Conv1, 5x5 pada Conv2, dan 3x3 pada Conv3-5) "
        "   disertai Max Pooling bertingkat (3x3, stride 2) dan Batch Normalization.\n"
        "2. Lapisan Fully Connected (Dense) yang Masif:\n"
        "   Memiliki dua lapisan Dense tersembunyi berukuran 1024 neuron dengan Dropout 50%. "
        "   Lapisan Dense ini saja menyumbang lebih dari 7.6 juta parameter.\n"
        "3. Karakteristik Beban Komputasi:\n"
        "   Total parameter mencapai 11.35 juta parameter (berukuran 43.3 MB) — hampir 5 kali lipat lebih besar dibanding MobileNetV2. "
        "   Beban komputasi yang tinggi menyebabkan latensi inferensi di CPU lebih lambat (~75 - 110 ms per frame), "
        "   sehingga kurang ideal untuk laju konveyor tembakau berkecepatan tinggi.\n"
        "4. Kinerja Empiris:\n"
        "   Menghasilkan Akurasi Validasi 75.00% dan loss 0.477 — jauh di bawah MobileNetV2 (86.61%), "
        "   yang membuktikan bahwa arsitektur modern dengan Transfer Learning unggul signifikan dibanding arsitektur klasik yang dilatih dari nol pada dataset berukuran kecil."
    )

    # Tabel Perbandingan Komprehensif MobileNetV2 vs AlexNet
    table2 = doc.add_table(rows=1, cols=3)
    table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    table2.autofit = False

    hdr2 = table2.rows[0].cells
    hdr2[0].text = "Parameter Komparasi"
    hdr2[1].text = "Model Utama: MobileNetV2 (2018)"
    hdr2[2].text = "Model Pembanding: AlexNet (2012)"
    for h in hdr2:
        h.paragraphs[0].runs[0].font.bold = True
        h.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(h, "1E3A8A")
    hdr2[0].width = Inches(2.0)
    hdr2[1].width = Inches(2.3)
    hdr2[2].width = Inches(2.2)

    comp_rows = [
        ("Kategori Arsitektur", "Modern Edge CNN (Inverted Residuals)", "Classical Deep CNN (Pioneer)"),
        ("Tipe Konvolusi", "Depthwise Separable (Depthwise + 1x1 Pointwise)", "Standard Spatial Conv (Filter 11x11, 5x5, 3x3)"),
        ("Jumlah Parameter", "2,422,147 parameter (~2.42 Juta)", "11,356,931 parameter (~11.35 Juta) [4.7x lebih besar]"),
        ("Ukuran Berkas Model", "11.5 MB (.h5)", "43.3 MB (.h5) [3.8x lebih berat]"),
        ("Kompleksitas FLOPs", "~300 MFLOPs (Sangat Hemat)", "~720 MFLOPs (Tinggi)"),
        ("Latensi Inferensi (CPU)", "~25 - 35 ms per daun (>30 FPS Real-time)", "~75 - 110 ms per daun (~10 - 13 FPS)"),
        ("Akurasi Validasi", "86.61% (Loss: 0.3191)", "75.00% (Loss: 0.4770)"),
        ("Kesesuaian di Konveyor IoT", "Sangat Direkomendasikan (Ringan, Tanpa GPU)", "Kurang Ideal (Latensi Tinggi di CPU Edge)")
    ]

    for c1, c2, c3 in comp_rows:
        r = table2.add_row().cells
        r[0].text = c1
        r[1].text = c2
        r[2].text = c3
        r[0].paragraphs[0].runs[0].font.bold = True
        r[0].width = Inches(2.0)
        r[1].width = Inches(2.3)
        r[2].width = Inches(2.2)
        set_cell_background(r[0], "F3F4F6")
        set_cell_background(r[1], "FAFAFA")
        set_cell_background(r[2], "FAFAFA")
        set_cell_margins(r[0], 60, 60, 80, 80)
        set_cell_margins(r[1], 60, 60, 80, 80)
        set_cell_margins(r[2], 60, 60, 80, 80)

    # -------------------------------------------------------------
    # 3. FRAMEWORKS & PERANGKAT TEKNOLOGI YANG DIGUNAKAN
    # -------------------------------------------------------------
    doc.add_page_break()
    h3 = doc.add_heading("3. Daftar Frameworks dan Perangkat Teknologi", level=1)
    h3.runs[0].font.color.rgb = RGBColor(0x0F, 0x29, 0x4A)

    doc.add_paragraph(
        "Seluruh ekosistem perangkat lunak dan keras dalam proyek ini saling terhubung secara modular:"
    )

    tech_list = [
        ("Bahasa Pemrograman", "Python 3.10+ (Backend, Algoritma AI, dan Simulasi) serta C++ Arduino (Firmware ESP32 dan Wemos D1 Mini)."),
        ("Library Deep Learning & ML", "TensorFlow 2.x & Keras (pembangunan arsitektur MobileNetV2 dan AlexNet), Scikit-Learn (komputasi bobot kelas, classification report), dan NumPy/Matplotlib (visualisasi evaluasi)."),
        ("Pengolahan Citra Digital (PCV)", "OpenCV (cv2) untuk akuisisi video stream webcam, panduan Guide Box, segmentasi HSV, dan filter tekstur Sobel; Pillow (PIL) untuk augmentasi dan manipulasi koordinat gambar; NumPy untuk operasi aljabar linier tensor piksel."),
        ("Backend & Web Service", "Flask (Microframework REST API), Flask-SQLAlchemy (Object Relational Mapping), Flask-CORS (Cross-Origin Resource Sharing), dan PyMySQL / SQLite sebagai engine penyimpan relasional."),
        ("Antarmuka Pengguna (Frontend)", "HTML5, Vanilla CSS dengan desain Taste-Skill (berkarakter Industrial Telemetry tanpa AI-slop), Bootstrap 5, dan Chart.js untuk visualisasi grafik tren lingkungan serta diagram donat mutu daun."),
        ("Hardware IoT & Sensor", "ESP32 DevKit (Sensor DHT22 untuk suhu/kelembapan, Sensor MQ-135 untuk kualitas gas, Relay 5V untuk aktivasi kipas, Buzzer alarm), Wemos D1 Mini (Sensor proximity konveyor), dan Kamera Webcam USB.")
    ]

    for cat, det in tech_list:
        p_t = doc.add_paragraph()
        r_cat = p_t.add_run(f"• {cat}: ")
        r_cat.bold = True
        p_t.add_run(det)

    # -------------------------------------------------------------
    # 4. CARA EVALUASI ALGORITMA & PENANGANAN OVERFITTING
    # -------------------------------------------------------------
    doc.add_page_break()
    h4 = doc.add_heading("4. Metodologi Evaluasi Algoritma dan Pencegahan Overfitting", level=1)
    h4.runs[0].font.color.rgb = RGBColor(0x0F, 0x29, 0x4A)

    doc.add_paragraph(
        "Untuk menjamin bahwa model yang dihasilkan tidak sekadar menghafal data (overfitting), "
        "evaluasi dilakukan secara komprehensif menggunakan metrik klasifikasi multi-kelas:"
    )

    eval_items = [
        ("Accuracy (Akurasi)", "Mengukur proporsi total prediksi yang tepat dibandingkan total data uji. Pada proyek ini, MobileNetV2 mencapai 86.61%."),
        ("Precision", "Mengukur ketepatan model saat memprediksi suatu kelas mutu daun tertentu. Mencegah terjadinya false positive (misalnya daun rusak tapi diprediksi sebagai daun mutu tinggi)."),
        ("Recall (Sensitivitas)", "Mengukur kemampuan model menemukan seluruh sampel dari kelas yang dicari. Sangat penting untuk kelas Filler (Low Quality) agar daun cacat tidak terlewat ke proses pengemasan."),
        ("F1-Score (Macro & Weighted)", "Rata-rata harmonik antara Precision dan Recall. Merupakan metrik paling objektif dalam mengevaluasi model pada dataset yang memiliki ketimpangan sampel."),
        ("Confusion Matrix", "Matriks kontingensi 3 × 3 yang memvisualisasikan korelasi antara label sebenarnya (Ground Truth) dan hasil prediksi model, mendeteksi di mana model mengalami kebingungan klasifikasi."),
        ("Categorical Crossentropy Loss", "Fungsi kerugian berbasis probabilitas yang dipantau setiap epoch untuk memastikan gradien model terus konvergen menuju nilai optimal.")
    ]

    for name, desc in eval_items:
        p_ev = doc.add_paragraph()
        r_ev = p_ev.add_run(f"• {name}: ")
        r_ev.bold = True
        p_ev.add_run(desc)

    doc.add_heading("Strategi Teknis Pencegahan Overfitting", level=2)
    doc.add_paragraph(
        "1. EarlyStopping Callback:\n"
        "   Pelatihan dipantau secara otomatis pada nilai validation loss (val_loss). "
        "   Jika dalam 4 epoch berurutan (patience=4) tidak ada penurunan error pada data validasi, proses training langsung dihentikan dan bobot terbaik (restore_best_weights=True) dikembalikan secara otomatis.\n"
        "2. Adaptive Learning Rate (ReduceLROnPlateau):\n"
        "   Jika model mengalami dataran belajar (stagnasi) selama 2 epoch, nilai learning rate diperkecil 50% (factor=0.5) hingga batas minimal 1e-5. "
        "   Langkah ini memungkinkan pengoptimal Adam menemukan celah minimum lokal secara lebih presisi.\n"
        "3. Dropout Regularization:\n"
        "   Memutuskan koneksi 30% neuron setelah layer pooling dan 20% neuron setelah layer dense selama training agar tidak terjadi ko-adaptasi berlebih antar neuron.\n"
        "4. Data Augmentation Berbasis Lingkungan Nyata:\n"
        "   Memberikan variasi acak rotasi sudut, pembalikan citra, fluktuasi brightness (±20%) dan contrast (±20%) "
        "   sehingga model tahan terhadap bayangan pekerja atau pantulan cahaya lampu di atas konveyor gudang."
    )

    # Embed Gambar Evaluasi Model & Confusion Matrix
    img_eval = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai", "reports", "model_evaluation.png")
    if os.path.exists(img_eval):
        doc.add_paragraph().paragraph_format.space_before = Pt(6)
        p_img3 = doc.add_paragraph()
        p_img3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(img_eval, width=Inches(5.8))
        cap3 = doc.add_paragraph("Gambar 3. Visualisasi Hasil Evaluasi Model: Confusion Matrix dan Kurva Loss/Akurasi Pelatihan MobileNetV2")
        cap3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap3.runs[0].font.size = Pt(9.5)
        cap3.runs[0].font.italic = True
        cap3.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    # -------------------------------------------------------------
    # 5. DIAGRAM ALUR END-TO-END (PIPELINE)
    # -------------------------------------------------------------
    doc.add_page_break()
    h5 = doc.add_heading("5. Diagram Alur End-to-End Sistem Cerdas dan Integrasi IoT", level=1)
    h5.runs[0].font.color.rgb = RGBColor(0x0F, 0x29, 0x4A)

    doc.add_paragraph(
        "Sistem bekerja secara terintegrasi penuh (End-to-End) mulai dari penyiapan data, pelatihan model, "
        "inferensi visual kamera, hingga penyimpanan database dan penyajian dashboard telemetri:"
    )

    # Langkah alur
    steps = [
        ("Tahap 1: Persiapan & Anotasi Data", "Dataset 1.436 citra Roboflow diparsing dari format CreateML JSON. Dilakukan pemotongan otomatis (ROI cropping) tepat pada batas daun untuk menghilangkan background konveyor."),
        ("Tahap 2: Augmentasi & Penyeimbangan", "Daun kelas Low Quality diperbanyak 8 kali lipat melalui teknik Targeted Oversampling dengan variasi posisi dan pencahayaan, menghasilkan 1.829 citra seimbang."),
        ("Tahap 3: Pemisahan Data (Data Splitting)", "Data diacak dan dibagi dengan metode Stratified Split menjadi 80% data latih dan 20% data validasi."),
        ("Tahap 4: Pelatihan Model (Training)", "Model MobileNetV2 dilatih dengan bobot kelas seimbang, pengoptimal Adam, callback EarlyStopping, dan Dropout regulasi."),
        ("Tahap 5: Serialisasi & Penyimpanan Model", "Model diekspor ke dalam format HDF5: ai/models/tobacco_model.h5 (MobileNetV2) dan ai/models/tobacco_alexnet.h5 (AlexNet) beserta berkas metadata JSON masing-masing."),
        ("Tahap 6: Inferensi Visual Real-Time (Webcam / Konveyor)", "Script ai/inference.py membaca video stream dari webcam, menempatkan Guide Box 300x300, melakukan resize 224x224, normalisasi 0-1, dan memprediksi mutu daun secara instan (dapat memilih model via argumen --model mobilenet atau --model alexnet)."),
        ("Tahap 7: Transmisi Data ke REST API", "Hasil prediksi (kelas daun, skor keyakinan / confidence, dan vektor fitur embedding) beserta berkas foto daun dikirim melalui HTTP POST multipart/form-data ke endpoint /api/conveyor."),
        ("Tahap 8: Pengolahan Backend & Database", "Server Flask menyimpan berkas gambar ke sistem direktori static/uploads/daun/YYYY/MM/DD/, sedangkan metadata dan path disimpan ke tabel SQLite/MySQL klasifikasi_daun."),
        ("Tahap 9: Pemantauan Dashboard Real-Time", "Dashboard web menampilkan statistik mutu daun, grafik donat Chart.js, histori log sortasi, dan foto bukti inferensi secara real-time tanpa refresh halaman.")
    ]

    for title, desc in steps:
        p_s = doc.add_paragraph()
        r_s = p_s.add_run(f"[{title}]\n")
        r_s.bold = True
        r_s.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
        p_s.add_run(desc)

    # -------------------------------------------------------------
    # 6. LAMPIRAN: PREDIKSI PERTANYAAN JEBAKAN DOSEN & CARA MENJAWAB
    # -------------------------------------------------------------
    doc.add_page_break()
    h6 = doc.add_heading("6. Lampiran: Prediksi Pertanyaan Kritis Dosen & Kunci Jawaban Ilmiah", level=1)
    h6.runs[0].font.color.rgb = RGBColor(0x0F, 0x29, 0x4A)

    doc.add_paragraph(
        "Gunakan panduan berikut saat menghadapi pertanyaan kritis atau 'jebakan' dari dosen penguji:"
    )

    faqs = [
        (
            "Tanya: 'Mengapa Anda membandingkan MobileNetV2 dengan AlexNet, dan apa perbedaan mendasar arsitekturnya?'",
            "Jawab: 'Perbandingan ini menyandingkan dua generasi arsitektur CNN: AlexNet (2012) sebagai representasi CNN klasik dengan Standard Convolution dan filter besar (11x11, 5x5), melawan MobileNetV2 (2018) sebagai representasi CNN modern hemat komputasi berbasis Depthwise Separable Convolution. AlexNet menghasilkan 11.35 juta parameter (43.3 MB) dan membutuhkan ~720 MFLOPs sehingga berat dijalankan di CPU edge. Sebaliknya, MobileNetV2 memisahkan konvolusi spasial dan kanal sehingga hanya membutuhkan 2.42 juta parameter (11.5 MB) dan ~300 MFLOPs. Ini membuktikan secara ilmiah mengapa MobileNetV2 jauh lebih layak untuk sistem konveyor real-time (latensi ~30 ms / >30 FPS) dibanding AlexNet.'"
        ),
        (
            "Tanya: 'Mengapa Anda menggunakan Transfer Learning pada MobileNetV2, bukan melatih CNN biasa dari nol (from scratch)?'",
            "Jawab: 'Melatih CNN dari nol membutuhkan jutaan citra agar bobot konvolusi dapat mengenali pola visual abstrak dengan stabil. Dataset daun tembakau yang kami miliki berjumlah sekitar 1.400 sampel, sehingga melatih dari nol sangat rawan overfitting (seperti yang dialami AlexNet yang dilatih from scratch). Dengan Transfer Learning, kami memanfaatkan fitur representasi visual dasar yang telah teruji dari ImageNet, lalu mengarahkan lapisan penutup (custom dense head) khusus untuk karakteristik mutu tembakau. Hasilnya jauh lebih konvergen dan stabil.'"
        ),
        (
            "Tanya: 'Kenapa Anda tidak hanya mengukur Akurasi saja dalam evaluasi?'",
            "Jawab: 'Karena pada kondisi dataset dengan ketimpangan kelas, akurasi dapat memberikan ilusi keberhasilan (Accuracy Paradox). Jika daun Wrapper berjumlah 80%, model yang menebak Wrapper terus-menerus tetap mendapat akurasi 80% meskipun gagal mengenali daun rusak. Oleh karena itu, kami wajib menggunakan Precision, Recall, Macro F1-Score, dan Confusion Matrix untuk menjamin bahwa model memiliki sensitivitas tinggi dalam mendeteksi kelas minoritas Low Quality/Filler.'"
        ),
        (
            "Tanya: 'Kenapa foto daun tidak disimpan langsung di dalam kolom Database (BLOB)?'",
            "Jawab: 'Menyimpan berkas citra berukuran 200 KB - 1 MB langsung di dalam database relasional sebagai binary BLOB adalah anti-pattern yang dapat menyebabkan ukuran database membengkak ratusan megabyte dalam waktu singkat, menurunkan performa indexing, dan memperlambat waktu query SQL. Solusi arsitektur terbaik kami adalah menyimpan berkas fisik ke direktori terstruktur filesystem (static/uploads/daun/YYYY/MM/DD/) dan hanya menyimpan path string serta vektor fitur numerik di database.'"
        )
    ]

    for q, a in faqs:
        p_faq = doc.add_paragraph()
        r_q = p_faq.add_run(f"{q}\n")
        r_q.bold = True
        r_q.font.color.rgb = RGBColor(0xB4, 0x53, 0x09)
        p_faq.add_run(a)
        p_faq.paragraph_format.space_after = Pt(8)

    # Simpan berkas dokumen
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Laporan_Sistem_Cerdas_MobileNetV2_vs_AlexNet.docx")
    doc.save(output_path)
    print(f"[SUCCESS] Berkas Word berhasil dibuat di: {output_path}")

if __name__ == '__main__':
    create_report()
