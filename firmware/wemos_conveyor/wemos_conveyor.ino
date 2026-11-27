/*
  ===================================================================================
  TobaccoGuard IoT - Firmware Conveyor & Leaf Sorter (Wemos D1 Mini / ESP8266)
  ===================================================================================
  Konfigurasi:
  - WiFi SSID        : MUTIARA
  - WiFi Password    : M4m4p4p4
  - Server Flask     : http://192.168.18.7:5000/api/conveyor
  - IR Sensor Pin    : D7 (GPIO 13)
  - Stepper Step Pin : D5 (GPIO 14)
  - Stepper Dir Pin  : D6 (GPIO 12)
  - Servo 1 (Binder) : D1 (GPIO 5)
  - Servo 2 (Filler) : D2 (GPIO 4)
  ===================================================================================
*/

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>
#include <Servo.h>

Servo servoBinder;
Servo servoFiller;

// --- KONFIGURASI JARINGAN & SERVER FLASK ---
const char* WIFI_SSID     = "MUTIARA";
const char* WIFI_PASSWORD = "M4m4p4p4";
const char* SERVER_URL    = "http://192.168.18.7:5000/api/conveyor/latest";

// --- KONFIGURASI PIN HARDWARE ---
const int irPin       = D7;      
const int servo1Pin   = D1; // Servo 1 -> BINDER (MG996R)
const int servo2Pin   = D2; // Servo 2 -> FILLER (MG90S)
const int stepPin     = D5;    
const int dirPin      = D6;     

// Posisi sudut masing-masing servo
const int BINDER_DIAM   = 15;
const int BINDER_DORONG = 180;
const int FILLER_DIAM   = 180;
const int FILLER_DORONG = 15;

// Kecepatan putaran konveyor (microsecond per pulse)
const int kecepatanKonveyor = 50; 

// Memori Sensor IR
int statusSensorSebelumnya = HIGH; 

// Variabel Penghitung Waktu
unsigned long timerMulai = 0;
unsigned long leafCounter = 0;

// Status mesin konveyor
int statusMesin = 0; 

// Variabel hasil klasifikasi yang sedang diproses
String kategoriSaatIni = "binder";
float confidenceSaatIni = 0.92;

// Prototipe fungsi
void connectToWiFi();
void classifyAndSendLeaf();

void setup() {
  Serial.begin(115200); // Pastikan Serial Monitor disetel ke 115200 baud
  delay(100);
  Serial.println("\n[TobaccoGuard] Sistem Conveyor Aktif! (115200 baud)");

  pinMode(irPin, INPUT);
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);

  digitalWrite(dirPin, LOW);

  servoBinder.attach(servo1Pin);
  servoFiller.attach(servo2Pin);
  servoBinder.write(BINDER_DIAM);
  servoFiller.write(FILLER_DIAM);

  // Hubungkan ke WiFi
  connectToWiFi();
}

