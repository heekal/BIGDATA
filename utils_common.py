import os
import shutil
import sqlite3
import time
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from sklearn.preprocessing import MinMaxScaler

load_dotenv()

REQUIRED_DASHBOARD_COLUMNS = [
  "id",
  "vendor_id",
  "pickup_datetime",
  "dropoff_datetime",
  "passenger_count",
  "pickup_longitude",
  "pickup_latitude",
  "dropoff_longitude",
  "dropoff_latitude",
  "trip_duration",
  "duration_minutes",
  "distance_km",
  "speed_kmh",
  "pickup_date",
  "pickup_hour",
  "pickup_day",
  "is_rain",
  "temp",
  "humidity",
  "precip",
  "windspeed",
  "visibility"
]

WEATHER_NUMERIC_COLUMNS = [
  "temp",
  "feelslike",
  "dew",
  "humidity",
  "precip",
  "precipprob",
  "snow",
  "snowdepth",
  "windgust",
  "windspeed",
  "winddir",
  "sealevelpressure",
  "cloudcover",
  "visibility",
  "solarradiation",
  "solarenergy",
  "uvindex",
  "severerisk"
]

WEATHER_CATEGORICAL_COLUMNS = [
  "name",
  "preciptype",
  "conditions",
  "icon",
  "stations"
]


def ensure_directories():
  for path in [
    "raw",
    "datalake",
    "warehouse",
    "outputs/etl",
    "outputs/elt",
    "dashboard_exports",
    "etl_pipeline/logs",
    "elt_pipeline/logs"
  ]:
    os.makedirs(path, exist_ok=True)


def reset_generated_outputs():
  paths = [
    "outputs",
    "dashboard_exports",
    "warehouse/warehouse.db",
    "warehouse/warehouse_etl.db",
    "warehouse/warehouse_elt.db",
    "warehouse/etl_cleaned_data.csv",
    "raw/etl_taxi_raw.csv",
    "raw/etl_weather_raw.csv",
    "datalake/taxi_raw.csv",
    "etl_pipeline/logs",
    "elt_pipeline/logs"
  ]

  for path in paths:
    if os.path.isdir(path):
      shutil.rmtree(path)
    elif os.path.exists(path):
      os.remove(path)

  ensure_directories()


def to_snake_case(columns):
  return (
    columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_", regex=False)
    .str.replace("-", "_", regex=False)
  )


def safe_mode(series, default_value="Unknown"):
  mode_value = series.dropna().mode()

  if len(mode_value) == 0:
    return default_value

  return mode_value.iloc[0]


def haversine(lon1, lat1, lon2, lat2):
  lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
  dlon = lon2 - lon1
  dlat = lat2 - lat1

  a = (
    np.sin(dlat / 2) ** 2
    + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
  )

  c = 2 * np.arcsin(np.sqrt(a))
  return 6371 * c


def haversine_scalar(lon1, lat1, lon2, lat2):
  try:
    lon1 = float(lon1)
    lat1 = float(lat1)
    lon2 = float(lon2)
    lat2 = float(lat2)
  except (TypeError, ValueError):
    return None

  lon1, lat1, lon2, lat2 = np.radians([lon1, lat1, lon2, lat2])
  dlon = lon2 - lon1
  dlat = lat2 - lat1
  a = (
    np.sin(dlat / 2) ** 2
    + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
  )
  c = 2 * np.arcsin(np.sqrt(a))
  return float(6371 * c)


def cap_outlier_iqr(df, column):
  q1 = df[column].quantile(0.25)
  q3 = df[column].quantile(0.75)
  iqr = q3 - q1

  lower = q1 - 1.5 * iqr
  upper = q3 + 1.5 * iqr

  df[column] = df[column].clip(lower, upper)
  return df


def read_taxi_source(path="raw/taxi.csv"):
  if not os.path.exists(path):
    raise FileNotFoundError(
      "raw/taxi.csv tidak ditemukan. Taruh dataset taxi di folder raw dengan nama taxi.csv."
    )

  return pd.read_csv(path)


