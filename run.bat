@echo off
title TobaccoGuard IoT - Control Center
color 0A
setlocal enabledelayedexpansion

:: Direktori root proyek
cd /d "%~dp0"

:MENU
cls
echo ======================================================================
echo           TOBACCOGUARD IOT - GUDANG TEMBAKAU ^& CONVEYOR
echo ======================================================================
echo.
echo   [1] Jalankan Server Web Dashboard (Flask - port 5000)
echo   [2] Jalankan Simulator IoT Saja (ESP32 ^& Wemos Conveyor)
echo   [3] Jalankan SERVER + SIMULATOR Sekaligus (Rekomendasi untuk Demo)
echo   [4] Inisialisasi Ulang Data Awal Database (seed_data.py)
echo   [5] Buka Web Dashboard di Browser (http://localhost:5000)
echo   [6] Keluar
echo.
echo ======================================================================
set /p CHOICE="Pilih menu [1-6]: "

if "%CHOICE%"=="1" goto RUN_SERVER
if "%CHOICE%"=="2" goto RUN_SIMULATOR
if "%CHOICE%"=="3" goto RUN_ALL
if "%CHOICE%"=="4" goto RUN_SEED
if "%CHOICE%"=="5" goto OPEN_BROWSER
if "%CHOICE%"=="6" goto EXIT_APP

echo.
echo Pilihan tidak valid. Silakan tekan tombol apa saja untuk memilih lagi...
pause >nul
goto MENU

:RUN_SERVER
cls
echo ======================================================================
echo   Menjalankan Server Web Flask (http://127.0.0.1:5000)...
echo   Tekan Ctrl + C untuk menghentikan server.
echo ======================================================================
echo.
python app.py
pause
goto MENU

:RUN_SIMULATOR
cls
echo ======================================================================
echo   Menjalankan Simulator IoT (ESP32 ^& Conveyor Classifier)...
echo   Tekan Ctrl + C untuk berhenti.
echo ======================================================================
echo.
python simulator.py
pause
goto MENU

:RUN_ALL
cls
echo ======================================================================
echo   Menjalankan Server Flask ^& Simulator IoT secara Terpadu...
echo ======================================================================
echo.
echo [1/3] Membuka jendela server Flask di background...
start "TobaccoGuard - Server Flask (Port 5000)" cmd /k "color 0B && python app.py"

echo [2/3] Menunggu 3 detik agar server siap...
timeout /t 3 /nobreak >nul

echo [3/3] Membuka dashboard di browser...
start http://localhost:5000

echo.
echo Server dan browser telah dibuka!
echo Sekarang menjalankan Simulator IoT di jendela ini...
echo.
python simulator.py
pause
goto MENU

:RUN_SEED
cls
echo ======================================================================
echo   Mengisi Data Awal Database SQLite (seed_data.py)...
echo ======================================================================
echo.
python seed_data.py
echo.
echo Selesai!
pause
goto MENU

:OPEN_BROWSER
start http://localhost:5000
goto MENU

:EXIT_APP
echo.
echo Terima kasih! Sampai jumpa.
timeout /t 1 /nobreak >nul
exit /b 0
