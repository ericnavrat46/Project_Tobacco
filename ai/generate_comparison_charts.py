"""
Script untuk menghasilkan grafik perbandingan visual MobileNetV2 vs AlexNet.
Bukti empiris yang bisa ditunjukkan ke dosen penguji.
"""
import os
import json
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

# Muat metadata kedua model
mobilenet_meta_path = os.path.join(BASE_DIR, 'models', 'model_metadata.json')
alexnet_meta_path = os.path.join(BASE_DIR, 'models', 'alexnet_metadata.json')

with open(mobilenet_meta_path, 'r') as f:
    mobilenet_meta = json.load(f)
with open(alexnet_meta_path, 'r') as f:
    alexnet_meta = json.load(f)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# =====================================================
# GRAFIK 1: Perbandingan Akurasi & Loss (Bar Chart)
# =====================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
fig.suptitle('Perbandingan Kinerja Empiris: MobileNetV2 vs AlexNet',
             fontsize=15, fontweight='bold', y=1.02)

# Akurasi
models = ['MobileNetV2\n(Transfer Learning)', 'AlexNet\n(From Scratch)']
acc_vals = [mobilenet_meta['validation_accuracy'] * 100, alexnet_meta['validation_accuracy'] * 100]
bars1 = axes[0].bar(models, acc_vals, color=['#2563EB', '#DC2626'], width=0.5, edgecolor='white', linewidth=2)
axes[0].set_ylabel('Akurasi Validasi (%)', fontsize=11)
axes[0].set_title('Akurasi Validasi', fontsize=13, fontweight='bold')
axes[0].set_ylim(0, 100)
for bar, val in zip(bars1, acc_vals):
    axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                 f'{val:.2f}%', ha='center', va='bottom', fontsize=14, fontweight='bold')
axes[0].axhline(y=acc_vals[0], color='#2563EB', linestyle='--', alpha=0.3, linewidth=1)

# Loss
loss_vals = [mobilenet_meta['validation_loss'], alexnet_meta['validation_loss']]
bars2 = axes[1].bar(models, loss_vals, color=['#2563EB', '#DC2626'], width=0.5, edgecolor='white', linewidth=2)
axes[1].set_ylabel('Validation Loss', fontsize=11)
axes[1].set_title('Validation Loss (Semakin Rendah = Semakin Baik)', fontsize=13, fontweight='bold')
axes[1].set_ylim(0, max(loss_vals) * 1.4)
for bar, val in zip(bars2, loss_vals):
    axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                 f'{val:.4f}', ha='center', va='bottom', fontsize=14, fontweight='bold')

plt.tight_layout()
path1 = os.path.join(REPORTS_DIR, 'perbandingan_akurasi_loss.png')
fig.savefig(path1, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"[OK] Grafik 1 tersimpan: {path1}")

# =====================================================
# GRAFIK 2: Perbandingan F1-Score Per Kelas
# =====================================================
alexnet_report = alexnet_meta.get('classification_report', {})

# Data per kelas
classes = ['Filler\n(Low Quality)', 'Binder\n(Medium Quality)', 'Wrapper\n(High Quality)']
class_keys = ['filler', 'binder', 'wrapper']

# AlexNet per-kelas
alexnet_f1 = [alexnet_report.get(k, {}).get('f1-score', 0) * 100 for k in class_keys]
alexnet_prec = [alexnet_report.get(k, {}).get('precision', 0) * 100 for k in class_keys]
alexnet_rec = [alexnet_report.get(k, {}).get('recall', 0) * 100 for k in class_keys]

fig2, ax2 = plt.subplots(figsize=(12, 6))
fig2.suptitle('Perbandingan F1-Score Per Kelas: AlexNet (CNN Klasik)',
              fontsize=14, fontweight='bold')

x = np.arange(len(classes))
width = 0.25

b1 = ax2.bar(x - width, alexnet_prec, width, label='Precision', color='#3B82F6', edgecolor='white')
b2 = ax2.bar(x, alexnet_rec, width, label='Recall', color='#10B981', edgecolor='white')
b3 = ax2.bar(x + width, alexnet_f1, width, label='F1-Score', color='#F59E0B', edgecolor='white')