def read_weather_source(output_path=None):
  weather_api_url = os.getenv("WEATHER_API_URL")

  if weather_api_url:
    response = requests.get(weather_api_url, timeout=60)
    response.raise_for_status()
    weather = pd.read_csv(StringIO(response.text))
    source_type = "api_csv"
  else:
    fallback_paths = [
      "datalake/weather_api_raw.csv",
      "raw/etl_weather_raw.csv",
      "raw/weather_api_raw.csv",
      "weather_api_raw.csv"
    ]
    selected_path = next((path for path in fallback_paths if os.path.exists(path)), None)

    if selected_path is None:
      raise FileNotFoundError(
        "Weather source tidak ditemukan. Isi WEATHER_API_URL di .env atau taruh cached weather CSV di datalake/weather_api_raw.csv."
      )

    weather = pd.read_csv(selected_path)
    source_type = f"cached_csv:{selected_path}"

  if output_path:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    weather.to_csv(output_path, index=False)

  return weather, source_type


def prepare_weather_daily(weather):
  weather = weather.copy()
  weather.columns = to_snake_case(weather.columns)

  if "datetime" not in weather.columns:
    raise KeyError("Weather data wajib punya kolom datetime.")

  weather["datetime"] = pd.to_datetime(weather["datetime"], errors="coerce")
  weather = weather.dropna(subset=["datetime"])

  for col in WEATHER_NUMERIC_COLUMNS:
    if col in weather.columns:
      weather[col] = pd.to_numeric(weather[col], errors="coerce")
      weather[col] = weather[col].fillna(weather[col].median())

  for col in WEATHER_CATEGORICAL_COLUMNS:
    if col in weather.columns:
      weather[col] = weather[col].fillna(safe_mode(weather[col], "Unknown"))

  weather["weather_date"] = weather["datetime"].dt.date

  required_cols = [
    "temp",
    "feelslike",
    "humidity",
    "precip",
    "windspeed",
    "cloudcover",
    "visibility",
    "conditions"
  ]

  for col in required_cols:
    if col not in weather.columns:
      weather[col] = 0 if col != "conditions" else "Unknown"

  weather_daily = weather.groupby("weather_date", as_index=False).agg({
    "temp": "mean",
    "feelslike": "mean",
    "humidity": "mean",
    "precip": "mean",
    "windspeed": "mean",
    "cloudcover": "mean",
    "visibility": "mean",
    "conditions": lambda x: safe_mode(x, "Unknown")
  })

  return weather_daily


