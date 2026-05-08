#include <WiFi.h>
#include <WebServer.h>
#include <DHT.h>

#define DHTPIN 4
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);
WebServer server(80);
const char* ssid = "BoxRouter";
const char* password = "routerBox1290";

void handleTrigger() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t) || isnan(h)) {
    server.send(500, "application/json", "{\"error\":\"Sensor read failed\"}");
    return;
  }
  String json = "{\"temperature\":" + String(t, 1) + ",\"humidity\":" + String(h, 1) + "}";
  server.send(200, "application/json", json);
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  Serial.println(WiFi.localIP());
  server.on("/trigger", HTTP_GET, handleTrigger);
  server.begin();
}

void loop() {
  server.handleClient();
}
