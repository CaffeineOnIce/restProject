#include <DHT.h>
#include <ESPmDNS.h>
#include <MQUnifiedsensor.h>
#include <WebServer.h>
#include <WiFi.h>

#define placa "ESP32"
#define Voltage_Resolution 3.3
#define pin 34
#define type "MQ-135"
#define ADC_Bit_Resolution 12
#define RatioMQ135CleanAir 3.6
#define DHTPIN 4
#define DHTTYPE DHT11

MQUnifiedsensor MQ135(placa, Voltage_Resolution, ADC_Bit_Resolution, pin, type);
DHT dht(DHTPIN, DHTTYPE);
WebServer server(80);

const char* ssid = "BoxRouter";
const char* password = "routerBox1290";

const char* hostname = "esp32";  // Access at esp32.local

void handleTempHum() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t) || isnan(h)) {
    server.send(500, "application/json", "{\"error\":\"Sensor read failed\"}");
    return;
  }
  String json = "{\"temperature\":" + String(t, 1) +
                ",\"humidity\":" + String(h, 1) + "}";
  server.send(200, "application/json", json);
}

void handleGas() {
  MQ135.update();
  float gasVal = MQ135.readSensor();

  // Fixed the missing '+' here
  String json = "{\"gas\":" + String(gasVal, 1) + "}";
  server.send(200, "application/json", json);
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected!");
  Serial.println(WiFi.localIP());

  if (!MDNS.begin(hostname)) {
    Serial.println("Error starting mDNS");
    return;
  }
  Serial.println("mDNS started: http://" + String(hostname) + ".local");

  // MQ-135 Setup
  MQ135.setRegressionMethod(1);
  MQ135.setA(110.47);  // CO2
  MQ135.setB(-2.862);
  MQ135.init();

  Serial.print("Calibrating MQ-135...");
  float calcR0 = 0;
  for (int i = 1; i <= 10; i++) {
    MQ135.update();
    calcR0 += MQ135.calibrate(RatioMQ135CleanAir);
    Serial.print(".");
    delay(100);
  }

  MQ135.setR0(calcR0 / 10);
  Serial.println(" Done!");

  if (isinf(calcR0) || calcR0 == 0) {
    Serial.println("Warning: Calibration failed. Check wiring.");
  }

  MQ135.serialDebug(false);

  server.on("/temphum", HTTP_GET, handleTempHum);
  server.on("/gas", HTTP_GET, handleGas);
  server.begin();
  Serial.println("HTTP server started");
}

void loop() { server.handleClient(); }
