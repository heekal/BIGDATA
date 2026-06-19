import sqlite3
import pandas as pd

# Paste this logic into the Power BI Python source for the ETL dashboard,
# or use make_dashboard_templates.py to patch the existing PBIT automatically.
db_path = r"warehouse/warehouse_etl.db"

conn = sqlite3.connect(db_path)

dashboard_trip = pd.read_sql_query("SELECT * FROM dashboard_trip", conn)
fact_trip = pd.read_sql_query("SELECT * FROM fact_trip", conn)
dim_time = pd.read_sql_query("SELECT * FROM dim_time", conn)
dim_vendor = pd.read_sql_query("SELECT * FROM dim_vendor", conn)
dim_weather = pd.read_sql_query("SELECT * FROM dim_weather", conn)
elt_trip_analysis = pd.read_sql_query("SELECT * FROM elt_trip_analysis", conn)

conn.close()
