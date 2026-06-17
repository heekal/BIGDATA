import os
import time
import sqlite3
import requests
import pandas as pd
from io import StringIO
from dotenv import load_dotenv

load_dotenv()

os.makedirs("datalake", exist_ok=True)
os.makedirs("elt_pipeline/logs", exist_ok=True)
os.makedirs("warehouse", exist_ok=True)

start = time.time()

weather_api_url = os.getenv("WEATHER_API_URL")

if not weather_api_url:
  raise ValueError("WEATHER_API_URL belum ada di file .env")

taxi = pd.read_csv("raw/taxi.csv")

response = requests.get(weather_api_url, timeout=60)
response.raise_for_status()

weather = pd.read_csv(StringIO(response.text))

taxi.to_csv("datalake/taxi_raw.csv", index=False)
weather.to_csv("datalake/weather_api_raw.csv", index=False)

conn = sqlite3.connect("warehouse/warehouse.db")

taxi.to_sql("raw_taxi", conn, if_exists="replace", index=False)
weather.to_sql("raw_weather", conn, if_exists="replace", index=False)

conn.close()

log = pd.DataFrame([{
  "process": "elt_extract_load",
  "status": "success",
  "taxi_source": "file_csv",
  "weather_source": "api_csv",
  "taxi_rows": taxi.shape[0],
  "taxi_columns": taxi.shape[1],
  "weather_rows": weather.shape[0],
  "weather_columns": weather.shape[1],
  "execution_time_seconds": round(time.time() - start, 4)
}])

log.to_csv("elt_pipeline/logs/elt_extract_load_log.csv", index=False)

print("ELT raw load success")
print(log)