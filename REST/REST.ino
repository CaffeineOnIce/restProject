#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <ArduinoJson.h>

#define DHTPIN 4
#define DHTTYPE DHT11
#define SLEEP_SECONDS 30

DHT dht(DHTPIN, DHTTYPE);
const char* ssid = "BoxRouter";
const char* password = "routerBox1290";
const char* piUrl = "http://DietPi.local:5000";  // ← Replace with Pi IP

void setup() {
  Serial.begin(115200);
  dht.begin();
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);
}

void loop() {
  // 1. Check for fetch command from Pi
  HTTPClient http;
  http.begin(piUrl + String("/cmd"));
  int code = http.GET();
  
  if (code == 200) {
    String resp = http.getString();
    DynamicJsonDocument doc(256);
    deserializeJson(doc, resp);
    
    // 2. If Pi says "fetch", collect 5 readings
    if (doc["action"] == "fetch") {
      JsonArray temps = doc["temps"].as<JsonArray>(); // Pi may send expected count
      for (int i = 0; i < 5; i++) {
        float t = dht.readTemperature();
        float h = dht.readHumidity();
        if (!isnan(t) && !isnan(h)) {
          DynamicJsonDocument payload(128);
          payload["temperature"] = t;
          payload["humidity"] = h;
          payload["seq"] = i;
          String json;
          serializeJson(payload, json);
          
          HTTPClient send;
          send.begin(piUrl + String("/data"));
          send.addHeader("Content-Type", "application/json");
          send.POST(json);
          send.end();
          delay(500); // small gap between readings
        }
      }
    }
  }
  http.end();
  
  // 3. Deep sleep until next check
  esp_sleep_enable_timer_wakeup(SLEEP_SECONDS * 1000000ULL);
  esp_deep_sleep_start();
}