def add_normalized_columns(df):
  df = df.copy()

  for col in ["trip_duration", "distance_km"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
    df[col] = df[col].fillna(df[col].median())

  if df[["trip_duration", "distance_km"]].nunique().min() <= 1:
    df["trip_duration_norm"] = 0
    df["distance_km_norm"] = 0
    return df

  scaler = MinMaxScaler()
  df[["trip_duration_norm", "distance_km_norm"]] = scaler.fit_transform(
    df[["trip_duration", "distance_km"]]
  )
  return df


def build_dashboard_table(df, source_pipeline):
  dashboard = df.copy()

  for col in REQUIRED_DASHBOARD_COLUMNS:
    if col not in dashboard.columns:
      if col in ["temp", "humidity", "precip", "windspeed", "visibility"]:
        dashboard[col] = 0
      elif col == "is_rain":
        dashboard[col] = 0
      else:
        dashboard[col] = None

  dashboard = dashboard[REQUIRED_DASHBOARD_COLUMNS].copy()

  dashboard["pickup_datetime"] = pd.to_datetime(dashboard["pickup_datetime"], errors="coerce")
  dashboard["dropoff_datetime"] = pd.to_datetime(dashboard["dropoff_datetime"], errors="coerce")
  dashboard["pickup_date"] = pd.to_datetime(dashboard["pickup_date"], errors="coerce")

  numeric_cols = [
    "passenger_count",
    "pickup_longitude",
    "pickup_latitude",
    "dropoff_longitude",
    "dropoff_latitude",
    "trip_duration",
    "duration_minutes",
    "distance_km",
    "speed_kmh",
    "pickup_hour",
    "pickup_day",
    "is_rain",
    "temp",
    "humidity",
    "precip",
    "windspeed",
    "visibility"
  ]

  for col in numeric_cols:
    dashboard[col] = pd.to_numeric(dashboard[col], errors="coerce")

  dashboard["rain_condition"] = dashboard["is_rain"].map({
    0: "Tidak Hujan",
    1: "Hujan"
  }).fillna("Tidak Hujan")

  dashboard["distance_category"] = pd.cut(
    dashboard["distance_km"],
    bins=[-1, 1, 3, 5, 10, 999999],
    labels=["<1 km", "1-3 km", "3-5 km", "5-10 km", ">10 km"]
  ).astype(str)

  dashboard["duration_category"] = pd.cut(
    dashboard["duration_minutes"],
    bins=[-1, 5, 10, 20, 40, 999999],
    labels=["<5 min", "5-10 min", "10-20 min", "20-40 min", ">40 min"]
  ).astype(str)

  dashboard["speed_category"] = pd.cut(
    dashboard["speed_kmh"],
    bins=[-1, 10, 25, 999999],
    labels=["Lambat", "Sedang", "Cepat"]
  ).astype(str)

  dashboard["time_period"] = pd.cut(
    dashboard["pickup_hour"],
    bins=[-1, 5, 11, 16, 20, 23],
    labels=["Dini Hari", "Pagi", "Siang", "Sore", "Malam"]
  ).astype(str)

  dashboard["precip_category"] = pd.cut(
    dashboard["precip"],
    bins=[-1, 0, 1, 999999],
    labels=["No Precip", "Low Precip", "High Precip"]
  ).astype(str)

  dashboard["source_pipeline"] = source_pipeline

  return dashboard


def build_star_schema(source_df, db_path, source_pipeline, include_elt_alias=True):
  df = source_df.copy()
  df = add_normalized_columns(df)

  required_cols = [
    "id",
    "vendor_id",
    "pickup_date",
    "pickup_hour",
    "pickup_day",
    "weather_date",
    "temp",
    "feelslike",
    "humidity",
    "precip",
    "windspeed",
    "cloudcover",
    "visibility",
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
  ]

  for col in required_cols:
    if col not in df.columns:
      if col == "weather_date":
        df[col] = df.get("pickup_date")
      else:
        df[col] = 0

  df["pickup_date"] = pd.to_datetime(df["pickup_date"], errors="coerce").dt.date.astype(str)
  df["weather_date"] = pd.to_datetime(df["weather_date"], errors="coerce").dt.date.astype(str)

  conn = sqlite3.connect(db_path)
  conn.execute("PRAGMA foreign_keys = OFF;")

  conn.executescript("""
  DROP TABLE IF EXISTS dashboard_trip;
  DROP TABLE IF EXISTS fact_trip;
  DROP TABLE IF EXISTS dim_time;
  DROP TABLE IF EXISTS dim_vendor;
  DROP TABLE IF EXISTS dim_weather;
  """)

  dim_time = df[[
    "pickup_date",
    "pickup_hour",
    "pickup_day"
  ]].drop_duplicates().reset_index(drop=True)
  dim_time["time_id"] = range(1, len(dim_time) + 1)
  dim_time = dim_time[["time_id", "pickup_date", "pickup_hour", "pickup_day"]]

  dim_vendor = df[["vendor_id"]].drop_duplicates().reset_index(drop=True)
  dim_vendor["vendor_key"] = range(1, len(dim_vendor) + 1)
  dim_vendor = dim_vendor[["vendor_key", "vendor_id"]]

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
  dim_weather = dim_weather[[
    "weather_id",
    "weather_date",
    "temp",
    "feelslike",
    "humidity",
    "precip",
    "windspeed",
    "cloudcover",
    "visibility"
  ]]

  fact = df.merge(
    dim_time,
    on=["pickup_date", "pickup_hour", "pickup_day"],
    how="left"
  )
  fact = fact.merge(dim_vendor, on="vendor_id", how="left")
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
  ]].copy()

  dashboard_trip = build_dashboard_table(df, source_pipeline)

  dim_time.to_sql("dim_time", conn, if_exists="replace", index=False)
  dim_vendor.to_sql("dim_vendor", conn, if_exists="replace", index=False)
  dim_weather.to_sql("dim_weather", conn, if_exists="replace", index=False)
  fact_trip.to_sql("fact_trip", conn, if_exists="replace", index=False)
  dashboard_trip.to_sql("dashboard_trip", conn, if_exists="replace", index=False)

  if include_elt_alias and "elt_trip_analysis" not in pd.read_sql_query(
    "SELECT name FROM sqlite_master WHERE type='table'",
    conn
  )["name"].tolist():
    elt_alias_columns = [
      "id",
      "vendor_id",
      "pickup_datetime",
      "dropoff_datetime",
      "passenger_count",
      "pickup_longitude",
      "pickup_latitude",
      "dropoff_longitude",
      "dropoff_latitude",
      "store_and_fwd_flag",
      "trip_duration",
      "duration_minutes",
      "pickup_date",
      "pickup_hour",
      "pickup_day",
      "pickup_weekday_number",
      "temp",
      "feelslike",
      "humidity",
      "precip",
      "windspeed",
      "cloudcover",
      "visibility",
      "conditions",
      "is_rain",
      "temp_feelslike_diff",
      "store_and_fwd_flag_encoded"
    ]

    alias_df = df.copy()

    if "pickup_weekday_number" not in alias_df.columns:
      pickup_dt = pd.to_datetime(alias_df["pickup_datetime"], errors="coerce")
      alias_df["pickup_weekday_number"] = ((pickup_dt.dt.dayofweek + 1) % 7).fillna(0).astype(int)

    if "conditions" not in alias_df.columns:
      condition_columns = [col for col in alias_df.columns if col.startswith("conditions_")]
      if condition_columns:
        alias_df["conditions"] = "Unknown"
        for col in condition_columns:
          alias_df.loc[alias_df[col].astype(bool), "conditions"] = col.replace("conditions_", "")
      else:
        alias_df["conditions"] = "Unknown"

    for col in elt_alias_columns:
      if col not in alias_df.columns:
        alias_df[col] = 0

    alias_df[elt_alias_columns].to_sql("elt_trip_analysis", conn, if_exists="replace", index=False)

  conn.commit()
  conn.close()

  return {
    "fact_rows": len(fact_trip),
    "dim_time_rows": len(dim_time),
    "dim_vendor_rows": len(dim_vendor),
    "dim_weather_rows": len(dim_weather),
    "dashboard_rows": len(dashboard_trip)
  }


def write_pipeline_summary():
  summaries = []

  for pipeline, db_path in [
    ("ETL", "warehouse/warehouse_etl.db"),
    ("ELT", "warehouse/warehouse_elt.db")
  ]:
    if not os.path.exists(db_path):
      continue

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM dashboard_trip", conn)
    conn.close()

    summaries.append({
      "pipeline": pipeline,
      "total_trip": len(df),
      "avg_duration_minutes": round(df["duration_minutes"].mean(), 4),
      "avg_distance_km": round(df["distance_km"].mean(), 4),
      "avg_speed_kmh": round(df["speed_kmh"].mean(), 4),
      "rain_rows": int((df["is_rain"] == 1).sum()),
      "not_rain_rows": int((df["is_rain"] == 0).sum())
    })

  summary = pd.DataFrame(summaries)
  summary.to_csv("dashboard_exports/dashboard_pipeline_summary.csv", index=False)
  return summary
