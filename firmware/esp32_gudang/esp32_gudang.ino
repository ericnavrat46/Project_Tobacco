/*****************************************************************
 *  ESP32 TobaccoGuard – Kontrol Kipas Gudang via MQTT
 *
 *  AUTO MODE:
 *    1. Gas >= gas_threshold                -> Buzzer ON, Kipas ON (respons asap)
 *    2. Sensor DHT22 gagal dibaca           -> Kipas OFF (pengamanan + peringatan)
 *    3. Suhu < suhu_min atau Hum < hum_min  -> Kipas OFF
 *    4. Suhu > suhu_max atau Hum > hum_max  -> Kipas ON
 *    5. Suhu & Hum dalam rentang optimal    -> Kipas OFF
 *
 *  MANUAL MODE:
 *    Kipas mengikuti perintah ON/OFF dari web UI secara real-time via MQTT
 *****************************************************************/

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <ArduinoJson.h>

// =============================================================
// 1. Wi-Fi & MQTT Broker
//    Jika memakai HiveMQ Docker lokal, ganti ke IP PC Anda (misal "192.168.18.6")
// =============================================================
const char* WIFI_SSID     = "MUTIARA";
const char* WIFI_PASSWORD = "M4m4p4p4";

const char* MQTT_BROKER   = "broker.hivemq.com";
const int   MQTT_PORT     = 1883;

const char* TOPIC_GUDANG_SENSOR  = "tobaccoguard/gudang/sensor";
const char* TOPIC_GUDANG_CONTROL = "tobaccoguard/gudang/fan_state";

WiFiClient espClient;
PubSubClient mqttClient(espClient);

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
// 6. Threshold default (otomatis ter-update via MQTT dari web)
// =============================================================
float thresholdSuhuMin       = 25.0;   // Batas bawah suhu
float thresholdSuhuMax       = 30.0;   // Batas atas suhu
float thresholdKelembapanMin = 40.0;   // Batas bawah kelembapan
float thresholdKelembapanMax = 50.0;   // Batas atas kelembapan
int   thresholdGasMin        = 1050;   // Batas bawah gas
int   thresholdGas           = 1500;   // Batas bahaya gas/asap

// =============================================================
// 7. Timer
// =============================================================
unsigned long previousMillisSensor    = 0;
unsigned long lastMqttReconnectAttempt  = 0;
const unsigned long sensorInterval    = 1000;  // Kirim sensor tiap 1 detik
const unsigned long reconnectInterval = 3000;  // Coba konek MQTT ulang tiap 3 detik

// =============================================================
// 8. Variabel global
// =============================================================
float lastTempC      = 0.0;
float lastHumidity   = 0.0;
int   lastGasValue   = 0;
bool  lastGasDanger  = false;

bool  manualMode     = false;   // false = AUTO, true = MANUAL
bool  fanStateManual = false;   // status fan saat MANUAL (true=ON)
bool  autoFanState   = false;   // status fan saat AUTO

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
// 10. Callback MQTT (menerima setting & perintah dari Web secara real-time)
// =============================================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String body;
  body.reserve(length + 1);
  for (unsigned int i = 0; i < length; i++) {
    body += (char)payload[i];
  }

  Serial.println("[MQTT RX] " + body);

  StaticJsonDocument<384> doc;
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
        autoFanState = false;
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
// 11. Reconnect MQTT (non-blocking cooldown)
// =============================================================
void ensureMQTTConnected() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (mqttClient.connected()) return;

  unsigned long now = millis();
  if (now - lastMqttReconnectAttempt < reconnectInterval) return;
  lastMqttReconnectAttempt = now;

  String clientId = "ESP32-Gudang-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  Serial.printf("[MQTT] Menghubungkan ke %s:%d...\n", MQTT_BROKER, MQTT_PORT);

  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("[MQTT] Terhubung!");
    mqttClient.subscribe(TOPIC_GUDANG_CONTROL, 1);
    Serial.printf("[MQTT] Subscribed: %s\n", TOPIC_GUDANG_CONTROL);
  } else {
    Serial.printf("[MQTT] Gagal konek (rc=%d)\n", mqttClient.state());
  }
}

// =============================================================
// 12. Publish data sensor ke MQTT
// =============================================================
void publishSensorData(float suhu, float kelembapan, int gas,
                       bool fanOn, bool alarmOn) {
  if (!mqttClient.connected()) return;

  String payload = "{";
  payload += "\"suhu\":" + String(isnan(suhu) ? 0.0 : suhu, 1) + ",";
  payload += "\"kelembapan\":" + String(isnan(kelembapan) ? 0.0 : kelembapan, 1) + ",";
  payload += "\"gas\":" + String(gas) + ",";
  payload += "\"status_fan\":" + String(fanOn ? "true" : "false") + ",";
  payload += "\"status_alarm\":" + String(alarmOn ? "true" : "false");
  payload += "}";

  if (mqttClient.publish(TOPIC_GUDANG_SENSOR, payload.c_str())) {
    Serial.println("[MQTT TX] Sensor terkirim");
  } else {
    Serial.println("[MQTT TX] Gagal kirim sensor");
  }
}

