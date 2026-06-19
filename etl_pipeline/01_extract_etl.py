import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import os
import time
import shutil

import pandas as pd

from utils_common import ensure_directories, read_taxi_source, read_weather_source


def main():
  ensure_directories()
  start = time.time()

  taxi = read_taxi_source("raw/taxi.csv")
  weather, weather_source_type = read_weather_source("outputs/etl/raw_weather.csv")

  shutil.copy("raw/taxi.csv", "raw/etl_taxi_raw.csv")
  taxi.to_csv("outputs/etl/raw_taxi.csv", index=False)
  weather.to_csv("raw/etl_weather_raw.csv", index=False)

  logs = pd.DataFrame([
    {
      "pipeline": "ETL",
      "process": "extract_taxi",
      "source_name": "taxi_trip",
      "source_type": "file_csv",
      "output_path": "outputs/etl/raw_taxi.csv",
      "rows": taxi.shape[0],
      "columns": taxi.shape[1],
      "file_size_bytes": os.path.getsize("outputs/etl/raw_taxi.csv")
    },
    {
      "pipeline": "ETL",
      "process": "extract_weather",
      "source_name": "weather",
      "source_type": weather_source_type,
      "output_path": "outputs/etl/raw_weather.csv",
      "rows": weather.shape[0],
      "columns": weather.shape[1],
      "file_size_bytes": os.path.getsize("outputs/etl/raw_weather.csv")
    }
  ])

  logs["execution_time_seconds"] = round(time.time() - start, 4)
  logs.to_csv("etl_pipeline/logs/extract_log.csv", index=False)

  print("ETL extract success")
  print(logs)


if __name__ == "__main__":
  main()
