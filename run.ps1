# TobaccoGuard IoT - PowerShell Launcher
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "          TOBACCOGUARD IOT - GUDANG TEMBAKAU & CONVEYOR               " -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  [1] Jalankan Server Web Dashboard (Flask - port 5000)" -ForegroundColor Cyan
Write-Host "  [2] Jalankan Simulator IoT Saja (ESP32 & Wemos Conveyor)" -ForegroundColor Cyan
Write-Host "  [3] Jalankan SERVER + SIMULATOR Sekaligus (Rekomendasi untuk Demo)" -ForegroundColor Yellow
Write-Host "  [4] Inisialisasi Ulang Data Awal Database (seed_data.py)" -ForegroundColor Cyan
Write-Host "  [5] Buka Web Dashboard di Browser (http://localhost:5000)" -ForegroundColor Cyan
Write-Host "  [6] Keluar" -ForegroundColor Gray
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green

$choice = Read-Host "Pilih menu [1-6]"

switch ($choice) {
    "1" {
        Clear-Host
        Write-Host "Menjalankan Server Web Flask di http://127.0.0.1:5000..." -ForegroundColor Cyan
        python app.py
    }
    "2" {
        Clear-Host
        Write-Host "Menjalankan Simulator IoT..." -ForegroundColor Yellow
        python simulator.py
    }
    "3" {
        Clear-Host
        Write-Host "Menjalankan Server Flask & Simulator IoT Terpadu..." -ForegroundColor Yellow
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'TobaccoGuard - Server Flask (Port 5000)' -ForegroundColor Cyan; python app.py"
        Start-Sleep -Seconds 3
        Start-Process "http://localhost:5000"
        Write-Host "Server dan browser telah dibuka!" -ForegroundColor Green
        Write-Host "Menjalankan simulator di sesi ini..." -ForegroundColor Yellow
        python simulator.py
    }
    "4" {
        Clear-Host
        Write-Host "Mengisi data simulasi awal database..." -ForegroundColor Cyan
        python seed_data.py
    }
    "5" {
        Start-Process "http://localhost:5000"
    }
    "6" {
        exit
    }
    default {
        Write-Host "Pilihan tidak valid." -ForegroundColor Red
    }
}
