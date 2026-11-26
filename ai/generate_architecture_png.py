import os
import sys

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Konfigurasi Path Output
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'reports')
os.makedirs(OUTPUT_DIR, exist_ok=True)
PNG_OUTPUT = os.path.join(OUTPUT_DIR, 'model_architecture.png')

# Setup Figure (Ukuran proporsional & resolusi tajam)
fig, ax = plt.subplots(figsize=(16, 17), dpi=300)
fig.patch.set_facecolor('#0b1120') # Deep dark slate
ax.set_facecolor('#0b1120')
ax.axis('off')

# Header Title & Subtitle
plt.text(0.5, 0.975, "ARSITEKTUR DETAIL MODEL KLASIFIKASI MUTU TEMBAKAU", 
         ha='center', va='center', fontsize=19, fontweight='bold', color='#f8fafc', fontfamily='sans-serif')
plt.text(0.5, 0.952, "TobaccoGuard AI  |  Framework: TensorFlow / Keras  |  Struktur Layer MobileNetV2 + Custom Head", 
         ha='center', va='center', fontsize=11.5, color='#94a3b8', fontfamily='sans-serif')

# Definisi Semua Layer / Komponen Kunci Sesuai Permintaan:
# Input -> Conv2D -> Batch Normalization -> ReLU -> Inverted Residual Bottleneck -> Top Head
blocks = [
    {
        "badge": "1. INPUT LAYER",
        "title": "Input Layer (Citra RGB)",
        "sub": "Menerima citra daun tembakau berdimensi (224 x 224 x 3) dalam skala nilai ternormalisasi [0, 1].",
        "shape": "Output: (Batch, 224, 224, 3)\nParams: 0",
        "color": "#0f172a",
        "border": "#38bdf8",
        "badge_bg": "#0284c7"
    },
    {
        "badge": "2. INITIAL CONV",
        "title": "Conv2D (Standard Convolution)",
        "sub": "Ekstraksi fitur spasial awal dengan 32 filter berukuran (3x3), stride=2, dan padding='same'.",
        "shape": "Output: (Batch, 112, 112, 32)\nParams: 864",
        "color": "#172554",
        "border": "#60a5fa",
        "badge_bg": "#2563eb"
    },
    {
        "badge": "3. NORMALIZATION",
        "title": "Batch Normalization (bn_Conv1)",
        "sub": "Menstabilkan distribusi aktivasi (mean & variance), mempercepat konvergensi, dan regularisasi gradien.",
        "shape": "Output: (Batch, 112, 112, 32)\nParams: 128 (64 Trainable)",
        "color": "#1e1b4b",
        "border": "#818cf8",
        "badge_bg": "#4f46e5"
    },
    {
        "badge": "4. ACTIVATION",
        "title": "ReLU6 Activation (Conv1_relu)",
        "sub": "Fungsi aktivasi f(x) = min(max(x, 0), 6) untuk membatasi rentang nilai agar tahan pada komputasi presisi rendah.",
        "shape": "Output: (Batch, 112, 112, 32)\nParams: 0",
        "color": "#2e1065",
        "border": "#c084fc",
        "badge_bg": "#9333ea"
    },
    {
        "badge": "5. BOTTLENECK BLOCKS",
        "title": "17 Inverted Residual & Linear Bottleneck Blocks",
        "sub": "Struktur Utama MobileNetV2:\n"
               "• 1x1 Conv (Expand Channel) + Batch Normalization + ReLU6\n"
               "• 3x3 Depthwise Conv (Spatial Feature Filter) + BN + ReLU6\n"
               "• 1x1 Linear Projection (Compress Channel) + BN (Tanpa aktivasi non-linear)\n"
               "• Residual Skip Connection (pada stride=1 & channel sama) untuk aliran gradien optimal.",
        "shape": "Output Akhir: (Batch, 7, 7, 1280)\nTotal Backbone Params: ~2.26M",
        "color": "#1c1917",
        "border": "#f59e0b",
        "badge_bg": "#d97706"
    },
    {
        "badge": "6. POOLING",
        "title": "Global Average Pooling 2D",
        "sub": "Meringkas feature map spasial (7x7) menjadi 1 nilai rata-rata per channel sehingga menghasilkan vektor fitur 1D.",
        "shape": "Output: (Batch, 1280)\nParams: 0",
        "color": "#064e3b",
        "border": "#34d399",
        "badge_bg": "#059669"
    },
    {
        "badge": "7. REGULARIZATION",
        "title": "Batch Normalization & Dropout (0.3)",
        "sub": "Normalisasi kembali representasi fitur 1280 dimensi dan menonaktifkan acak 30% koneksi neuron untuk cegah overfitting.",
        "shape": "Output: (Batch, 1280)\nParams: 5,120 (2,560 Trainable)",
        "color": "#14532d",
        "border": "#4ade80",
        "badge_bg": "#16a34a"
    },
    {
        "badge": "8. DENSE HEAD",
        "title": "Dense (128 Units, ReLU) & Dropout (0.2)",
        "sub": "Fully Connected Layer untuk interpretasi mutu tembakau + Dropout 20% sebelum lapisan keputusan klasifikasi.",
        "shape": "Output: (Batch, 128)\nParams: 163,968",
        "color": "#4c0519",
        "border": "#fb7185",
        "badge_bg": "#e11d48"
    },
    {
        "badge": "9. CLASSIFIER OUTPUT",
        "title": "Output Dense (3 Units, Softmax)",
        "sub": "Menghasilkan distribusi probabilitas mutu daun tembakau:\n"
               "• Kelas 0 : FILLER (Low Quality)  |  Kelas 1 : BINDER (Medium Quality)  |  Kelas 2 : WRAPPER (High Quality)",
        "shape": "Output: (Batch, 3)\nParams: 387",
        "color": "#064e3b",
        "border": "#10b981",
        "badge_bg": "#10b981"
    }
]

