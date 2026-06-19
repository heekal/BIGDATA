import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import sqlite3
import time

import numpy as np
import pandas as pd

from utils_common import (
  add_normalized_columns,
  build_star_schema,
  ensure_directories,
  haversine_scalar
)


def main():
  ensure_directories()
  start = time.time()

  conn = sqlite3.connect("warehouse/warehouse_elt.db")
  conn.create_function("HAVERSINE_KM", 4, haversine_scalar)

  with open("elt_pipeline/02_transform_elt.sql", "r", encoding="utf-8") as file:
    sql = file.read()

  conn.executescript(sql)

  df = pd.read_sql_query("SELECT * FROM elt_trip_analysis", conn)
  df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce")
  df["distance_km"] = df["distance_km"].fillna(df["distance_km"].median())
  df["speed_kmh"] = pd.to_numeric(df["speed_kmh"], errors="coerce")
  df["speed_kmh"] = df["speed_kmh"].replace([np.inf, -np.inf], np.nan)
  df["speed_kmh"] = df["speed_kmh"].fillna(df["speed_kmh"].median())
  df = add_normalized_columns(df)

  df.to_sql("elt_trip_analysis", conn, if_exists="replace", index=False)
  df.to_csv("outputs/elt/elt_sql_transformed_data.csv", index=False)

  conn.commit()
  conn.close()

  result = build_star_schema(
    source_df=df,
    db_path="warehouse/warehouse_elt.db",
    source_pipeline="ELT",
    include_elt_alias=False
  )

  log = pd.DataFrame([{
    "pipeline": "ELT",
    "process": "elt_transform",
    "status": "success",
    "output_table": "elt_trip_analysis",
    "output_path": "outputs/elt/elt_sql_transformed_data.csv",
    "output_database": "warehouse/warehouse_elt.db",
    "rows": len(df),
    **result,
    "execution_time_seconds": round(time.time() - start, 4)
  }])

  log.to_csv("elt_pipeline/logs/elt_transform_log.csv", index=False)

  print("ELT transform success")
  print(log)


if __name__ == "__main__":
  main()
