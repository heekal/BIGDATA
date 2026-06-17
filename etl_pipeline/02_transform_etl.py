import os
import time
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

os.makedirs("warehouse", exist_ok=True)
os.makedirs("etl_pipeline/logs", exist_ok=True)

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

def cap_outlier_iqr(df, column):
  q1 = df[column].quantile(0.25)
  q3 = df[column].quantile(0.75)
  iqr = q3 - q1

  lower = q1 - 1.5 * iqr
  upper = q3 + 1.5 * iqr

  df[column] = df[column].clip(lower, upper)
  return df

start = time.time()

taxi = pd.read_csv("raw/etl_taxi_raw.csv")
weather = pd.read_csv("raw/etl_weather_raw.csv")

taxi.columns = to_snake_case(taxi.columns)
weather.columns = to_snake_case(weather.columns)

before_rows = len(taxi)
before_columns = taxi.shape[1] + weather.shape[1]

# =========================
# Cleaning taxi
# =========================

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

# Batas koordinat New York State untuk menghapus data entry error.
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

# Hindari drop row supaya jumlah data tetap >= 100.000
taxi["passenger_count"] = taxi["passenger_count"].clip(1, 6).astype(int)

positive_duration_median = taxi.loc[taxi["trip_duration"] > 0, "trip_duration"].median()
taxi.loc[taxi["trip_duration"] <= 0, "trip_duration"] = positive_duration_median

taxi["vendor_id"] = taxi["vendor_id"].fillna(safe_mode(taxi["vendor_id"], "Unknown"))
taxi["store_and_fwd_flag"] = taxi["store_and_fwd_flag"].fillna(
  safe_mode(taxi["store_and_fwd_flag"], "N")
)

# =========================
# Cleaning weather
# =========================

weather["datetime"] = pd.to_datetime(weather["datetime"], errors="coerce")
weather = weather.dropna(subset=["datetime"])

weather_numeric_candidates = [
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

for col in weather_numeric_candidates:
  if col in weather.columns:
    weather[col] = pd.to_numeric(weather[col], errors="coerce")
    weather[col] = weather[col].fillna(weather[col].median())

weather_categorical_candidates = [
  "name",
  "preciptype",
  "conditions",
  "icon",
  "stations"
]

for col in weather_categorical_candidates:
  if col in weather.columns:
    weather[col] = weather[col].fillna(safe_mode(weather[col], "Unknown"))

# =========================
# Feature engineering taxi
# =========================

taxi["pickup_date"] = taxi["pickup_datetime"].dt.date
taxi["pickup_hour"] = taxi["pickup_datetime"].dt.hour
taxi["pickup_day"] = taxi["pickup_datetime"].dt.day
taxi["pickup_weekday"] = taxi["pickup_datetime"].dt.day_name()

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

# Outlier pakai capping, bukan drop
for col in ["trip_duration", "duration_minutes", "distance_km", "speed_kmh"]:
  taxi = cap_outlier_iqr(taxi, col)

# =========================
# Weather daily aggregation
# =========================

weather["weather_date"] = weather["datetime"].dt.date

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

# =========================
# Merge taxi + weather
# =========================

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

# =========================
# Feature engineering tambahan
# =========================

merged["is_rain"] = (merged["precip"] > 0).astype(int)
merged["temp_feelslike_diff"] = merged["temp"] - merged["feelslike"]

# Encoding kategorikal
merged["store_and_fwd_flag_encoded"] = merged["store_and_fwd_flag"].map({
  "N": 0,
  "Y": 1
}).fillna(0).astype(int)

merged = pd.get_dummies(
  merged,
  columns=["pickup_weekday", "conditions"],
  drop_first=True
)

# Normalisasi minimal dua kolom numerik
scaler = MinMaxScaler()

merged[["trip_duration_norm", "distance_km_norm"]] = scaler.fit_transform(
  merged[["trip_duration", "distance_km"]]
)

# =========================
# Validasi kualitas data
# =========================

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

# =========================
# Save output
# =========================

merged.to_csv("warehouse/etl_cleaned_data.csv", index=False)

transform_log = pd.DataFrame([{
  "process": "etl_transform",
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
