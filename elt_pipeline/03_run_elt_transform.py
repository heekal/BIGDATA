import os
import time
import sqlite3
import pandas as pd

os.makedirs("elt_pipeline/logs", exist_ok=True)

start = time.time()

conn = sqlite3.connect("warehouse/warehouse.db")

with open("elt_pipeline/02_transform_elt.sql", "r", encoding="utf-8") as file:
  sql = file.read()

conn.executescript(sql)

row_count = pd.read_sql_query(
  "SELECT COUNT(*) AS total_rows FROM elt_trip_analysis",
  conn
)["total_rows"].iloc[0]

conn.commit()
conn.close()

log = pd.DataFrame([{
  "process": "elt_transform",
  "status": "success",
  "output_table": "elt_trip_analysis",
  "rows": row_count,
  "execution_time_seconds": round(time.time() - start, 4)
}])

log.to_csv("elt_pipeline/logs/elt_transform_log.csv", index=False)

print("ELT transform success")
print(log)