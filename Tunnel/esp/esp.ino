#include <Arduino.h>
#include <DHT.h>
#include <ESPmDNS.h>
#include <MQUnifiedsensor.h>
#include <WebServer.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiMulti.h>

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

WiFiMulti wifiMulti;
const uint32_t connectTimeoutMs = 10000;
const char *hostname = "esp32";

void handleTempHum()
{
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t) || isnan(h))
  {
    server.send(500, "application/json", "{\"error\":\"Sensor read failed\"}");
    return;
  }
  String json = "{\"temperature\":" + String(t, 1) + ",\"humidity\":" + String(h, 1) + "}";
  server.send(200, "application/json", json);
}

void handleGas()
{
  MQ135.update();
  float correctionFactor = 0;
  
  MQ135.setA(110.47); 
  MQ135.setB(-2.862); 
  
  float gasVal = MQ135.readSensor(false, correctionFactor) + 400;

  String json = "{\"gas\":" + String(gasVal, 1) + "}";
  server.send(200, "application/json", json);
}

void healthInfo()
{
  server.send(200, "application/json", "{\"status\":\"ok\"}");
}

void setup()
{
  Serial.begin(115200);

  delay(2000);

  dht.begin();
  analogSetWidth(12);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(100);

  wifiMulti.addAP("BoxRouter", "routerBox1290");
  wifiMulti.addAP("TP-Link_3BCA", "65591574");

  Serial.print("Connecting to WiFi");
  while (wifiMulti.run() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected! IP: " + WiFi.localIP().toString());

  if (!MDNS.begin(hostname))
  {
    Serial.println("Error starting mDNS");
  }
  else
  {
    MDNS.addService("http", "tcp", 80);
    Serial.println("mDNS started: http://esp32.local");
  }

  // MQ-135 Setup
  MQ135.setRegressionMethod(1); //_PPM =  a*ratio^b
  
  // Configure the pin of arduino as input.
  MQ135.init(); 
  
  // Set RL value (Kept your 4.7K assumption)
  MQ135.setRL(4.7);

  Serial.print("Calibrating please wait.");
  float calcR0 = 0;
  for (int i = 1; i <= 10; i++)
  {
    MQ135.update(); // Update data, the arduino will read the voltage from the analog pin
    calcR0 += MQ135.calibrate(RatioMQ135CleanAir);
    Serial.print(".");
  }
  MQ135.setR0(calcR0 / 10);
  Serial.println("  done!.");
  
  // Safety checks from the working example to catch wiring/hardware issues
  if (isinf(calcR0)) {
    Serial.println("Warning: Connection issue, R0 is infinite (Open circuit detected) please check your wiring and supply"); 
    while (1);
  }
  if (calcR0 == 0) {
    Serial.println("Warning: Connection issue found, R0 is zero (Analog pin shorts to ground) please check your wiring and supply"); 
    while (1);
  }
  
  Serial.println("** Values from MQ-135 **");

  server.on("/temphum", HTTP_GET, handleTempHum);
  server.on("/gas", HTTP_GET, handleGas);
  server.on("/health", HTTP_GET, healthInfo);
  server.begin();
  Serial.println("HTTP server online.");
}

void loop()
{
  if (WiFi.status() != WL_CONNECTED)
  {
    Serial.println("WiFi disconnected. Reconnecting...");
    wifiMulti.run(connectTimeoutMs);
  }

  server.handleClient();
}
