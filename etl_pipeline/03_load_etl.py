import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import time

import pandas as pd

from utils_common import build_star_schema, ensure_directories


def main():
  ensure_directories()
  start = time.time()

  df = pd.read_csv("outputs/etl/etl_cleaned_data.csv")
  result = build_star_schema(
    source_df=df,
    db_path="warehouse/warehouse_etl.db",
    source_pipeline="ETL",
    include_elt_alias=True
  )

  load_log = pd.DataFrame([{
    "pipeline": "ETL",
    "process": "etl_load",
    "status": "success",
    "output_database": "warehouse/warehouse_etl.db",
    **result,
    "execution_time_seconds": round(time.time() - start, 4)
  }])

  load_log.to_csv("etl_pipeline/logs/load_log.csv", index=False)

  print("ETL load success")
  print(load_log)


if __name__ == "__main__":
  main()
