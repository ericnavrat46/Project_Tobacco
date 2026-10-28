#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>

// ==========================================================
// 1. KONFIGURASI WIFI & SERVER FLASK
// ==========================================================
const char* WIFI_SSID     = "MUTIARA";
const char* WIFI_PASSWORD = "M4m4p4p4";

// Alamat IP komputer server Anda (Port default 5000)
const char* SERVER_URL    = "http://192.168.18.6:5000/api/gudang";


// ==========================================================
// 2. LCD I2C
// ==========================================================
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ==========================================================
// 3. PIN ESP32
// ==========================================================
#define MQ_PIN       34
#define DHTPIN       14
#define BUZZER_PIN   13
#define FAN_PIN      22

// ==========================================================
// PIN I2C LCD
// ==========================================================
#define SDA_PIN      32
#define SCL_PIN      33

// ==========================================================
// DHT22
// ==========================================================
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

// ==========================================================
// BATAS GAS
// ==========================================================
#define GAS_THRESHOLD 1500

// ==========================================================
// LOGIKA BUZZER & FAN
// LOW  = ON
// HIGH = OFF
// ==========================================================
#define BUZZER_ON  LOW
#define BUZZER_OFF HIGH

#define FAN_ON  LOW
#define FAN_OFF HIGH

// ==========================================================
// TIMER SENSOR LOKAL
// ==========================================================
unsigned long previousMillisSensor = 0;
const unsigned long sensorInterval = 1000; // Baca sensor & update LCD tiap 1 detik

// Variabel penampung data sensor terakhir
float lastTempC = 0.0;
float lastHumidity = 0.0;
int lastGasValue = 0;
bool lastGasDanger = false;
bool lastFanState = true; // Default ON

// ==========================================================
// FUNGSI KONEKSI WIFI
// ==========================================================
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("[WiFi] Menghubungkan ke: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Berhasil Terhubung!");
    Serial.print("[WiFi] IP ESP32: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WiFi] Gagal terhubung (Timeout). Melanjutkan operasi lokal...");
  }
}

// ==========================================================
// FUNGSI PENGIRIMAN DATA KE SERVER FLASK (HTTP POST)
// ==========================================================
void sendDataToServer(float suhu, float kelembapan, int gas, bool fanOn, bool alarmOn) {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) return;
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  // Format data JSON untuk API backend Flask
  String payload = "{";
  payload += "\"suhu\":" + String(isnan(suhu) ? 0.0 : suhu, 1) + ",";
  payload += "\"kelembapan\":" + String(isnan(kelembapan) ? 0.0 : kelembapan, 1) + ",";
  payload += "\"gas\":" + String(gas) + ",";
  payload += "\"status_fan\":" + String(fanOn ? "true" : "false") + ",";
  payload += "\"status_alarm\":" + String(alarmOn ? "true" : "false");
  payload += "}";

  int httpCode = http.POST(payload);

  if (httpCode > 0) {
    Serial.print(">>> [SERVER POST] Sukses (HTTP ");
    Serial.print(httpCode);
    Serial.print(") Payload: ");
    Serial.println(payload);
  } else {
    Serial.print(">>> [SERVER POST] Gagal kirim: ");
    Serial.println(http.errorToString(httpCode).c_str());
  }

  http.end();
}

// ==========================================================
// FUNGSI BUZZER
// ==========================================================
void handleAlarm(bool gasDanger) {
  if (gasDanger) {
    // GAS BAHAYA
    digitalWrite(BUZZER_PIN, BUZZER_ON);
    Serial.println(">>> BUZZER : ON");
  } else {
    // GAS NORMAL
    digitalWrite(BUZZER_PIN, BUZZER_OFF);
    Serial.println(">>> BUZZER : OFF");
  }
}

