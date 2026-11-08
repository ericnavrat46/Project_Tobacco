import shutil
import sys
from pathlib import Path

def move_contents(src_root: Path, dst_root: Path, subfolders: list):
    """Move subfolders (train, val, test) from src_root to dst_root.
    If a destination subfolder already exists, files are merged.
    """
    for name in subfolders:
        src = src_root / name
        dst = dst_root / name
        if not src.exists():
            print(f"[WARN] {src} tidak ada, lewati.")
            continue
        dst.mkdir(parents=True, exist_ok=True)
        # copy semua isi, menjaga struktur dalam kelas
        for item in src.rglob('*'):
            if item.is_dir():
                continue
            # relative path inside src (e.g. wrapper/img1.jpg)
            rel = item.relative_to(src)
            target_dir = dst / rel.parent
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(target_dir / rel.name))
            print(f"[INFO] {item} → {target_dir / rel.name}")
        # setelah semua file dipindahkan, hapus folder src (sekarang kosong)
        try:
            shutil.rmtree(src)
            print(f"[INFO] Hapus folder kosong {src}")
        except Exception as e:
            print(f"[ERROR] Gagal hapus {src}: {e}")

def main():
    # root nested dataset (ai/dataset/dataset)
    src_root = Path('ai/dataset/dataset')
    # destination root yang dipakai training scripts (data)
    dst_root = Path('data')
    if not src_root.exists():
        print(f"[ERROR] Source root {src_root} tidak ditemukan.")
        sys.exit(1)
    dst_root.mkdir(parents=True, exist_ok=True)
    # subfolders yang biasanya ada
    subfolders = ['train', 'val', 'test']
    move_contents(src_root, dst_root, subfolders)
    # jika src_root kosong setelah dipindah, hapus foldernya
    if not any(src_root.iterdir()):
        try:
            src_root.rmdir()
            print(f"[INFO] Hapus folder kosong {src_root}")
        except Exception as e:
            print(f"[WARN] Tidak dapat hapus {src_root}: {e}")
    else:
        print(f"[WARN] {src_root} masih berisi file, periksa manual.")

if __name__ == '__main__':
    main()