void loop() {
  // Pastikan WiFi tetap terhubung tanpa memblokir pergerakan motor
  if (WiFi.status() != WL_CONNECTED && millis() % 10000 < 50) {
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }

  int statusSensorSekarang = digitalRead(irPin);
  
  // ==============================================================
  // 1. DETEKSI DAUN BARU MASUK
  // ==============================================================
  if (statusMesin == 0 && statusSensorSekarang == LOW && statusSensorSebelumnya == HIGH) {
    statusSensorSebelumnya = LOW; // Kunci sensor
    statusMesin = 1;              // Konveyor BERHENTI (Tunggu pemindaian)
    timerMulai = millis();        // Mulai stopwatch
    leafCounter++;

    Serial.printf("\n[CONVEYOR] Daun #%lu terdeteksi! Konveyor BERHENTI untuk pemindaian...\n", leafCounter);
  }

  // ==============================================================
  // 2. RESET SENSOR (Membuka Kunci saat kosong dan mesin normal)
  // ==============================================================
  if (statusMesin == 0 && statusSensorSekarang == HIGH) {
    statusSensorSebelumnya = HIGH;
  }

  // ==============================================================
  // 3. LOGIKA URUTAN MESIN (STATE MACHINE)
  // ==============================================================
  
  // FASE 1: Konveyor BERHENTI (1 Detik saat daun tepat di area pemindaian)
  if (statusMesin == 1) {
    if (millis() - timerMulai >= 1000) {  
      classifyAndSendLeaf();              // Ambil hasil deteksi webcam terbaru dari Flask
      statusMesin = 2;                    
      timerMulai = millis();
      Serial.println("[CONVEYOR] Selesai pindai! Konveyor JALAN membawa daun ke servo...");
    }
  } 
  
  // FASE 2: Konveyor BERJALAN (4 Detik membawa daun mendekati servo)
  else if (statusMesin == 2) {
    if (millis() - timerMulai >= 4000) {  
      statusMesin = 3;                    
      timerMulai = millis();

      if (kategoriSaatIni == "binder") {
        servoBinder.write(BINDER_DORONG);
        Serial.println("[SERVO] Binder -> Servo 1 (D1) JALAN menyortir daun.");
      } else if (kategoriSaatIni == "filler") {
        servoFiller.write(FILLER_DORONG);
        Serial.println("[SERVO] Filler -> Servo 2 (D2) JALAN menyortir daun.");
      } else {
        Serial.println("[SERVO] Wrapper -> Lolos (Kedua servo diam).");
      }
    }
  }
  
  // FASE 3: Servo Menahan Posisi Dorong (Konveyor TETAP JALAN)
  else if (statusMesin == 3) {
    if (millis() - timerMulai >= 1000) {  // Lama palang terbuka (1 detik)
      statusMesin = 4;                    
      servoBinder.write(BINDER_DIAM);
      servoFiller.write(FILLER_DIAM);
      timerMulai = millis();
      Serial.println("[SERVO] Servo kembali ke posisi awal.");
    }
  }
  
  // FASE 4: Servo Turun Posisi 0 (Konveyor TETAP JALAN)
  else if (statusMesin == 4) {
    if (millis() - timerMulai >= 500) {   // Lama proses palang turun
      statusMesin = 0;                    // Kembali ke mode normal
      Serial.println("[CONVEYOR] Siklus selesai. Siap menerima daun berikutnya.\n");
    }
  }

  // ==============================================================
  // 4. PENGGERAK KONVEYOR (STEPPER MOTOR)
  // Konveyor BERHENTI HANYA di status 1. Sisanya JALAN TERUS!
  // ==============================================================
  if (statusMesin == 0 || statusMesin == 2 || statusMesin == 3 || statusMesin == 4) {
    for (int i = 0; i < 5; i++) {
      digitalWrite(stepPin, HIGH);
      delayMicroseconds(kecepatanKonveyor);
      digitalWrite(stepPin, LOW);
      delayMicroseconds(kecepatanKonveyor);
    }
  }
}

// ==============================================================
// 5. AMBIL HASIL KLASIFIKASI WEBCAM TERBARU DARI FLASK (GET)
// ==============================================================
void classifyAndSendLeaf() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WARN] WiFi belum terkoneksi, gagal mengambil hasil dari Flask.");
    return;
  }

  WiFiClient client;
  HTTPClient http;
  if (http.begin(client, SERVER_URL)) {
    int httpCode = http.GET();
    if (httpCode == HTTP_CODE_OK) {
      String payload = http.getString();
      StaticJsonDocument<2048> doc;
      DeserializationError err = deserializeJson(doc, payload);

      // Pastikan parsing JSON berhasil dan field ada
      if (err) {
        Serial.printf("[HTTP] Gagal parsing JSON (%s). Payload: %s\n", err.c_str(), payload.c_str());
      } else if (doc["data"].containsKey("hasil_klasifikasi")) {
      kategoriSaatIni = doc["data"]["hasil_klasifikasi"].as<String>();
      kategoriSaatIni.toLowerCase();
      // confidence_score optional, gunakan 0.0 bila tidak ada
      confidenceSaatIni = doc["data"].containsKey("confidence_score") ? 
                        doc["data"]["confidence_score"].as<float>() : 0.0f;
      Serial.printf("[HTTP] Hasil Webcam dari Flask: %s (%.1f%%)\n",
                    kategoriSaatIni.c_str(), confidenceSaatIni * 100.0);
    } else {
      Serial.println("[HTTP] Data klasifikasi belum tersedia di Flask.");
    }
    } else {
      Serial.printf("[HTTP] Gagal GET dari Flask (%d): %s\n",
                    httpCode, http.errorToString(httpCode).c_str());
    }
    http.end();
  }
}

// ==============================================================
// 6. KONEKSI KE JARINGAN WIFI
// ==============================================================
void connectToWiFi() {
  Serial.printf("\n[WiFi] Menghubungkan ke %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(300);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Terhubung!");
    Serial.print("[WiFi] IP Wemos: ");
    Serial.println(WiFi.localIP());
    Serial.printf("[WiFi] Target Server Flask: %s\n", SERVER_URL);
  } else {
    Serial.println("\n[WiFi] Koneksi gagal! Periksa nama/password WiFi.");
  }
}