y_start = 0.905
box_height = 0.063
box_height_bottleneck = 0.105 # Kotak bottleneck dibuat lebih tinggi karena memuat penjelasan mendalam
spacing = 0.025
x_start = 0.08
box_width = 0.84

cur_y = y_start
for i, block in enumerate(blocks):
    h = box_height_bottleneck if i == 4 else box_height
    y = cur_y - h
    
    # Draw Fancy Box
    rect = patches.FancyBboxPatch(
        (x_start, y), box_width, h,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        facecolor=block["color"],
        edgecolor=block["border"],
        linewidth=2,
        zorder=2
    )
    ax.add_patch(rect)
    
    # Badge (Category)
    ax.text(x_start + 0.02, y + h - 0.016, block["badge"], 
            fontsize=8.5, fontweight='bold', color='#ffffff',
            bbox=dict(facecolor=block["badge_bg"], edgecolor=block["border"], boxstyle='round,pad=0.25', linewidth=1),
            va='center')

    # Title
    ax.text(x_start + 0.19, y + h - 0.016, block["title"], 
            fontsize=12, fontweight='bold', color='#f8fafc', va='center')
    
    # Sub / Description
    if i == 4:
        # Multiline untuk Bottleneck Block
        ax.text(x_start + 0.02, y + 0.042, block["sub"], 
                fontsize=9.2, color='#e2e8f0', va='center', linespacing=1.3)
    else:
        ax.text(x_start + 0.02, y + 0.020, block["sub"], 
                fontsize=9.2, color='#cbd5e1', va='center')
    
    # Shape / Dimension Badge on Right
    ax.text(x_start + box_width - 0.02, y + h / 2, block["shape"], 
            fontsize=9.2, color='#38bdf8', fontweight='semibold', ha='right', va='center',
            bbox=dict(facecolor='#020617', edgecolor=block["border"], boxstyle='round,pad=0.3', alpha=0.9))
    
    # Draw Connector Arrow down to next block
    if i < len(blocks) - 1:
        arrow_x = 0.5
        arrow_y_top = y - 0.002
        arrow_y_bottom = y - spacing + 0.004
        ax.annotate(
            '', xy=(arrow_x, arrow_y_bottom), xytext=(arrow_x, arrow_y_top),
            arrowprops=dict(facecolor='#38bdf8', edgecolor='#38bdf8', width=2, headwidth=6, headlength=6),
            zorder=3
        )
    
    cur_y = y - spacing

# Footer Summary Info
footer_rect = patches.FancyBboxPatch(
    (0.08, 0.015), 0.84, 0.052,
    boxstyle="round,pad=0.01,rounding_size=0.01",
    facecolor='#1e293b', edgecolor='#64748b', linewidth=1.5
)
ax.add_patch(footer_rect)

ax.text(0.5, 0.041, 
        "Ringkasan Parameter & Spesifikasi:\n"
        "Total Parameter: 2,427,459 (9.26 MB)  |  Trainable: 2,390,787 (9.12 MB)  |  Non-trainable: 36,672 (143.25 KB)\n"
        "Input Shape: 224x224x3  |  Akurasi Validasi: 85.99%  |  Target Output: 3 Kelas Mutu Tembakau (Filler, Binder, Wrapper)",
        ha='center', va='center', fontsize=9.2, color='#f1f5f9', fontweight='medium', linespacing=1.35)

plt.tight_layout()
plt.savefig(PNG_OUTPUT, dpi=300, facecolor=fig.get_facecolor(), bbox_inches='tight')
plt.close()

print(f"[OK] Gambar diagram arsitektur berhasil diperbarui: {PNG_OUTPUT}")