ax2.set_ylabel('Skor (%)', fontsize=11)
ax2.set_xticks(x)
ax2.set_xticklabels(classes, fontsize=10)
ax2.set_ylim(0, 110)
ax2.legend(loc='upper right', fontsize=10)
ax2.grid(axis='y', alpha=0.3)

for bars in [b1, b2, b3]:
    for bar in bars:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.1f}%',
                 ha='center', va='bottom', fontsize=9, fontweight='bold')

plt.tight_layout()
path2 = os.path.join(REPORTS_DIR, 'alexnet_f1_per_kelas.png')
fig2.savefig(path2, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"[OK] Grafik 2 tersimpan: {path2}")

# =====================================================
# GRAFIK 3: Ringkasan Perbandingan Arsitektur
# =====================================================
fig3, ax3 = plt.subplots(figsize=(12, 7))
ax3.axis('off')
fig3.suptitle('Ringkasan Perbandingan Arsitektur MobileNetV2 vs AlexNet',
              fontsize=15, fontweight='bold', y=0.97)

table_data = [
    ['Aspek', 'MobileNetV2 (2018)', 'AlexNet (2012)'],
    ['Pendekatan', 'Transfer Learning\n(Bobot ImageNet)', 'Training dari Nol\n(Random Initialization)'],
    ['Tipe Konvolusi', 'Depthwise Separable\n(3x3 DW + 1x1 PW)', 'Standard Spatial\n(11x11, 5x5, 3x3)'],
    ['Jumlah Parameter', '2.42 Juta\n(11.5 MB)', '11.35 Juta\n(136 MB)'],
    ['Akurasi Validasi', f'{mobilenet_meta["validation_accuracy"]*100:.2f}%', f'{alexnet_meta["validation_accuracy"]*100:.2f}%'],
    ['Validation Loss', f'{mobilenet_meta["validation_loss"]:.4f}', f'{alexnet_meta["validation_loss"]:.4f}'],
    ['Selisih Akurasi', '(Baseline)', f'-{(mobilenet_meta["validation_accuracy"] - alexnet_meta["validation_accuracy"])*100:.2f}%\n(Lebih rendah)'],
    ['Cocok Untuk', 'Edge/IoT Real-time\n(> 30 FPS di CPU)', 'Riset/Eksperimen\n(Butuh GPU)'],
    ['Kesimpulan', 'MODEL TERPILIH', 'Pembanding saja']
]

table = ax3.table(cellText=table_data, loc='center', cellLoc='center')
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1.0, 2.2)

# Header row styling
for j in range(3):
    cell = table[0, j]
    cell.set_facecolor('#1E3A8A')
    cell.set_text_props(color='white', fontweight='bold', fontsize=11)

# Color the data rows
for i in range(1, len(table_data)):
    table[i, 0].set_facecolor('#F1F5F9')
    table[i, 0].set_text_props(fontweight='bold')
    table[i, 1].set_facecolor('#EFF6FF')
    table[i, 2].set_facecolor('#FEF2F2')

# Highlight accuracy row
table[4, 1].set_text_props(fontweight='bold', color='#1D4ED8')
table[4, 2].set_text_props(fontweight='bold', color='#DC2626')

# Highlight conclusion row
table[8, 1].set_facecolor('#DCFCE7')
table[8, 1].set_text_props(fontweight='bold', color='#166534')
table[8, 2].set_facecolor('#FEE2E2')
table[8, 2].set_text_props(fontweight='bold', color='#991B1B')

plt.tight_layout()
path3 = os.path.join(REPORTS_DIR, 'ringkasan_perbandingan_arsitektur.png')
fig3.savefig(path3, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"[OK] Grafik 3 tersimpan: {path3}")

print("\n" + "=" * 60)
print("  SEMUA GRAFIK PERBANDINGAN BERHASIL DIBUAT!")
print("=" * 60)
