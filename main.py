import os
from dotenv import load_dotenv
from supabase import create_client, Client
from flask import Flask, jsonify, request

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

app = Flask(__name__)

@app.route("/fetch", methods=['POST'])
def process():
    res = supabase.table("process_data").select("*").order('id',desc=True).limit(1).execute()
    return (jsonify(res.data), 200)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)