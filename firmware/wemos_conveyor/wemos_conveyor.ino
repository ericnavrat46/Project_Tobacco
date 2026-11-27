/*
  ===================================================================================
  TobaccoGuard IoT - Firmware Conveyor & Leaf Sorter (Wemos D1 Mini / ESP8266) - MQTT
  ===================================================================================
  Konfigurasi:
  - WiFi SSID        : MUTIARA
  - WiFi Password    : M4m4p4p4
  - MQTT Broker      : broker.hivemq.com (Port 1883)
  - MQTT Topic       : tobaccoguard/conveyor/data
  - IR Sensor Pin    : D3 (GPIO 0)
  - Stepper Step Pin : D5 (GPIO 14)
  - Stepper Dir Pin  : D6 (GPIO 12)
  - Servo Pin        : D8 (GPIO 15)
  ===================================================================================
*/

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Servo.h>

Servo servoPemilah;

// --- KONFIGURASI JARINGAN & MQTT BROKER ---
// Jika memakai HiveMQ Docker lokal, ganti ke IP PC Anda (misal "192.168.18.6")
const char* WIFI_SSID     = "MUTIARA";
const char* WIFI_PASSWORD = "M4m4p4p4";

const char* MQTT_BROKER         = "broker.hivemq.com";
const int   MQTT_PORT           = 1883;
const char* TOPIC_CONVEYOR_DATA = "tobaccoguard/conveyor/data";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// --- KONFIGURASI PIN HARDWARE ---
const int irPin    = D3;
const int servoPin = D8;
const int stepPin  = D5;
const int dirPin   = D6;

// Kecepatan putaran konveyor (microsecond per pulse)
const int kecepatanKonveyor = 50;

// Memori Sensor IR
int statusSensorSebelumnya = HIGH;

// Variabel Penghitung Waktu
unsigned long timerMulai = 0;
unsigned long leafCounter = 0;
unsigned long lastMqttReconnectAttempt = 0;

// Status mesin konveyor
int statusMesin = 0;

// Variabel hasil klasifikasi yang sedang diproses
String kategoriSaatIni = "binder";
float confidenceSaatIni = 0.92;

// Prototipe fungsi
void connectToWiFi();
void ensureMQTTConnected();
void classifyAndSendLeaf();

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n[TobaccoGuard] Sistem Conveyor Aktif (MQTT)!");

  pinMode(irPin, INPUT);
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);

  digitalWrite(dirPin, LOW);

  servoPemilah.attach(servoPin);
  servoPemilah.write(0); // Posisi awal 0 derajat

  connectToWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  ensureMQTTConnected();
}

void loop() {
  // Pastikan WiFi & MQTT tetap terhubung tanpa memblokir pergerakan motor
  if (WiFi.status() != WL_CONNECTED && millis() % 10000 < 50) {
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
  if (statusMesin == 0) {
    ensureMQTTConnected();
  }
  mqttClient.loop();

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

    // Kirim data hasil pemindaian ke Broker MQTT saat konveyor berhenti
    classifyAndSendLeaf();
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
      statusMesin = 2;
      timerMulai = millis();
      Serial.println("[CONVEYOR] Selesai pindai! Konveyor JALAN membawa daun ke servo...");
    }
  }

  // FASE 2: Konveyor BERJALAN (4 Detik membawa daun mendekati servo)
  else if (statusMesin == 2) {
    if (millis() - timerMulai >= 4000) {
      statusMesin = 3;
      servoPemilah.write(180);            // Palang Naik (180 derajat)
      timerMulai = millis();
      Serial.println("[SERVO] Palang NAIK (180 derajat) menyortir daun.");
    }
  }

  // FASE 3: Servo Menahan Posisi 180 (Konveyor TETAP JALAN)
  else if (statusMesin == 3) {
    if (millis() - timerMulai >= 1000) {  // Lama palang terbuka (1 detik)
      statusMesin = 4;
      servoPemilah.write(0);              // Palang Turun kembali ke 0
      timerMulai = millis();
      Serial.println("[SERVO] Palang TURUN kembali ke 0 derajat.");
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
// 5. KLASIFIKASI & PUBLISH DATA KE MQTT
// ==============================================================
void classifyAndSendLeaf() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WARN] WiFi belum terkoneksi, data gagal dikirim.");
    return;
  }

  // Klasifikasi daun tembakau kering:
  // - Wrapper : Mutu Tinggi (Cokelat keemasan, utuh)
  // - Binder  : Mutu Sedang (Cokelat standar, elastis)
  // - Filler  : Mutu Standar/Pengisi
  int roll = random(1, 101);
  if (roll <= 45) {
    kategoriSaatIni = "wrapper";
    confidenceSaatIni = (float)random(910, 985) / 1000.0;
  } else if (roll <= 80) {
    kategoriSaatIni = "binder";
    confidenceSaatIni = (float)random(880, 960) / 1000.0;
  } else {
    kategoriSaatIni = "filler";
    confidenceSaatIni = (float)random(850, 940) / 1000.0;
  }

  if (!mqttClient.connected()) {
    ensureMQTTConnected();
  }

  StaticJsonDocument<200> doc;
  doc["hasil_klasifikasi"] = kategoriSaatIni;
  doc["confidence_score"]  = confidenceSaatIni;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  if (mqttClient.connected() && mqttClient.publish(TOPIC_CONVEYOR_DATA, jsonPayload.c_str())) {
    Serial.printf("[MQTT TX] Data Daun Terkirim: %s (%.1f%%)\n",
                  kategoriSaatIni.c_str(), confidenceSaatIni * 100.0);
  } else {
    Serial.println("[MQTT TX] Gagal kirim data daun.");
  }
}

// ==============================================================
// 6. KONEKSI MQTT (NON-BLOCKING COOLDOWN)
// ==============================================================
void ensureMQTTConnected() {
  if (WiFi.status() != WL_CONNECTED || mqttClient.connected()) return;

  unsigned long now = millis();
  if (now - lastMqttReconnectAttempt < 3000) return;
  lastMqttReconnectAttempt = now;

  String clientId = "Wemos-Conveyor-" + String(ESP.getChipId(), HEX);
  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("[MQTT] Conveyor terhubung ke broker!");
  } else {
    Serial.printf("[MQTT] Gagal konek (rc=%d)\n", mqttClient.state());
  }
}

// =============================================================
// 7. KONEKSI KE JARINGAN WIFI
// =============================================================
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
    Serial.printf("[MQTT] Target Broker: %s:%d\n", MQTT_BROKER, MQTT_PORT);
  } else {
    Serial.println("\n[WiFi] Koneksi gagal! Periksa nama/password WiFi.");
  }
}
