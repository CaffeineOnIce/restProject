#!/usr/bin/env python3
import os, time, requests, statistics
from supabase import create_client
from dotenv import load_dotenv
from flask import Flask, jsonify 

load_dotenv(".env")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Ensure the URL is properly formatted with an HTTP prefix
ESP32_URL = os.getenv("ESP32_URL", "esp32.local")
if not ESP32_URL.startswith("http://") and not ESP32_URL.startswith("https://"):
    ESP32_URL = f"http://{ESP32_URL}"

app = Flask(__name__)

def handle_temp_hum(samples=5):
    temps, hums = [], []
    for _ in range(samples):
        try:
            resp = requests.get(f"{ESP32_URL}/temphum", timeout=5)
            data = resp.json()
            if "temperature" in data and "humidity" in data:
                temps.append(data["temperature"])
                hums.append(data["humidity"])
        except Exception as e:
            print(f"Temp/Hum fetch error: {e}")
        time.sleep(0.2)

    if len(temps) >= 3:
        result = {
            "status": "completed",
            "temp": round(statistics.mean(temps), 2),
            "hum": round(statistics.mean(hums), 2),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    else:
        result = {"status": "error", "error_msg": "Insufficient sensor data", "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}

    supabase.table("temphum").insert(result).execute()
    return {"temp": result.get("temp"), "hum": result.get("hum")}

def handle_gas(samples=5):
    gas_readings = []
    for _ in range(samples):
        try:
            resp = requests.get(f"{ESP32_URL}/gas", timeout=5)
            data = resp.json()
            if "gas" in data:
                gas_readings.append(data["gas"])
        except Exception as e:
            print(f"Gas fetch error: {e}")
        time.sleep(0.2)

    if len(gas_readings) >= 3:
        result = {
            "status": "completed",
            "gas": round(statistics.mean(gas_readings), 2),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    else:
        result = {"status": "error", "error_msg": "Insufficient sensor data", "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}

    supabase.table("gasval").insert(result).execute()
    return {"gas": result.get("gas")}

@app.route("/temphum", methods=["GET"])
def api_temphum():
    return jsonify(handle_temp_hum())

@app.route("/gas", methods=["GET"])
def api_gas():
    return jsonify(handle_gas())

if __name__ == "__main__":
    print("Server active. Waiting for requests on port 52471...")
    app.run(host="0.0.0.0", port=52471)
