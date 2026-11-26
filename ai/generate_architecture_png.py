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

# Setup Figure
fig, ax = plt.subplots(figsize=(15, 12), dpi=300)
fig.patch.set_facecolor('#0f172a') # Dark slate background
ax.set_facecolor('#0f172a')
ax.axis('off')

# Title & Metadata Header
plt.text(0.5, 0.96, "ARSITEKTUR MODEL KLASIFIKASI MUTU TEMBAKAU", 
         ha='center', va='center', fontsize=18, fontweight='bold', color='#f8fafc', fontfamily='sans-serif')
plt.text(0.5, 0.93, "TobaccoGuard AI  |  Framework: TensorFlow 2 / Keras  |  Backbone: MobileNetV2 (Pre-trained ImageNet)", 
         ha='center', va='center', fontsize=11, color='#94a3b8', fontfamily='sans-serif')

# Boxes definition: (name, desc, shape, color, border_color)
blocks = [
    {
        "title": "Input Layer",
        "sub": "Citra Daun Tembakau (RGB)",
        "shape": "(Batch, 224, 224, 3)",
        "color": "#1e293b",
        "border": "#38bdf8",
        "badge": "INPUT"
    },
    {
        "title": "MobileNetV2 Backbone",
        "sub": "154 Layers | Inverted Residuals & Linear Bottlenecks\nFeature Extractor pre-trained on ImageNet",
        "shape": "Output: (Batch, 7, 7, 1280)\nParams: ~2.26M",
        "color": "#1e3a5f",
        "border": "#60a5fa",
        "badge": "BACKBONE"
    },
    {
        "title": "Global Average Pooling 2D",
        "sub": "Kompresi spasial 7x7 menjadi representasi vektor fitur 1D",
        "shape": "(Batch, 1280)",
        "color": "#1e293b",
        "border": "#818cf8",
        "badge": "POOLING"
    },
    {
        "title": "Batch Normalization & Dropout (0.3)",
        "sub": "Normalisasi distribusi aktivasi & Regularisasi Dropout 30%",
        "shape": "(Batch, 1280)",
        "color": "#1e293b",
        "border": "#a855f7",
        "badge": "REGULARIZATION"
    },
    {
        "title": "Dense Layer (ReLU)",
        "sub": "Fully Connected Layer pemetaan fitur mutu tembakau (128 neuron)",
        "shape": "(Batch, 128)\nParams: 163,968",
        "color": "#1e293b",
        "border": "#ec4899",
        "badge": "DENSE HEAD"
    },
    {
        "title": "Dropout Layer (0.2)",
        "sub": "Pencegahan Overfitting akhir sebelum prediksi",
        "shape": "(Batch, 128)",
        "color": "#1e293b",
        "border": "#f43f5e",
        "badge": "DROPOUT"
    },
    {
        "title": "Output Dense (Softmax)",
        "sub": "Klasifikasi Mutu Daun: [0: Filler, 1: Binder, 2: Wrapper]",
        "shape": "(Batch, 3)\nProbabilitas Kelas Mutu",
        "color": "#064e3b",
        "border": "#10b981",
        "badge": "OUTPUT CLASSIFIER"
    }
]

y_start = 0.86
box_height = 0.075
box_width = 0.76
x_start = 0.12
spacing = 0.038

for i, block in enumerate(blocks):
    y = y_start - i * (box_height + spacing)
    
    # Draw Rectangle Box
    rect = patches.FancyBboxPatch(
        (x_start, y), box_width, box_height,
        boxstyle="round,pad=0.015,rounding_size=0.015",
        facecolor=block["color"],
        edgecolor=block["border"],
        linewidth=2,
        zorder=2
    )
    ax.add_patch(rect)
    
    # Badge (Category)
    ax.text(x_start + 0.02, y + box_height - 0.018, block["badge"], 
            fontsize=8, fontweight='bold', color=block["border"],
            bbox=dict(facecolor='#0f172a', edgecolor=block["border"], boxstyle='round,pad=0.2', linewidth=1),
            va='center')

    # Title
    ax.text(x_start + 0.16, y + box_height - 0.018, block["title"], 
            fontsize=12, fontweight='bold', color='#f8fafc', va='center')
    
    # Description
    ax.text(x_start + 0.02, y + 0.025, block["sub"], 
            fontsize=9.5, color='#cbd5e1', va='center')
    
    # Shape / Dimension info on right side
    ax.text(x_start + box_width - 0.02, y + box_height / 2, block["shape"], 
            fontsize=9.5, color='#38bdf8', fontweight='semibold', ha='right', va='center',
            bbox=dict(facecolor='#0b1329', edgecolor='#1e293b', boxstyle='round,pad=0.3', alpha=0.9))
    
    # Draw Connector Arrow down to next block
    if i < len(blocks) - 1:
        arrow_x = 0.5
        arrow_y_top = y - 0.002
        arrow_y_bottom = y - spacing + 0.005
        ax.annotate(
            '', xy=(arrow_x, arrow_y_bottom), xytext=(arrow_x, arrow_y_top),
            arrowprops=dict(facecolor='#38bdf8', edgecolor='#38bdf8', width=2, headwidth=7, headlength=7),
            zorder=3
        )

# Summary Info Footer
footer_y = 0.06
summary_rect = patches.FancyBboxPatch(
    (0.08, 0.02), 0.84, 0.065,
    boxstyle="round,pad=0.01,rounding_size=0.01",
    facecolor='#1e293b', edgecolor='#475569', linewidth=1.5
)
ax.add_patch(summary_rect)

ax.text(0.5, footer_y, 
        "Ringkasan Parameter:\n"
        "Total Params: 2,427,459 (9.26 MB)  |  Trainable: 2,390,787 (9.12 MB)  |  Non-trainable: 36,672 (143.25 KB)\n"
        "Akurasi Validasi: 85.99%  |  Input Resolusi: 224x224x3  |  Kelas Mutu: 3 (Filler, Binder, Wrapper)",
        ha='center', va='center', fontsize=9.5, color='#e2e8f0', fontweight='medium', linespacing=1.4)

plt.tight_layout()
plt.savefig(PNG_OUTPUT, dpi=300, facecolor=fig.get_facecolor(), bbox_inches='tight')
plt.close()

print(f"[OK] Diagram arsitektur model berhasil dibuat: {PNG_OUTPUT}")