// ==========================================================
// SETUP
// ==========================================================
void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("========================================");
  Serial.println("   SISTEM MONITORING ESP32 & WEB CLOUD  ");
  Serial.println("========================================");

  // Inisialisasi Pin Output
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, BUZZER_OFF);

  pinMode(FAN_PIN, OUTPUT);
  digitalWrite(FAN_PIN, FAN_ON); // Fan selalu ON

  pinMode(MQ_PIN, INPUT);

  // Inisialisasi I2C LCD
  Wire.begin(SDA_PIN, SCL_PIN);
  lcd.init();
  lcd.backlight();
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("Connecting WiFi");
  lcd.setCursor(0, 1);
  lcd.print(WIFI_SSID);

  // Inisialisasi Sensor DHT22
  dht.begin();

  // Koneksi ke WiFi
  connectWiFi();

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("System Ready...");
  lcd.setCursor(0, 1);
  if (WiFi.status() == WL_CONNECTED) {
    lcd.print("WiFi Connected");
  } else {
    lcd.print("WiFi Offline");
  }
  delay(1500);
  lcd.clear();

  Serial.println("System Ready!");
  Serial.println("----------------------------------------");
  Serial.print("Server Target : ");
  Serial.println(SERVER_URL);
  Serial.print("Gas Threshold : ");
  Serial.println(GAS_THRESHOLD);
  Serial.println("----------------------------------------");
}

// ==========================================================
// LOOP
// ==========================================================
void loop() {
  unsigned long currentMillis = millis();

  // ========================================================
  // 1. BACA SENSOR & TAMPILKAN KE LCD (Setiap 1 detik)
  // ========================================================
  if (currentMillis - previousMillisSensor >= sensorInterval) {
    previousMillisSensor = currentMillis;

    // BACA DHT22
    float tempC = dht.readTemperature();
    float humidity = dht.readHumidity();

    // BACA MQ SENSOR
    int gasValue = analogRead(MQ_PIN);

    // EVALUASI STATUS
    bool isGasDanger = (gasValue > GAS_THRESHOLD);

    // KONTROL FAN & BUZZER
    digitalWrite(FAN_PIN, FAN_ON);
    handleAlarm(isGasDanger);

    // Simpan ke variabel global jika pembacaan valid
    if (!isnan(tempC)) lastTempC = tempC;
    if (!isnan(humidity)) lastHumidity = humidity;
    lastGasValue = gasValue;
    lastGasDanger = isGasDanger;
    lastFanState = true;

    // STATUS BUZZER FISIK
    int buzzerState = digitalRead(BUZZER_PIN);

    // SERIAL MONITOR LOG
    Serial.println();
    Serial.println("----------------------------------------");
    Serial.print("Suhu        : ");
    if (isnan(tempC)) Serial.print("ERROR"); else { Serial.print(tempC, 1); Serial.print(" C"); }
    Serial.print(" | Kelembapan : ");
    if (isnan(humidity)) Serial.print("ERROR"); else { Serial.print(humidity, 1); Serial.print(" %"); }
    Serial.print(" | Gas : ");
    Serial.println(gasValue);

    Serial.print("Status Gas  : ");
    Serial.println(isGasDanger ? "!!! GAS TERDETEKSI !!!" : "NORMAL");

    Serial.print("Buzzer      : ");
    Serial.println((buzzerState == BUZZER_ON) ? "ON" : "OFF");
    Serial.println("Fan         : ON");

    // UPDATE DISPLAY LCD
    lcd.clear();
    if (isGasDanger) {
      lcd.setCursor(0, 0);
      lcd.print("!! GAS BAHAYA !!");
      lcd.setCursor(0, 1);
      lcd.print("Gas:");
      lcd.print(gasValue);
    } else {
      // Baris 1: Suhu & Kelembapan
      lcd.setCursor(0, 0);
      lcd.print("T:");
      if (isnan(tempC)) lcd.print(lastTempC, 1); else { lcd.print(tempC, 1); }
      lcd.print("C H:");
      if (isnan(humidity)) lcd.print((int)lastHumidity); else { lcd.print((int)humidity); }
      lcd.print("%");

      // Baris 2: Gas & Status Fan
      lcd.setCursor(0, 1);
      lcd.print("G:");
      lcd.print(gasValue);
      lcd.print(WiFi.status() == WL_CONNECTED ? " [W]" : " [!]");
      lcd.print(" Fan:ON");
    }

    // ========================================================
    // 2. KIRIM DATA KE SERVER WEB FLASK (SINKRON DENGAN SERIAL)
    // ========================================================
    // Dikirim langsung setiap siklus pembacaan (tiap 1 detik)
    sendDataToServer(lastTempC, lastHumidity, lastGasValue, lastFanState, lastGasDanger);
  }
}
