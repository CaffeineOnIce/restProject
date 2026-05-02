import os
from dotenv import load_dotenv
from supabase import create_client, Client
from flask import Flask, jsonify, request

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)
res = supabase.table("processed_data").select("*").order('id',desc=True).limit(1).execute()