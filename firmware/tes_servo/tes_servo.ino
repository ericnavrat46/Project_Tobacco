#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <Servo.h>

// ================= KONFIGURASI WIFI & SERVER =================
const char* ssid     = "MUTIARA";
const char* password = "M4m4p4p4";

// IP Laptop/PC tempat Flask berjalan
const char* serverUrl = "http://192.168.18.7:5000/api/conveyor/latest";

// ================= KONFIGURASI PIN SERVO =================
const int PIN_SERVO1 = D1; // Servo 1 -> BINDER
const int PIN_SERVO2 = D2; // Servo 2 -> FILLER

Servo servoBinder;
Servo servoFiller;

// Posisi sudut Servo 1 / BINDER (MG996R)
const int BINDER_DIAM   = 0;
const int BINDER_DORONG = 180;

// Posisi sudut Servo 2 / FILLER (MG90S)
const int FILLER_DIAM   = 0;
const int FILLER_DORONG = 180;

// Menyimpan ID data terakhir agar tidak double trigger
int lastId = -1;

void setup() {
  Serial.begin(115200);

  servoBinder.attach(PIN_SERVO1);
  servoFiller.attach(PIN_SERVO2);
  servoBinder.write(BINDER_DIAM);
  servoFiller.write(FILLER_DIAM);

  WiFi.begin(ssid, password);
  Serial.print("Menghubungkan ke WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    Serial.print(WiFi.status()); // Tampilkan kode status (1=SSID tdk ada, 4=Password salah, 6=Connecting)
  }
  Serial.println("\nWiFi Terhubung! IP: " + WiFi.localIP().toString());
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;

    if (http.begin(client, serverUrl)) {
      int httpCode = http.GET();
      if (httpCode == HTTP_CODE_OK) {
        String payload = http.getString();

        // 1. Ambil ID data terbaru dari JSON
        int currentId = extractId(payload);

        // 2. Jalankan servo HANYA jika ada data baru (ID berbeda)
        if (currentId != -1 && currentId != lastId) {
          // Saat pertama kali nyala, simpan ID tanpa menggerakkan servo
          if (lastId == -1) {
            lastId = currentId;
            Serial.println("[INIT] Sinkronisasi ID awal: " + String(lastId));
          } else {
            lastId = currentId;
            String hasil = extractHasil(payload);
            Serial.println("\n[BARU] ID: " + String(currentId) + " | Hasil: " + hasil);

            // ================= LOGIKA IF / ELSE IF 2 SERVO =================
            if (hasil == "wrapper") {
              Serial.println("[SERVO] Wrapper -> Lolos (Kedua servo diam)");
            } 
            else if (hasil == "binder") {
              Serial.println("[SERVO] Binder -> Servo 1 JALAN");
              servoBinder.write(BINDER_DORONG);
              delay(500);
              servoBinder.write(BINDER_DIAM);
            } 
            else if (hasil == "filler") {
              Serial.println("[SERVO] Filler -> Servo 2 JALAN");
              servoFiller.write(FILLER_DORONG);
              delay(500);
              servoFiller.write(FILLER_DIAM);
            }
          }
        }
      }
      http.end();
    }
  }

  delay(500); // Cek data baru setiap 0.5 detik
}

// Helper: Ambil nilai "id": <angka> dari JSON
int extractId(String payload) {
  int idx = payload.indexOf("\"id\":");
  if (idx == -1) return -1;
  int start = idx + 5;
  int end = payload.indexOf(",", start);
  if (end == -1) end = payload.indexOf("}", start);
  String idStr = payload.substring(start, end);
  idStr.trim();
  return idStr.toInt();
}

// Helper: Ambil nilai "hasil_klasifikasi" dari JSON
String extractHasil(String payload) {
  if (payload.indexOf("\"wrapper\"") != -1) return "wrapper";
  if (payload.indexOf("\"binder\"") != -1)  return "binder";
  if (payload.indexOf("\"filler\"") != -1)  return "filler";
  return "";
}
