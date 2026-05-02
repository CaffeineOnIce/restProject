import os
import threading
from flask import Flask, jsonify, request
from datetime import datetime, timezone
from supabase import create_client
from dotenv import load_dotenv
import statistics

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
app = Flask(__name__)

temp_history = []
hum_history = []
_lock = threading.Lock()

@app.route("/fetch", methods=["POST"])
def log_data():
    global temp_history, hum_history
    
    if not request.is_json:
        return jsonify({"error": "Expected JSON"}), 400

    data = request.get_json()
    temp = data.get("temperature")
    hum = data.get("humidity")

    if temp is None or hum is None:
        return jsonify({"error": "Missing fields"}), 400

    try:
        temp = float(temp)
        hum = float(hum)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numeric values"}), 400

    with _lock:
        temp_history.append(temp)
        hum_history.append(hum)

        if len(temp_history) >= 5:
            avg_temp = statistics.mean(temp_history)
            avg_hum = statistics.mean(hum_history)

            try:
                supabase.table("processed_data").insert({
                    "avg_temp": avg_temp,
                    "avg_hum": avg_hum
                }).execute()
                temp_history.clear()
                hum_history.clear()
            except Exception as e:
                print(f"Supabase insert failed: {e}")

    return jsonify({"status": "logged"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)