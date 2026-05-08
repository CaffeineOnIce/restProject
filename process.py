#!/usr/bin/env python3
import os, time, requests, statistics
from supabase import create_client
from dotenv import load_dotenv

load_dotenv(".env")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

ESP32_URL = os.getenv("ESP32_URL", "http://192.168.29.192")
POLL_INTERVAL = 2

def fetch_from_esp32(samples=5):
    temps, hums = [], []
    for _ in range(samples):
        resp = requests.get(f"{ESP32_URL}/trigger", timeout=10)
        data = resp.json()
        if "temperature" in data and "humidity" in data:
            temps.append(data["temperature"])
            hums.append(data["humidity"])
        time.sleep(0.5)
    
    if len(temps) < 3:
        return None, None
    return round(statistics.mean(temps), 2), round(statistics.mean(hums), 2)

def poll_supabase():
    while True:
        pending = supabase.table("fetch_jobs").select("*").eq("status", "pending").order("created_at").limit(1).execute().data
        
        if not pending:
            time.sleep(POLL_INTERVAL)
            continue
        
        job = pending[0]
        job_id = job["id"]
        
        supabase.table("fetch_jobs").update({"status": "processing"}).eq("id", job_id).execute()
        
        avg_t, avg_h = fetch_from_esp32()
        
        if avg_t is not None:
            supabase.table("fetch_jobs").update({
                "status": "completed",
                "avg_temp": avg_t,
                "avg_hum": avg_h,
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }).eq("id", job_id).execute()
        else:
            supabase.table("fetch_jobs").update({
                "status": "error",
                "error_msg": "Failed to read sensor",
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }).eq("id", job_id).execute()
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    poll_supabase()