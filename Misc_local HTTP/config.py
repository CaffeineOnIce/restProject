import os
from dotenv import load_dotenv

load_dotenv(".env")

ESP32_URL = os.getenv("ESP32_URL", "esp32.local")

if not ESP32_URL.startswith("http://") and not ESP32_URL.startswith("https://"):
    ESP32_URL = f"http://{ESP32_URL}"
