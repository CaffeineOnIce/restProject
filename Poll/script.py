#!/usr/bin/env python3
import os, time, requests, statistics
from supabase import create_client
from dotenv import load_dotenv

load_dotenv(".env")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

ESP32_URL = os.getenv("ESP32_URL", "esp32.local")
POLL_INTERVAL = 2

# --- SENSOR FETCHING FUNCTIONS ---
def fetch_temp_hum(samples=5):
    temps, hums = [], []
    for _ in range(samples):
        try:
            resp = requests.get(f"{ESP32_URL}/temphum", timeout=5)
            data = resp.json()
            if "temperature" in data and "humidity" in data:
                temps.append(data["temperature"])
                hums.append(data["humidity"])
        except Exception as e:
            print(f"Error fetching Temp/Hum: {e}")
        time.sleep(0.2)
    
    if len(temps) < 3: return None, None
    return round(statistics.mean(temps), 2), round(statistics.mean(hums), 2)

def fetch_gas(samples=5):
    gas_readings = []
    for _ in range(samples):
        try:
            resp = requests.get(f"{ESP32_URL}/gas", timeout=5)
            data = resp.json()
            if "gas" in data:
                gas_readings.append(data["gas"])
        except Exception as e:
            print(f"Error fetching Gas: {e}")
        time.sleep(0.2)
    
    if len(gas_readings) < 5: return None
    return round(statistics.mean(gas_readings), 2)

def process_temphum():
    pending = supabase.table("temphum").select("*").eq("status", "pending").order("created_at").limit(1).execute().data
    if not pending: return

    job = pending[0]
    job_id = job["id"]
    supabase.table("temphum").update({"status": "processing"}).eq("id", job_id).execute()

    t, h = fetch_temp_hum()
    if t is not None:
        supabase.table("temphum").update({
            "status": "completed",
            "temp": t,
            "hum": h,
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }).eq("id", job_id).execute()
    else:
        supabase.table("temphum").update({
            "status": "error", "error_msg": "Sensor timeout", "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }).eq("id", job_id).execute()

def process_gas():
    pending = supabase.table("gasval").select("*").eq("status", "pending").order("created_at").limit(1).execute().data
    if not pending: return

    job = pending[0]
    job_id = job["id"]
    supabase.table("gasval").update({"status": "processing"}).eq("id", job_id).execute()

    g = fetch_gas()
    if g is not None:
        supabase.table("gasval").update({
            "status": "completed",
            "gas": g,
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }).eq("id", job_id).execute()
    else:
        supabase.table("gasval").update({
            "status": "error", "error_msg": "Gas sensor timeout", "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }).eq("id", job_id).execute()

def main_loop():
    print("Cloud bridge active. Polling Supabase...")
    while True:
        process_temphum()
        process_gas()
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main_loop()