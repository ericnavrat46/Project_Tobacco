/*
  ===================================================================================
  TobaccoGuard IoT - Firmware Monitoring Gudang Tembakau (ESP32)
  ===================================================================================
  Deskripsi:
  Membaca sensor lingkungan gudang tembakau, mengontrol kipas dan buzzer alarm,
  lalu mengirimkan telemetri secara berkala via HTTP POST JSON ke server Flask.

  Komponen Hardware:
  - Mikrokontroler : ESP32 DevKit V1 (30 / 38 pin)
  - Sensor Suhu & RH: DHT22 (Pin GPIO 4)
  - Sensor Gas    : MQ-135 / MQ-2 Air Quality (Pin Analog GPIO 34 / ADC1)
  - Modul Relay   : Relay 1-Channel untuk Kipas Sirkulasi (Pin GPIO 18)
  - Modul Buzzer  : Active Buzzer untuk Alarm Kritis (Pin GPIO 19)
  - Indikator LED : Built-in LED ESP32 (Pin GPIO 2)

  Library yang Dibutuhkan (Install via Arduino Library Manager):
  1. "DHT sensor library" by Adafruit
  2. "Adafruit Unified Sensor" by Adafruit
  3. "ArduinoJson" by Benoit Blanchon (versi 6 atau 7)
  ===================================================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <ArduinoJson.h>

// =================== 1. KONFIGURASI JARINGAN & SERVER ===================
const char* WIFI_SSID     = "NAMA_WIFI_ANDA";         // Ganti dengan SSID WiFi Anda
const char* WIFI_PASSWORD = "PASSWORD_WIFI_ANDA";     // Ganti dengan Password WiFi Anda

// Masukkan IP Komputer / Server Laragon Anda (Cek via 'ipconfig' di cmd Windows)
// Contoh: "http://192.168.1.8:5000/api/gudang"
const char* SERVER_URL    = "http://192.168.1.8:5000/api/gudang";
const char* SETTINGS_URL  = "http://192.168.1.8:5000/api/settings";

// Interval pengiriman data ke server (milidetik)
const unsigned long SEND_INTERVAL_MS = 5000; // Kirim tiap 5 detik

// =================== 2. DEFINISI PIN HARDWARE ===================
#define DHTPIN        4       // Pin Data DHT22 (GPIO 4)
#define DHTTYPE       DHT22   // Jenis DHT: DHT22 (AM2302)
#define GAS_PIN       34      // Pin Analog MQ-135 (GPIO 34 ADC1_CH6)
#define RELAY_FAN_PIN 18      // Pin Kontrol Relay Kipas (GPIO 18)
#define BUZZER_PIN    19      // Pin Kontrol Buzzer Alarm (GPIO 19)
#define LED_PIN       2       // Pin Built-in LED Indikator (GPIO 2)

// Konfigurasi Trigger Relay (Sebagian besar relay module menggunakan ACTIVE LOW)
#define RELAY_ON      LOW
#define RELAY_OFF     HIGH

// =================== 3. AMBANG BATAS LOKAL (FALLBACK HARDWARE) ===================
const float THRESHOLD_TEMP_MAX_NORMAL = 28.0; // °C -> Suhu > 28°C kipas nyala
const float THRESHOLD_HUM_MAX_NORMAL  = 70.0; // %  -> RH > 70% kipas nyala
const float THRESHOLD_TEMP_DANGER     = 32.0; // °C -> Suhu > 32°C ALARM BAHAYA
const int   THRESHOLD_GAS_DANGER      = 300;  // ppm -> Gas > 300 ALARM BAHAYA

// Variabel Settings dari Server
float suhuMax = 25.0;
float kelembapanMax = 70.0;
int gasThreshold = 1500;
String modeFan = "auto";
bool statusFanManual = false;

// Inisialisasi Objek Sensor
DHT dht(DHTPIN, DHTTYPE);
unsigned long lastSendTime = 0;
unsigned long lastSettingsTime = 0;
const unsigned long SETTINGS_INTERVAL_MS = 5000;

// =================== SETUP ===================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n==============================================");
  Serial.println("  TobaccoGuard IoT - ESP32 Warehouse Monitor  ");
  Serial.println("==============================================");

  // Inisialisasi GPIO
  pinMode(RELAY_FAN_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(GAS_PIN, INPUT);

  // Default state: Kipas & Buzzer Mati
  digitalWrite(RELAY_FAN_PIN, RELAY_OFF);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);

  // Inisialisasi DHT
  dht.begin();
  Serial.println("[OK] Sensor DHT22 diinisialisasi.");

  // Hubungkan ke WiFi
  connectToWiFi();
}

// =================== LOOP UTAMA ===================
void loop() {
  // Cek dan pertahankan koneksi WiFi
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }

  // Pengambilan settings berbasis timer
  if (currentMillis - lastSettingsTime >= SETTINGS_INTERVAL_MS) {
    lastSettingsTime = currentMillis;
    if (WiFi.status() == WL_CONNECTED) {
      getSettingsFromServer();
    }
  }

  // Pengiriman data berbasis timer non-blocking
  if (currentMillis - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = currentMillis;
    processAndSendData();
  }
}

// =================== FUNGSI AMBIL SETTINGS ===================
void getSettingsFromServer() {
  HTTPClient http;
  http.begin(SETTINGS_URL);
  int httpResponseCode = http.GET();

  if (httpResponseCode == 200) {
    String payload = http.getString();
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, payload);

    if (!error && doc["success"] == true) {
      JsonObject data = doc["data"];
      suhuMax = data["suhu_max"] | suhuMax;
      kelembapanMax = data["kelembapan_max"] | kelembapanMax;
      gasThreshold = data["gas_threshold"] | gasThreshold;
      modeFan = data["mode_fan"].as<String>();
      statusFanManual = data["status_fan_manual"] | statusFanManual;
      Serial.println("[SETTINGS] Berhasil mengambil pengaturan terbaru.");
    }
  } else {
    Serial.printf("[SETTINGS] Gagal mengambil pengaturan (HTTP %d). Menggunakan nilai terakhir.\n", httpResponseCode);
  }
  http.end();
}

// =================== FUNGSI KONEKSI WIFI ===================
void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.printf("\n[WiFi] Menghubungkan ke: %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Blink LED saat mencoba koneksi
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_PIN, HIGH);
    Serial.println("\n[WiFi] Terhubung!");
    Serial.print("[WiFi] IP Address ESP32: ");
    Serial.println(WiFi.localIP());
  } else {
    digitalWrite(LED_PIN, LOW);
    Serial.println("\n[WiFi] Gagal terhubung. ESP32 tetap membaca sensor secara lokal.");
  }
}

// =================== FUNGSI BACA SENSOR & KIRIM API ===================
void processAndSendData() {
  // 1. Baca Sensor Suhu & Kelembapan DHT22
  float suhu = dht.readTemperature();
  float kelembapan = dht.readHumidity();

  // Validasi pembacaan DHT22
  if (isnan(suhu) || isnan(kelembapan)) {
    Serial.println("[WARN] Gagal membaca dari sensor DHT22! Menggunakan nilai simulasi aman.");
    suhu = 26.0;
    kelembapan = 65.0;
  }

  // 2. Baca Sensor Gas MQ-135 (ADC 0 - 4095)
  // Rumus konversi estimasi kasar sensor gas ke skala konsentrasi ppm
  int rawGas = analogRead(GAS_PIN);
  int gasPpm = map(rawGas, 0, 4095, 20, 500);

  // 3. Logika Otomatisasi Aktuator (Relay Kipas & Buzzer Alarm)
  bool statusFan = false;
  bool statusAlarm = false;

  // Aktifkan kipas berdasarkan mode (auto/manual)
  if (modeFan == "manual") {
    statusFan = statusFanManual;
    digitalWrite(RELAY_FAN_PIN, statusFan ? RELAY_ON : RELAY_OFF);
  } else {
    // Mode Auto
    if (suhu > suhuMax || kelembapan > kelembapanMax) {
      statusFan = true;
      digitalWrite(RELAY_FAN_PIN, RELAY_ON);
    } else {
      statusFan = false;
      digitalWrite(RELAY_FAN_PIN, RELAY_OFF);
    }
  }

  // Aktifkan alarm jika suhu kritis atau gas pekat terdeteksi
  if (suhu > THRESHOLD_TEMP_DANGER || gasPpm > THRESHOLD_GAS_DANGER || kelembapan < 45.0) {
    statusAlarm = true;
    digitalWrite(BUZZER_PIN, HIGH); // Bunyikan alarm buzzer
  } else {
    statusAlarm = false;
    digitalWrite(BUZZER_PIN, LOW);
  }

  // Tampilkan telemetri di Serial Monitor
  Serial.printf("\n[SENSORS] Suhu: %.2f °C | RH: %.2f %% | Gas: %d ppm | Kipas: %s | Alarm: %s\n",
                suhu, kelembapan, gasPpm,
                statusFan ? "ON" : "OFF",
                statusAlarm ? "BAHAYA" : "AMAN");

  // 4. Kirim Data ke Server Flask Backend jika WiFi terhubung
  if (WiFi.status() == WL_CONNECTED) {
    sendToServer(suhu, kelembapan, gasPpm, statusFan, statusAlarm);
  }
}

// =================== FUNGSI HTTP POST JSON ===================
void sendToServer(float suhu, float kelembapan, int gas, bool statusFan, bool statusAlarm) {
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  // Format Dokumen JSON
  StaticJsonDocument<256> doc;
  doc["suhu"] = round(suhu * 10.0) / 10.0;
  doc["kelembapan"] = round(kelembapan * 10.0) / 10.0;
  doc["gas"] = gas;
  doc["status_fan"] = statusFan;
  doc["status_alarm"] = statusAlarm;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  // Eksekusi POST
  int httpResponseCode = http.POST(jsonPayload);

  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.printf("[HTTP] POST Sukses (Code %d): %s\n", httpResponseCode, response.c_str());
  } else {
    Serial.printf("[HTTP] POST Gagal, Error: %s\n", http.errorToString(httpResponseCode).c_str());
  }

  http.end();
}
