import shutil
import sys
from pathlib import Path

def move_subfolder(src_parent: Path, dst_parent: Path, name: str):
    src = src_parent / name
    dst = dst_parent / name
    if not src.exists():
        print(f"[WARN] Source folder {src} does not exist, skipping.")
        return
    dst.mkdir(parents=True, exist_ok=True)
    # move all files/subfolders preserving structure
    for item in src.rglob('*'):
        if item.is_dir():
            continue
        # compute relative path inside src folder
        rel = item.relative_to(src)
        target = dst / rel.parent
        target.mkdir(parents=True, exist_ok=True)
        shutil.move(str(item), str(target / rel.name))
    # after moving files, remove the (now empty) src folder tree
    try:
        shutil.rmtree(src)
        print(f"[INFO] Moved and removed {src}")
    except Exception as e:
        print(f"[ERROR] Could not remove {src}: {e}")

def main():
    # Root where the duplicated dataset lives
    src_root = Path('ai/dataset/dataset')
    # Destination root used by training scripts
    dst_root = Path('data')
    if not src_root.exists():
        print(f"[ERROR] Source root {src_root} not found.")
        sys.exit(1)
    # Ensure destination exists
    dst_root.mkdir(parents=True, exist_ok=True)
    for folder in ['train', 'val']:
        move_subfolder(src_root, dst_root, folder)
    # If src_root is now empty, delete it
    if not any(src_root.iterdir()):
        try:
            src_root.rmdir()
            print(f"[INFO] Deleted empty folder {src_root}")
        except Exception as e:
            print(f"[WARN] Could not delete {src_root}: {e}")
    else:
        print(f"[WARN] {src_root} still contains files, manual check may be needed.")

if __name__ == '__main__':
    main()

