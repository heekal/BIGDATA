import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import time

import numpy as np
import pandas as pd

from utils_common import (
  cap_outlier_iqr,
  ensure_directories,
  haversine,
  prepare_weather_daily,
  safe_mode,
  to_snake_case,
  add_normalized_columns
)


def main():
  ensure_directories()
  start = time.time()

  taxi = pd.read_csv("outputs/etl/raw_taxi.csv")
  weather = pd.read_csv("outputs/etl/raw_weather.csv")

  taxi.columns = to_snake_case(taxi.columns)
  weather.columns = to_snake_case(weather.columns)

  before_rows = len(taxi)
  before_columns = taxi.shape[1] + weather.shape[1]

  taxi["pickup_datetime"] = pd.to_datetime(taxi["pickup_datetime"], errors="coerce")
  taxi["dropoff_datetime"] = pd.to_datetime(taxi["dropoff_datetime"], errors="coerce")

  taxi = taxi.drop_duplicates(subset=["id"])
  taxi = taxi.dropna(subset=["id", "pickup_datetime", "dropoff_datetime"])

  numeric_taxi_cols = [
    "passenger_count",
    "pickup_longitude",
    "pickup_latitude",
    "dropoff_longitude",
    "dropoff_latitude",
    "trip_duration"
  ]

  for col in numeric_taxi_cols:
    taxi[col] = pd.to_numeric(taxi[col], errors="coerce")
    taxi[col] = taxi[col].fillna(taxi[col].median())

  lat_min = 40.5
  lat_max = 45.0167
  lon_min = -79.7667
  lon_max = -71.85

  coordinate_mask = (
    taxi["pickup_longitude"].between(lon_min, lon_max)
    & taxi["pickup_latitude"].between(lat_min, lat_max)
    & taxi["dropoff_longitude"].between(lon_min, lon_max)
    & taxi["dropoff_latitude"].between(lat_min, lat_max)
  )

  rows_before_coordinate_filter = len(taxi)
  taxi = taxi[coordinate_mask].copy()
  coordinate_filtered_rows = rows_before_coordinate_filter - len(taxi)

  taxi["passenger_count"] = taxi["passenger_count"].clip(1, 6).astype(int)

  positive_duration_median = taxi.loc[taxi["trip_duration"] > 0, "trip_duration"].median()
  taxi.loc[taxi["trip_duration"] <= 0, "trip_duration"] = positive_duration_median

  taxi["vendor_id"] = taxi["vendor_id"].fillna(safe_mode(taxi["vendor_id"], "Unknown"))
  taxi["store_and_fwd_flag"] = taxi["store_and_fwd_flag"].fillna(
    safe_mode(taxi["store_and_fwd_flag"], "N")
  )

  taxi["pickup_date"] = taxi["pickup_datetime"].dt.date
  taxi["pickup_hour"] = taxi["pickup_datetime"].dt.hour
  taxi["pickup_day"] = taxi["pickup_datetime"].dt.day
  taxi["pickup_weekday"] = taxi["pickup_datetime"].dt.day_name()
  taxi["pickup_weekday_number"] = ((taxi["pickup_datetime"].dt.dayofweek + 1) % 7).astype(int)
  taxi["duration_minutes"] = taxi["trip_duration"] / 60

  taxi["distance_km"] = haversine(
    taxi["pickup_longitude"],
    taxi["pickup_latitude"],
    taxi["dropoff_longitude"],
    taxi["dropoff_latitude"]
  )

  taxi["speed_kmh"] = taxi["distance_km"] / (taxi["trip_duration"] / 3600)
  taxi["speed_kmh"] = taxi["speed_kmh"].replace([np.inf, -np.inf], np.nan)
  taxi["speed_kmh"] = taxi["speed_kmh"].fillna(taxi["speed_kmh"].median())

  for col in ["trip_duration", "duration_minutes", "distance_km", "speed_kmh"]:
    taxi = cap_outlier_iqr(taxi, col)

  weather_daily = prepare_weather_daily(weather)

  merged = taxi.merge(
    weather_daily,
    left_on="pickup_date",
    right_on="weather_date",
    how="left"
  )

  merged["weather_date"] = merged["weather_date"].fillna(merged["pickup_date"])

  weather_numeric_after_merge = [
    "temp",
    "feelslike",
    "humidity",
    "precip",
    "windspeed",
    "cloudcover",
    "visibility"
  ]

  for col in weather_numeric_after_merge:
    merged[col] = merged[col].fillna(merged[col].median())

  merged["conditions"] = merged["conditions"].fillna("Unknown")
  merged["is_rain"] = (merged["precip"] > 0).astype(int)
  merged["temp_feelslike_diff"] = merged["temp"] - merged["feelslike"]

  merged["store_and_fwd_flag_encoded"] = merged["store_and_fwd_flag"].map({
    "N": 0,
    "Y": 1
  }).fillna(0).astype(int)

  weekday_dummies = pd.get_dummies(
    merged["pickup_weekday"],
    prefix="pickup_weekday",
    drop_first=True
  )
  condition_dummies = pd.get_dummies(
    merged["conditions"],
    prefix="conditions",
    drop_first=True
  )
  merged = pd.concat([merged, weekday_dummies, condition_dummies], axis=1)

  merged = add_normalized_columns(merged)
  merged["source_pipeline"] = "ETL"

  validation_results = []

  validation_results.append({
    "rule": "uniqueness_check_id",
    "status": bool(merged["id"].is_unique),
    "failed_rows": int(merged["id"].duplicated().sum())
  })

  validation_results.append({
    "rule": "null_check_id",
    "status": bool(merged["id"].isna().sum() == 0),
    "failed_rows": int(merged["id"].isna().sum())
  })

  validation_results.append({
    "rule": "range_check_passenger_count",
    "status": bool(merged["passenger_count"].between(1, 6).all()),
    "failed_rows": int((~merged["passenger_count"].between(1, 6)).sum())
  })

  coordinate_validation_mask = (
    merged["pickup_longitude"].between(lon_min, lon_max)
    & merged["pickup_latitude"].between(lat_min, lat_max)
    & merged["dropoff_longitude"].between(lon_min, lon_max)
    & merged["dropoff_latitude"].between(lat_min, lat_max)
  )

  validation_results.append({
    "rule": "range_check_coordinate_bounds",
    "status": bool(coordinate_validation_mask.all()),
    "failed_rows": int((~coordinate_validation_mask).sum())
  })

  validation_results.append({
    "rule": "datatype_pickup_datetime",
    "status": bool(pd.api.types.is_datetime64_any_dtype(merged["pickup_datetime"])),
    "failed_rows": 0
  })

  validation_results.append({
    "rule": "referential_integrity_weather_date",
    "status": bool(merged["weather_date"].isna().sum() == 0),
    "failed_rows": int(merged["weather_date"].isna().sum())
  })

  validation_results.append({
    "rule": "distribution_trip_duration_positive",
    "status": bool((merged["trip_duration"] > 0).all()),
    "failed_rows": int((merged["trip_duration"] <= 0).sum())
  })

  validation_df = pd.DataFrame(validation_results)
  validation_df.to_csv("etl_pipeline/logs/validation_log.csv", index=False)

  merged.to_csv("outputs/etl/etl_cleaned_data.csv", index=False)
  merged.to_csv("warehouse/etl_cleaned_data.csv", index=False)

  transform_log = pd.DataFrame([{
    "pipeline": "ETL",
    "process": "etl_transform",
    "status": "success",
    "output_path": "outputs/etl/etl_cleaned_data.csv",
    "before_rows": before_rows,
    "after_rows": len(merged),
    "coordinate_filtered_rows": coordinate_filtered_rows,
    "before_columns": before_columns,
    "after_columns": merged.shape[1],
    "execution_time_seconds": round(time.time() - start, 4)
  }])

  transform_log.to_csv("etl_pipeline/logs/transform_log.csv", index=False)

  print("ETL transform success")
  print("Final shape:", merged.shape)
  print(validation_df)


if __name__ == "__main__":
  main()
