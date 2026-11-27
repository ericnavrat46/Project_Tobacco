/*****************************************************************
 *  ESP32 TobaccoGuard – Kipas dengan Hysteresis + Kontrol Manual
 *  
 *  AUTO MODE:
 *    Kipas ON  jika SALAH SATU terjadi:
 *      - Suhu       >= batas atas (dari settings web)
 *      - Kelembapan >= batas atas (dari settings web)
 *      - Gas        >  gas_threshold
 *    Kipas OFF  jika SEMUA kondisi sudah aman (di bawah batas bawah):
 *      - Suhu       < (batas_atas - 2°C)
 *      - Kelembapan < (batas_atas - 5%)
 *      - Gas        <= (gas_threshold * 0.7)
 *
 *  MANUAL MODE:
 *    Kipas mengikuti perintah ON/OFF dari web UI
 *****************************************************************/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <ArduinoJson.h>

// =============================================================
// 1. Wi-Fi & Server Flask
// =============================================================
const char* WIFI_SSID     = "MUTIARA";
const char* WIFI_PASSWORD = "M4m4p4p4";

const char* SERVER_POST_URL = "http://192.168.18.6:5000/api/gudang";
const char* SERVER_FAN_URL  = "http://192.168.18.6:5000/api/gudang/fan_state";

// =============================================================
// 2. LCD I2C
// =============================================================
LiquidCrystal_I2C lcd(0x27, 16, 2);

// =============================================================
// 3. Pin ESP32
// =============================================================
#define MQ_PIN       34
#define DHTPIN       14
#define BUZZER_PIN   13
#define FAN_PIN      26
#define SDA_PIN      32
#define SCL_PIN      33

// =============================================================
// 4. DHT22
// =============================================================
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

// =============================================================
// 5. Logika pin relay (active-LOW + Open-Drain untuk relay 5V)
//    ON  -> OUTPUT LOW (tarik ke GND)
//    OFF -> INPUT (Hi-Z / lepas seperti kabel dicabut)
//           agar tegangan 5V relay tidak bocor ke GPIO 3.3V
// =============================================================
#define BUZZER_ON  LOW
#define BUZZER_OFF HIGH

void setFanPin(bool on) {
  if (on) {
    pinMode(FAN_PIN, OUTPUT);
    digitalWrite(FAN_PIN, LOW);   // Tarik ke GND -> Relay ON
  } else {
    pinMode(FAN_PIN, INPUT);      // Mode Hi-Z -> Relay OFF (putus arus dari 5V)
  }
}

// =============================================================
// 6. Threshold default (akan di-update dari server)
// =============================================================
float thresholdSuhuMin       = 20.0;   // Batas bawah suhu (OFF)
float thresholdSuhuMax       = 25.0;   // Kipas ON jika suhu >= ini
float thresholdKelembapanMin = 60.0;   // Batas bawah kelembapan (OFF)
float thresholdKelembapanMax = 70.0;   // Kipas ON jika kelembapan >= ini
int   thresholdGasMin        = 1050;   // Batas bawah gas (OFF)
int   thresholdGas           = 1500;   // Kipas ON jika gas > ini

// =============================================================
// 7. Timer
// =============================================================
unsigned long previousMillisSensor  = 0;
unsigned long previousMillisCommand = 0;
const unsigned long sensorInterval  = 1000;  // 1 detik
const unsigned long commandInterval = 2000;  // 2 detik

// =============================================================
// 8. Variabel global
// =============================================================
float lastTempC      = 0.0;
float lastHumidity   = 0.0;
int   lastGasValue   = 0;
bool  lastGasDanger  = false;

bool  manualMode     = false;   // false = AUTO, true = MANUAL
bool  fanStateManual = false;   // status fan saat MANUAL (true=ON)
bool  autoFanState   = false;   // status fan saat AUTO (hysteresis)

// =============================================================
// 9. Koneksi Wi-Fi
// =============================================================
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("[WiFi] Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 8000) {
    delay(250);
    Serial.print('.');
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected! IP:");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WiFi] Failed - will retry later");
  }
}

