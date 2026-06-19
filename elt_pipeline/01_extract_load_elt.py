import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import os
import sqlite3
import time

import pandas as pd

from utils_common import ensure_directories, read_taxi_source, read_weather_source


def main():
  ensure_directories()
  start = time.time()

  taxi = read_taxi_source("raw/taxi.csv")
  weather, weather_source_type = read_weather_source("datalake/weather_api_raw.csv")

  taxi.to_csv("datalake/taxi_raw.csv", index=False)
  weather.to_csv("datalake/weather_api_raw.csv", index=False)

  conn = sqlite3.connect("warehouse/warehouse_elt.db")
  taxi.to_sql("raw_taxi", conn, if_exists="replace", index=False)
  weather.to_sql("raw_weather", conn, if_exists="replace", index=False)
  conn.close()

  log = pd.DataFrame([{
    "pipeline": "ELT",
    "process": "elt_extract_load",
    "status": "success",
    "output_database": "warehouse/warehouse_elt.db",
    "taxi_source": "file_csv",
    "weather_source": weather_source_type,
    "taxi_output_path": "datalake/taxi_raw.csv",
    "weather_output_path": "datalake/weather_api_raw.csv",
    "taxi_rows": taxi.shape[0],
    "taxi_columns": taxi.shape[1],
    "weather_rows": weather.shape[0],
    "weather_columns": weather.shape[1],
    "execution_time_seconds": round(time.time() - start, 4)
  }])

  log.to_csv("elt_pipeline/logs/elt_extract_load_log.csv", index=False)

  print("ELT extract-load success")
  print(log)


if __name__ == "__main__":
  main()
