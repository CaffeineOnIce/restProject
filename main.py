import os
from dotenv import load_dotenv
from supabase import create_client
from flask import Flask, jsonify

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status": "API running", "endpoints": ["/latest"]}), 200

@app.route("/latest", methods=["GET"])
def get_latest():
    res = supabase.table("processed_data").select("*").order("id", desc=True).limit(1).execute()
    return jsonify(res.data[0]), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)