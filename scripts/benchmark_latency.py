"""
===================================================================================
TobaccoGuard AI - Benchmark Latensi & Throughput Inferensi
MobileNetV2 vs AlexNet Murni
===================================================================================
Tujuan:
Mengukur kecepatan komputasi nyata (latensi per frame dalam milidetik dan FPS)
pada perangkat saat ini, untuk membuktikan keunggulan MobileNetV2 dalam integrasi
konveyor berjalan secara real-time. Data ini digunakan langsung untuk Bab IV Skripsi.
===================================================================================
"""

import os
import sys
import time
import json
import glob
from pathlib import Path
import numpy as np
import tensorflow as tf

BASE_DIR = Path(r"D:\laragon\www\Tobacco")
MODELS_DIR = BASE_DIR / "ai" / "models"
OUTPUTS_DIR = BASE_DIR / "ai" / "outputs"
TEST_DATA_DIR = BASE_DIR / "data" / "test"

MOBILENET_PATH = MODELS_DIR / "tobacco_model.keras"
ALEXNET_PATH = MODELS_DIR / "tobacco_model_alexnet_cmp.keras"

NUM_WARMUP = 10
NUM_ITERATIONS = 50
IMG_SIZE = (224, 224)

def load_sample_images():
    images = []
    jpg_files = list(TEST_DATA_DIR.glob("*.jpg"))
    if not jpg_files:
        jpg_files = list((BASE_DIR / "data" / "valid").glob("*.jpg"))
    
    # Ambil maksimal 10 gambar uji
    sample_files = jpg_files[:10]
    for p in sample_files:
        img = tf.io.read_file(str(p))
        img = tf.image.decode_jpeg(img, channels=3)
        img = tf.image.resize(img, IMG_SIZE)
        img = tf.cast(img, tf.float32) / 255.0
        images.append(img.numpy())
    return np.array(images)

def benchmark_model(model_path, model_name, sample_batch):
    print(f"\n[INFO] Memuat {model_name} dari: {model_path.name} ...")
    model = tf.keras.models.load_model(str(model_path))
    
    # 1. Warm-up (menghilangkan overhead kompilasi grafis pertama)
    print(f"  -> Melakukan warm-up ({NUM_WARMUP} iterasi)...")
    single_input = np.expand_dims(sample_batch[0], axis=0)
    for _ in range(NUM_WARMUP):
        _ = model(single_input, training=False)
        
    # 2. Benchmark Single Image (Latensi per Frame - Penggunaan Nyata Konveyor)
    print(f"  -> Mengukur latensi inferensi per frame ({NUM_ITERATIONS} iterasi)...")
    latencies = []
    num_samples = len(sample_batch)
    
    for i in range(NUM_ITERATIONS):
        # Gunakan citra bergantian
        img_input = np.expand_dims(sample_batch[i % num_samples], axis=0)
        
        t_start = time.perf_counter()
        _ = model(img_input, training=False)
        t_end = time.perf_counter()
        
        latencies.append((t_end - t_start) * 1000.0) # Konversi ke milidetik (ms)
        
    latencies = np.array(latencies)
    avg_latency = float(np.mean(latencies))
    std_latency = float(np.std(latencies))
    min_latency = float(np.min(latencies))
    max_latency = float(np.max(latencies))
    fps = 1000.0 / avg_latency if avg_latency > 0 else 0.0
    
    params = int(model.count_params())
    file_size_mb = os.path.getsize(str(model_path)) / (1024.0 * 1024.0)
    
    return {
        "model_name": model_name,
        "avg_latency_ms": round(avg_latency, 2),
        "std_latency_ms": round(std_latency, 2),
        "min_latency_ms": round(min_latency, 2),
        "max_latency_ms": round(max_latency, 2),
        "throughput_fps": round(fps, 1),
        "total_params": params,
        "file_size_mb": round(file_size_mb, 2)
    }

def main():
    print("=" * 75)
    print("  TobaccoGuard AI - Benchmark Latensi & Throughput Inferensi")
    print("=" * 75)
    
    samples = load_sample_images()
    print(f"[DATA] {len(samples)} citra uji dimuat untuk siklus benchmark.")
    
    # 1. Benchmark MobileNetV2
    mob_res = benchmark_model(MOBILENET_PATH, "MobileNetV2 (Transfer Learning)", samples)
    
    # 2. Benchmark AlexNet
    alex_res = benchmark_model(ALEXNET_PATH, "AlexNet Murni (Original 2012)", samples)
    
    # 3. Hitung Selisih & Rasio Kecepatan
    speedup = alex_res["avg_latency_ms"] / mob_res["avg_latency_ms"] if mob_res["avg_latency_ms"] > 0 else 1.0
    mem_ratio = alex_res["total_params"] / mob_res["total_params"] if mob_res["total_params"] > 0 else 1.0
    
    # 4. Tampilkan Tabel Hasil
    print("\n" + "=" * 75)
    print("  HASIL BENCHMARK KOMPUTASI NYATA (REAL-TIME CONVEYOR READINESS)")
    print("=" * 75)
    header = f"{'Metrik Evaluasi':<32} | {'MobileNetV2':<18} | {'AlexNet Murni':<18}"
    print(header)
    print("-" * len(header))
    print(f"{'Rata-rata Latensi (ms/frame)':<32} | {mob_res['avg_latency_ms']:<18} | {alex_res['avg_latency_ms']:<18}")
    print(f"{'Rentang Latensi Min-Max (ms)':<32} | {mob_res['min_latency_ms']}-{mob_res['max_latency_ms']:<15} | {alex_res['min_latency_ms']}-{alex_res['max_latency_ms']:<15}")
    print(f"{'Throughput (FPS)':<32} | {mob_res['throughput_fps']} FPS{'':<13} | {alex_res['throughput_fps']} FPS")
    print(f"{'Jumlah Parameter':<32} | {mob_res['total_params']:,}{'':<13} | {alex_res['total_params']:,}")
    print(f"{'Ukuran File Model':<32} | {mob_res['file_size_mb']} MB{'':<13} | {alex_res['file_size_mb']} MB")
    print(f"{'Rasio Efisiensi Kecepatan':<32} | {speedup:.2f}x Lebih Cepat{'':<13} | Baseline")
    print("=" * 75)
    
    # 5. Simpan Hasil ke JSON
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "iterations_tested": NUM_ITERATIONS,
        "mobilenetv2": mob_res,
        "alexnet": alex_res,
        "speedup_ratio": round(speedup, 2),
        "param_efficiency_ratio": round(mem_ratio, 2)
    }
    
    out_json = OUTPUTS_DIR / "benchmark_latency_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[SUKSES] Laporan benchmark disimpan ke: {out_json}")

if __name__ == "__main__":
    main()
