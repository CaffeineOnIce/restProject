#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <ArduinoJson.h> // 1. Added missing library

#define DHTPIN 4        
#define DHTTYPE DHT11 
DHT dht(DHTPIN, DHTTYPE);

const char* ssid = "BoxRouter";
const char* password = "routerBox1290";
const char* serverName = "http://192.168.29.115:5000/fetch";

void setup() {
  Serial.begin(115200);
  dht.begin(); // 2. Critical: Initialize DHT sensor

  WiFi.begin(ssid, password);
  Serial.print("Connecting");
  while(WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected!");
}

void loop() {
  if(WiFi.status() == WL_CONNECTED){
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();

    if (isnan(temperature) || isnan(humidity)) {
      Serial.println("⚠️ Failed to read from DHT sensor");
    } else {
      WiFiClient client;
      HTTPClient http;
      http.begin(client, serverName);
      http.addHeader("Content-Type", "application/json");

      JsonDocument doc; 
      doc["temperature"] = temperature;
      doc["humidity"] = humidity;

      String httpRequestData;
      serializeJson(doc, httpRequestData);

      int httpResponseCode = http.POST(httpRequestData);
     
      Serial.print("Sent JSON: ");
      Serial.println(httpRequestData);
      Serial.print("HTTP Response code: ");
      Serial.println(httpResponseCode);
        
      http.end();
    }
  } else {
    Serial.println("WiFi Disconnected");
  }
  delay(10000);
}