// =============================================================
// 13. Buzzer handler
// =============================================================
void handleAlarm(bool gasDanger) {
  digitalWrite(BUZZER_PIN, gasDanger ? BUZZER_ON : BUZZER_OFF);
}

// =============================================================
// 14. Logika AUTO: aturan kondisi gudang tembakau
// =============================================================
void updateAutoFan(float suhu, float kelembapan, int gas, bool dhtValid) {
  bool nextFanState = false;
  const char* reason = "OPTIMAL";

  if (gas >= thresholdGas) {
    // 1. Gas/Asap >= ambang batas -> buzzer ON dan kipas ON (respons asap pada prototipe)
    nextFanState = true;
    reason = "GAS_DANGER_FAN_ON";
  } else if (!dhtValid) {
    // 2. Sensor DHT22 gagal dibaca dan gas aman -> kipas OFF sebagai pengamanan
    nextFanState = false;
    reason = "DHT_ERROR_SAFE_OFF";
  } else if (suhu < thresholdSuhuMin || kelembapan < thresholdKelembapanMin) {
    // 3. Suhu < 25°C atau kelembapan < 40% -> kipas OFF
    nextFanState = false;
    reason = "LOW_TEMP_OR_HUM_OFF";
  } else if (suhu > thresholdSuhuMax || kelembapan > thresholdKelembapanMax) {
    // 4. Suhu > 30°C atau kelembapan > 50% -> kipas ON
    nextFanState = true;
    reason = "HIGH_TEMP_OR_HUM_ON";
  } else {
    // 5. Suhu 25-30°C dan kelembapan 40-50% (rentang optimal) -> kipas OFF
    nextFanState = false;
    reason = "OPTIMAL_OFF";
  }

  if (nextFanState != autoFanState) {
    autoFanState = nextFanState;
    Serial.printf("[Fan AUTO] %s (%s | S:%.1f [%.1f..%.1f] H:%.1f [%.1f..%.1f] G:%d/%d)\n",
                  autoFanState ? "ON" : "OFF", reason,
                  suhu, thresholdSuhuMin, thresholdSuhuMax,
                  kelembapan, thresholdKelembapanMin, thresholdKelembapanMax,
                  gas, thresholdGas);
  }

  setFanPin(autoFanState);
}

// =============================================================
// 15. Setup
// =============================================================
void setup() {
  Serial.begin(115200);
  delay(800);

  Serial.println("\n=== TobaccoGuard ESP32 Gudang (MQTT) ===");

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, BUZZER_OFF);
  setFanPin(false);
  pinMode(MQ_PIN, INPUT);

  Wire.begin(SDA_PIN, SCL_PIN);
  lcd.init();
  lcd.backlight();
  lcd.clear();

  dht.begin();

  connectWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setBufferSize(512);
  mqttClient.setCallback(mqttCallback);
  ensureMQTTConnected();

  lcd.setCursor(0, 0);
  lcd.print("System Ready");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.status() == WL_CONNECTED ? "WiFi+MQTT OK" : "WiFi OFF");
  delay(1200);
  lcd.clear();

  Serial.println("[Setup] Done");
}

// =============================================================
// 16. Loop utama
// =============================================================
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  ensureMQTTConnected();
  mqttClient.loop();

  unsigned long now = millis();
  if (now - previousMillisSensor >= sensorInterval) {
    previousMillisSensor = now;

    float tempC    = dht.readTemperature();
    float humidity = dht.readHumidity();
    int   gasValue = analogRead(MQ_PIN);
    bool  dhtValid = (!isnan(tempC) && !isnan(humidity));
    bool  gasDanger = (gasValue >= thresholdGas);

    if (dhtValid) {
      lastTempC    = tempC;
      lastHumidity = humidity;
    } else {
      Serial.println("[DHT22] Gagal membaca sensor! Kipas dimatikan (pengamanan).");
    }
    lastGasValue  = gasValue;
    lastGasDanger = gasDanger;

    handleAlarm(gasDanger);

    if (!manualMode) {
      updateAutoFan(lastTempC, lastHumidity, gasValue, dhtValid);
    } else {
      setFanPin(fanStateManual);
    }

    bool fanOnNow = manualMode ? fanStateManual : autoFanState;

    Serial.printf("S:%.1fC H:%.1f%% G:%d | Mode:%s Fan:%s\n",
                  lastTempC, lastHumidity, gasValue,
                  manualMode ? "MAN" : "AUTO",
                  fanOnNow ? "ON" : "OFF");

    lcd.clear();
    if (gasDanger) {
      lcd.setCursor(0, 0);
      lcd.print("!! GAS BAHAYA !!");
      lcd.setCursor(0, 1);
      lcd.print("G:");
      lcd.print(gasValue);
      lcd.print(" F:");
      lcd.print(fanOnNow ? "ON" : "OFF");
    } else if (!dhtValid) {
      lcd.setCursor(0, 0);
      lcd.print("DHT22 GAGAL BACA");
      lcd.setCursor(0, 1);
      lcd.print("F:");
      lcd.print(fanOnNow ? "ON" : "OFF");
      lcd.print(" (AMAN)");
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

    publishSensorData(lastTempC, lastHumidity, gasValue, fanOnNow, gasDanger);
  }

  delay(10);
}
