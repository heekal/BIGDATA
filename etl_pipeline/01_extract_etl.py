import os
import time
import shutil
import requests
import pandas as pd
from io import StringIO
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = "raw"
LOG_DIR = "etl_pipeline/logs"

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

def extract_etl_source1():
  start = time.time()

  source_path = "raw/taxi.csv"
  output_path = "raw/etl_taxi_raw.csv"

  df = pd.read_csv(source_path)
  shutil.copy(source_path, output_path)

  return {
    "source_name": "taxi_trip",
    "source_type": "file_csv",
    "rows": df.shape[0],
    "columns": df.shape[1],
    "file_size_bytes": os.path.getsize(output_path),
    "execution_time_seconds": round(time.time() - start, 4)
  }

def extract_etl_source2():
  start = time.time()

  weather_api_url = os.getenv("WEATHER_API_URL")

  if not weather_api_url:
    raise ValueError("WEATHER_API_URL belum ada di file .env")

  response = requests.get(weather_api_url, timeout=60)
  response.raise_for_status()

  df = pd.read_csv(StringIO(response.text))

  output_path = "raw/etl_weather_raw.csv"
  df.to_csv(output_path, index=False)

  return {
    "source_name": "weather",
    "source_type": "api_csv",
    "rows": df.shape[0],
    "columns": df.shape[1],
    "file_size_bytes": os.path.getsize(output_path),
    "execution_time_seconds": round(time.time() - start, 4)
  }

if __name__ == "__main__":
  logs = [
    extract_etl_source1(),
    extract_etl_source2()
  ]

  log_df = pd.DataFrame(logs)
  log_df.to_csv("etl_pipeline/logs/extract_log.csv", index=False)

  print(log_df)