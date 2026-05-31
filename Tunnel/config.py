import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ESP32_URL = os.getenv("ESP32_URL", "esp32.local")

if not ESP32_URL.startswith("http://") and not ESP32_URL.startswith("https://"):
    ESP32_URL = f"http://{ESP32_URL}"
