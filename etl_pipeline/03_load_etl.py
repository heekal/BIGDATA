import os
import time
import sqlite3
import pandas as pd

os.makedirs("warehouse", exist_ok=True)
os.makedirs("etl_pipeline/logs", exist_ok=True)

start = time.time()

df = pd.read_csv("warehouse/etl_cleaned_data.csv")

conn = sqlite3.connect("warehouse/warehouse.db")
conn.execute("PRAGMA foreign_keys = ON;")

conn.executescript("""
DROP TABLE IF EXISTS fact_trip;
DROP TABLE IF EXISTS dim_time;
DROP TABLE IF EXISTS dim_vendor;
DROP TABLE IF EXISTS dim_weather;

CREATE TABLE dim_time (
  time_id INTEGER PRIMARY KEY,
  pickup_date TEXT NOT NULL,
  pickup_hour INTEGER NOT NULL,
  pickup_day INTEGER NOT NULL
);

CREATE TABLE dim_vendor (
  vendor_key INTEGER PRIMARY KEY,
  vendor_id TEXT NOT NULL
);

CREATE TABLE dim_weather (
  weather_id INTEGER PRIMARY KEY,
  weather_date TEXT NOT NULL,
  temp REAL,
  feelslike REAL,
  humidity REAL,
  precip REAL,
  windspeed REAL,
  cloudcover REAL,
  visibility REAL
);

CREATE TABLE fact_trip (
  id TEXT PRIMARY KEY,
  time_id INTEGER NOT NULL,
  vendor_key INTEGER NOT NULL,
  weather_id INTEGER NOT NULL,
  passenger_count INTEGER,
  trip_duration REAL,
  duration_minutes REAL,
  distance_km REAL,
  speed_kmh REAL,
  is_rain INTEGER,
  temp_feelslike_diff REAL,
  store_and_fwd_flag_encoded INTEGER,
  trip_duration_norm REAL,
  distance_km_norm REAL,
  FOREIGN KEY (time_id) REFERENCES dim_time(time_id),
  FOREIGN KEY (vendor_key) REFERENCES dim_vendor(vendor_key),
  FOREIGN KEY (weather_id) REFERENCES dim_weather(weather_id)
);
""")

dim_time = df[[
  "pickup_date",
  "pickup_hour",
  "pickup_day"
]].drop_duplicates().reset_index(drop=True)

dim_time["time_id"] = range(1, len(dim_time) + 1)

dim_vendor = df[[
  "vendor_id"
]].drop_duplicates().reset_index(drop=True)

dim_vendor["vendor_key"] = range(1, len(dim_vendor) + 1)

dim_weather = df[[
  "weather_date",
  "temp",
  "feelslike",
  "humidity",
  "precip",
  "windspeed",
  "cloudcover",
  "visibility"
]].drop_duplicates().reset_index(drop=True)

dim_weather["weather_id"] = range(1, len(dim_weather) + 1)

fact = df.merge(
  dim_time,
  on=["pickup_date", "pickup_hour", "pickup_day"],
  how="left"
)

fact = fact.merge(
  dim_vendor,
  on=["vendor_id"],
  how="left"
)

fact = fact.merge(
  dim_weather,
  on=[
    "weather_date",
    "temp",
    "feelslike",
    "humidity",
    "precip",
    "windspeed",
    "cloudcover",
    "visibility"
  ],
  how="left"
)

fact_trip = fact[[
  "id",
  "time_id",
  "vendor_key",
  "weather_id",
  "passenger_count",
  "trip_duration",
  "duration_minutes",
  "distance_km",
  "speed_kmh",
  "is_rain",
  "temp_feelslike_diff",
  "store_and_fwd_flag_encoded",
  "trip_duration_norm",
  "distance_km_norm"
]]

dim_time.to_sql("dim_time", conn, if_exists="append", index=False)
dim_vendor.to_sql("dim_vendor", conn, if_exists="append", index=False)
dim_weather.to_sql("dim_weather", conn, if_exists="append", index=False)
fact_trip.to_sql("fact_trip", conn, if_exists="append", index=False)

conn.commit()
conn.close()

load_log = pd.DataFrame([{
  "process": "etl_load",
  "status": "success",
  "fact_rows": len(fact_trip),
  "dim_time_rows": len(dim_time),
  "dim_vendor_rows": len(dim_vendor),
  "dim_weather_rows": len(dim_weather),
  "execution_time_seconds": round(time.time() - start, 4)
}])

load_log.to_csv("etl_pipeline/logs/load_log.csv", index=False)

print("ETL load success")
print(load_log)