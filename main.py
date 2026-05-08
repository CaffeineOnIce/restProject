#!/usr/bin/env python3
import os, time
from flask import Flask, jsonify
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
if not url or not key:
    raise ValueError("Missing Supabase Environment Variables")

supabase = create_client(url, key)

POLL_INTERVAL = 1
TIMEOUT = 25 

@app.route("/th", methods=["POST"])
def get_temp_hum():
    try:
        # Insert job
        res = supabase.table("temphum").insert({"status": "pending"}).execute()
        if not res.data:
            return jsonify({"error": "Failed to create job"}), 500
            
        job_id = res.data[0]["id"]
        
        # Poll for result
        for _ in range(TIMEOUT):
            time.sleep(POLL_INTERVAL)
            result = supabase.table("temphum").select("*").eq("id", job_id).execute().data[0]
            
            if result["status"] == "completed":
                return jsonify({"temp": result["temp"], "hum": result["hum"]}), 200
            if result["status"] == "error":
                return jsonify({"error": result["error_msg"]}), 500
        
        # Cleanup on timeout
        supabase.table("temphum").update({"status": "error", "error_msg": "Bridge Timeout"}).eq("id", job_id).execute()
        return jsonify({"error": "ESP32 did not respond in time"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/gas", methods=["POST"])
def get_gas():
    try:
        res = supabase.table("gasval").insert({"status": "pending"}).execute()
        if not res.data:
            return jsonify({"error": "Failed to create job"}), 500
            
        job_id = res.data[0]["id"]
        
        for _ in range(TIMEOUT):
            time.sleep(POLL_INTERVAL)
            result = supabase.table("gasval").select("*").eq("id", job_id).execute().data[0]
            
            if result["status"] == "completed":
                return jsonify({"gas": result["gas"]}), 200
            if result["status"] == "error":
                return jsonify({"error": result["error_msg"]}), 500
        
        supabase.table("gasval").update({"status": "error", "error_msg": "Bridge Timeout"}).eq("id", job_id).execute()
        return jsonify({"error": "ESP32 did not respond in time"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "online"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))