// =============================================================
// 10. Kirim data sensor ke server (POST)
// =============================================================
void sendDataToServer(float suhu, float kelembapan, int gas,
                      bool fanOn, bool alarmOn) {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) return;
  }

  HTTPClient http;
  http.setTimeout(800);
  http.begin(SERVER_POST_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = "{";
  payload += "\"suhu\":" + String(isnan(suhu) ? 0.0 : suhu, 1) + ",";
  payload += "\"kelembapan\":" + String(isnan(kelembapan) ? 0.0 : kelembapan, 1) + ",";
  payload += "\"gas\":" + String(gas) + ",";
  payload += "\"status_fan\":" + String(fanOn ? "true" : "false") + ",";
  payload += "\"status_alarm\":" + String(alarmOn ? "true" : "false");
  payload += "}";

  int httpCode = http.POST(payload);
  if (httpCode > 0) {
    Serial.printf("[POST] OK (%d)\n", httpCode);
  } else {
    Serial.printf("[POST] FAILED: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

// =============================================================
// 11. Buzzer handler
// =============================================================
void handleAlarm(bool gasDanger) {
  digitalWrite(BUZZER_PIN, gasDanger ? BUZZER_ON : BUZZER_OFF);
}

// =============================================================
// 12. Polling perintah + threshold dari server (GET)
// =============================================================
void fetchFanCommand() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) return;
  }

  HTTPClient http;
  http.setTimeout(800);
  http.begin(SERVER_FAN_URL);
  int httpCode = http.GET();

  if (httpCode != HTTP_CODE_OK) {
    Serial.printf("[GET] Failed (%d): %s\n", httpCode,
                  http.errorToString(httpCode).c_str());
    http.end();
    return;
  }

  String body = http.getString();
  http.end();

  Serial.println("[GET] " + body);

  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    Serial.printf("[JSON] Parse error: %s\n", err.c_str());
    return;
  }

  // --- Update threshold dari server ---
  if (doc.containsKey("suhu_min"))
    thresholdSuhuMin = doc["suhu_min"].as<float>();
  if (doc.containsKey("suhu_max"))
    thresholdSuhuMax = doc["suhu_max"].as<float>();
  if (doc.containsKey("kelembapan_min"))
    thresholdKelembapanMin = doc["kelembapan_min"].as<float>();
  if (doc.containsKey("kelembapan_max"))
    thresholdKelembapanMax = doc["kelembapan_max"].as<float>();
  if (doc.containsKey("gas_min"))
    thresholdGasMin = doc["gas_min"].as<int>();
  if (doc.containsKey("gas_threshold"))
    thresholdGas = doc["gas_threshold"].as<int>();

  // --- Update mode ---
  const char* modeCmd = doc["mode"];
  bool modeChanged = false;
  if (modeCmd) {
    bool newManual = (strcasecmp(modeCmd, "MANUAL") == 0);
    if (newManual != manualMode) {
      manualMode = newManual;
      modeChanged = true;
      Serial.printf("[Mode] -> %s\n", manualMode ? "MANUAL" : "AUTO");
      if (manualMode) {
        autoFanState = false; // Reset state hysteresis saat masuk MANUAL
      } else {
        fanStateManual = false;
      }
    }
  }

  // --- Update fan (hanya berlaku saat MANUAL) ---
  const char* fanCmd = doc["fan"];
  if (fanCmd && manualMode) {
    bool newFanState = (strcasecmp(fanCmd, "ON") == 0);
    if (modeChanged || newFanState != fanStateManual) {
      fanStateManual = newFanState;
      setFanPin(fanStateManual);
      Serial.printf("[Fan MANUAL] -> %s (%s)\n",
                    fanStateManual ? "ON" : "OFF",
                    fanStateManual ? "OUTPUT LOW" : "INPUT Hi-Z");
    }
  }
}

// =============================================================
// 13. Logika AUTO: kipas dengan hysteresis
// =============================================================
void updateAutoFan(float suhu, float kelembapan, int gas) {
  // --- Kondisi NYALA (salah satu terpenuhi) ---
  bool shouldTurnOn = (suhu >= thresholdSuhuMax) ||
                      (kelembapan >= thresholdKelembapanMax) ||
                      (gas > thresholdGas);

  // --- Kondisi MATI (SEMUA harus aman, di bawah batas minimal dari web) ---
  float offSuhu = thresholdSuhuMin;
  float offKelembapan = thresholdKelembapanMin;
  int   offGas  = thresholdGasMin;

  bool shouldTurnOff = (suhu <= offSuhu) &&
                       (kelembapan <= offKelembapan) &&
                       (gas <= offGas);

  // --- Hysteresis: hanya ubah state jika melewati batas ---
  if (shouldTurnOn && !autoFanState) {
    autoFanState = true;
    Serial.printf("[Fan AUTO] ON  (S:%.1f>=%0.1f | H:%.1f>=%0.1f | G:%d>%d)\n",
                  suhu, thresholdSuhuMax, kelembapan, thresholdKelembapanMax, gas, thresholdGas);
  } else if (shouldTurnOff && autoFanState) {
    autoFanState = false;
    Serial.printf("[Fan AUTO] OFF (S:%.1f<%.1f & H:%.1f<%.1f & G:%d<=%d)\n",
                  suhu, offSuhu, kelembapan, offKelembapan, gas, offGas);
  }

  // Terapkan ke pin
  setFanPin(autoFanState);
}

