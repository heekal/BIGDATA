import os
import sqlite3

import pandas as pd

from utils_common import ensure_directories, write_pipeline_summary


def export_dashboard_table(db_path, table_name, output_path):
  conn = sqlite3.connect(db_path)
  df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
  conn.close()

  df.to_csv(output_path, index=False)
  return df


def main():
  ensure_directories()

  etl = export_dashboard_table(
    db_path="warehouse/warehouse_etl.db",
    table_name="dashboard_trip",
    output_path="dashboard_exports/dashboard_etl.csv"
  )

  elt = export_dashboard_table(
    db_path="warehouse/warehouse_elt.db",
    table_name="dashboard_trip",
    output_path="dashboard_exports/dashboard_elt.csv"
  )

  summary = write_pipeline_summary()

  print("Dashboard outputs created")
  print("ETL dashboard:", etl.shape, "-> dashboard_exports/dashboard_etl.csv")
  print("ELT dashboard:", elt.shape, "-> dashboard_exports/dashboard_elt.csv")
  print(summary)


if __name__ == "__main__":
  main()
