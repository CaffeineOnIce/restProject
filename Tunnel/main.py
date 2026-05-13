#!/usr/bin/env python3
import os, time, requests, sys
from flask import Flask, jsonify

app = Flask(__name__)

SERVER_IP = "https://projrest.shares.zrok.io"

@app.route("/th", methods=["GET"])
def get_temp_hum():
    try:
        response = requests.get(f"{SERVER_IP}/th")
        server_data = response.json()
        return jsonify({"received": server_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/gas", methods=["GET"])
def get_gas():
    try:
        response = requests.get(f"{SERVER_IP}/gas")
        server_data = response.json()
        return jsonify({"received": server_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "online"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))