// =============================================================
// 14. Setup
// =============================================================
void setup() {
  Serial.begin(115200);
  delay(800);

  Serial.println("\n=== TobaccoGuard ESP32 (Hysteresis) ===");

  // Pin output - mulai dalam kondisi OFF
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, BUZZER_OFF);
  setFanPin(false);   // Kipas MATI saat boot (Hi-Z)
  pinMode(MQ_PIN, INPUT);

  // I2C + LCD
  Wire.begin(SDA_PIN, SCL_PIN);
  lcd.init();
  lcd.backlight();
  lcd.clear();

  // DHT22
  dht.begin();

  // Wi-Fi & sinkronisasi awal dari server
  connectWiFi();
  fetchFanCommand();

  // Tampilan awal LCD
  lcd.setCursor(0, 0);
  lcd.print("System Ready");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.status() == WL_CONNECTED ? "WiFi OK" : "WiFi OFF");
  delay(1200);
  lcd.clear();

  Serial.println("[Setup] Done");
  Serial.printf("[Threshold] Suhu: %.1f..%.1f | Hum: %.1f..%.1f | Gas: %d..%d\n",
                thresholdSuhuMin, thresholdSuhuMax,
                thresholdKelembapanMin, thresholdKelembapanMax,
                thresholdGasMin, thresholdGas);
}

// =============================================================
// 15. Loop utama
// =============================================================
void loop() {
  unsigned long now = millis();

  // ---- 1. Baca sensor tiap 1 detik ----
  if (now - previousMillisSensor >= sensorInterval) {
    previousMillisSensor = now;

    float tempC    = dht.readTemperature();
    float humidity = dht.readHumidity();
    int   gasValue = analogRead(MQ_PIN);
    bool  gasDanger = (gasValue > thresholdGas);

    // Simpan nilai valid
    if (!isnan(tempC))    lastTempC    = tempC;
    if (!isnan(humidity)) lastHumidity = humidity;
    lastGasValue  = gasValue;
    lastGasDanger = gasDanger;

    // Buzzer (hanya untuk gas bahaya)
    handleAlarm(gasDanger);

    // === KONTROL KIPAS ===
    if (!manualMode) {
      // AUTO: gunakan hysteresis berdasarkan suhu, kelembapan, gas
      updateAutoFan(lastTempC, lastHumidity, gasValue);
    } else {
      // MANUAL: pastikan pin fisik selalu sesuai perintah manual dari web
      setFanPin(fanStateManual);
    }

    // Status fan saat ini untuk tampilan & pengiriman
    bool fanOnNow = manualMode ? fanStateManual : autoFanState;

    // Serial log
    Serial.printf("S:%.1fC H:%.1f%% G:%d | Mode:%s Fan:%s\n",
                  lastTempC, lastHumidity, gasValue,
                  manualMode ? "MAN" : "AUTO",
                  fanOnNow ? "ON" : "OFF");

    // Update LCD
    lcd.clear();
    if (gasDanger) {
      lcd.setCursor(0, 0);
      lcd.print("!! GAS BAHAYA !!");
      lcd.setCursor(0, 1);
      lcd.print("G:");
      lcd.print(gasValue);
      lcd.print(" F:");
      lcd.print(fanOnNow ? "ON" : "OFF");
    } else {
      lcd.setCursor(0, 0);
      lcd.print("T:");
      lcd.print(lastTempC, 1);
      lcd.print("C H:");
      lcd.print((int)lastHumidity);
      lcd.print("%");
      lcd.setCursor(0, 1);
      lcd.print("G:");
      lcd.print(gasValue);
      lcd.print(" F:");
      lcd.print(fanOnNow ? "ON" : "OFF");
    }

    // Kirim data ke server
    sendDataToServer(lastTempC, lastHumidity, gasValue, fanOnNow, gasDanger);
  }

  // ---- 2. Polling perintah HTTP tiap 2 detik ----
  if (now - previousMillisCommand >= commandInterval) {
    previousMillisCommand = now;
    fetchFanCommand();
  }

  delay(10);
}
