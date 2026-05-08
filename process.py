#!/usr/bin/env python3
import os, time, requests, json, threading
from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv("/edge/.env")
app = Flask(__name__)

CLOUD_URL = os.getenv("CLOUD_URL")  # https://sampled.cv/flasktest
ESP32_IP = os.getenv("ESP32_IP")    # 192.168.1.100

latest_data = {}

def poll_cloud():
    """Poll HelioHost every 10s for fetch requests"""
    global latest_data
    while True:
        try:
            res = requests.get(f"{CLOUD_URL}/poll", timeout=5)
            fetch = res.json()
            
            if fetch and fetch.get("status") == "pending":
                fetch_id = fetch["fetch_id"]
                print(f"🔔 Fetch request: {fetch_id}")
                
                # Wake ESP32
                try:
                    wake_res = requests.get(f"http://{ESP32_IP}/wake", timeout=5)
                    print(f"✅ ESP32 woken: {wake_res.text}")
                except Exception as e:
                    print(f"❌ Failed to wake ESP32: {e}")
                    continue
                
                # Wait for ESP32 to collect 5 readings (~15s)
                time.sleep(15)
                
                # Get data from ESP32 (stored by /data endpoint)
                if latest_data:
                    avg_temp = latest_data.get("avg_temp", 0)
                    avg_hum = latest_data.get("avg_hum", 0)
                    
                    # Mark complete in cloud
                    try:
                        requests.post(
                            f"{CLOUD_URL}/complete/{fetch_id}",
                            json={"avg_temp": avg_temp, "avg_hum": avg_hum},
                            timeout=5
                        )
                        print(f"✅ Completed {fetch_id}: T={avg_temp}°C, H={avg_hum}%")
                    except Exception as e:
                        print(f"❌ Failed to complete: {e}")
                    
                    latest_data = {}
                else:
                    print("⚠️ No data from ESP32")
                    
        except Exception as e:
            print(f"Poll error: {e}")
        
        time.sleep(10)

@app.route("/data", methods=["POST"])
def receive_data():
    """ESP32 sends averaged data"""
    global latest_data
    data = request.get_json()
    latest_data = data
    print(f"📥 Received from ESP32: {data}")
    return jsonify({"status": "received"}), 200

if __name__ == "__main__":
    # Start polling thread
    threading.Thread(target=poll_cloud, daemon=True).start()
    print("🔌 RPi Edge started, polling cloud...")
    app.run(host="0.0.0.0", port=5000)