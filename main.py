#!/usr/bin/env python3
import os, time
from flask import Flask, jsonify
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

POLL_INTERVAL = 1
TIMEOUT = 60

@app.route("/fetch", methods=["POST"])
def fetch():
    job = supabase.table("fetch_jobs").insert({"status": "pending"}).execute().data[0]
    job_id = job["id"]
    
    for _ in range(TIMEOUT // POLL_INTERVAL):
        time.sleep(POLL_INTERVAL)
        result = supabase.table("fetch_jobs").select("*").eq("id", job_id).execute().data[0]
        if result["status"] == "completed":
            return jsonify({"avg_temp": result["avg_temp"], "avg_hum": result["avg_hum"]}), 200
        if result["status"] == "error":
            return jsonify({"error": result["error_msg"]}), 500
    
    supabase.table("fetch_jobs").update({"status": "error", "error_msg": "Timeout"}).eq("id", job_id).execute()
    return jsonify({"error": "Request timed out"}), 504

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200