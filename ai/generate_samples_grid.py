"""
Script untuk membuat poster visual sampel daun per kelas mutu (Filler, Binder, Wrapper)
Berguna untuk bukti fisik pengujian kualitas dataset di naskah skripsi / laporan.
"""
import os
import random
import pandas as pd
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_ROOT = os.path.join(BASE_DIR, 'dataset')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

CLASS_INFO = [
    {"id": 0, "code": "filler", "name": "FILLER (Low Quality)", "desc": "Cacat, robek, bercak, atau berlubang", "color": "#DC2626"},
    {"id": 1, "code": "binder", "name": "BINDER (Medium Quality)", "desc": "Utuh, urat sedang, pengikat cerutu", "color": "#D97706"},
    {"id": 2, "code": "wrapper", "name": "WRAPPER (High Quality)", "desc": "Mulus sempurna, lentur, mutu ekspor", "color": "#16A34A"}
]

csv_path = os.path.join(DATASET_ROOT, 'train', '_classes.csv')
df = pd.read_csv(csv_path)

samples_per_class = {0: [], 1: [], 2: []}

for _, row in df.iterrows():
    active = [c.strip() for c in df.columns[1:] if row[c] == 1]
    act_str = ' '.join(active).lower()

    lbl_id = None
    if 'filler' in act_str or 'low' in act_str:
        lbl_id = 0
    elif 'binder' in act_str or 'medium' in act_str:
        lbl_id = 1
    elif 'wrapper' in act_str or 'high' in act_str:
        lbl_id = 2

    if lbl_id is not None and len(samples_per_class[lbl_id]) < 4:
        img_p = os.path.join(DATASET_ROOT, 'train', row['filename'])
        if os.path.exists(img_p):
            samples_per_class[lbl_id].append(img_p)

fig, axes = plt.subplots(3, 4, figsize=(15, 11))
fig.suptitle('Visualisasi Sampel Nyata Mutu Daun Tembakau (Tobacco.v2i.multiclass)',
             fontsize=16, fontweight='bold', y=0.98)

for row_idx, info in enumerate(CLASS_INFO):
    cls_id = info['id']
    img_paths = samples_per_class[cls_id]

    for col_idx in range(4):
        ax = axes[row_idx, col_idx]
        if col_idx < len(img_paths):
            with Image.open(img_paths[col_idx]) as img:
                ax.imshow(img)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_color(info['color'])
                spine.set_linewidth(2.5)

            if col_idx == 0:
                ax.set_ylabel(f"{info['name']}\n{info['desc']}",
                              fontsize=11, fontweight='bold', color=info['color'], labelpad=12)
            ax.set_title(f"Sampel #{col_idx+1}", fontsize=10)
        else:
            ax.axis('off')

plt.tight_layout()
out_path = os.path.join(REPORTS_DIR, 'dataset_samples_grid.png')
plt.savefig(out_path, dpi=160, bbox_inches='tight', facecolor='white')
plt.close()
print(f"[OK] Visual sample grid berhasil dibuat di:\n{out_path}")
