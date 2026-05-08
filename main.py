#!/usr/bin/env python3
import os, time
from flask import Flask, jsonify, request
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))
POLL_INTERVAL = 1  # seconds
TIMEOUT = 60       # seconds

@app.route("/fetch", methods=["POST"])
def fetch():
    # 1. Create job
    job = supabase.table("fetch_jobs").insert({"status": "pending"}).execute().data[0]
    job_id = job["id"]
    
    # 2. Poll for completion
    for _ in range(TIMEOUT // POLL_INTERVAL):
        time.sleep(POLL_INTERVAL)
        result = supabase.table("fetch_jobs").select("*").eq("id", job_id).execute().data[0]
        if result["status"] == "completed":
            return jsonify({"avg_temp": result["avg_temp"], "avg_hum": result["avg_hum"]}), 200
        if result["status"] == "error":
            return jsonify({"error": result["error_msg"]}), 500
    
    # 3. Timeout: mark as error
    supabase.table("fetch_jobs").update({"status": "error", "error_msg": "Timeout"}).eq("id", job_id).execute()
    return jsonify({"error": "Request timed out"}), 504

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))