DROP TABLE IF EXISTS elt_trip_analysis;

CREATE TABLE elt_trip_analysis AS
WITH taxi_clean AS (
  SELECT
    id,
    vendor_id,
    datetime(pickup_datetime) AS pickup_datetime,
    datetime(dropoff_datetime) AS dropoff_datetime,

    CASE
      WHEN CAST(passenger_count AS INTEGER) < 1 THEN 1
      WHEN CAST(passenger_count AS INTEGER) > 6 THEN 6
      ELSE CAST(passenger_count AS INTEGER)
    END AS passenger_count,

    CAST(pickup_longitude AS REAL) AS pickup_longitude,
    CAST(pickup_latitude AS REAL) AS pickup_latitude,
    CAST(dropoff_longitude AS REAL) AS dropoff_longitude,
    CAST(dropoff_latitude AS REAL) AS dropoff_latitude,

    CASE
      WHEN CAST(trip_duration AS REAL) <= 0 THEN NULL
      ELSE CAST(trip_duration AS REAL)
    END AS trip_duration,

    store_and_fwd_flag
  FROM raw_taxi
  WHERE id IS NOT NULL
    AND pickup_datetime IS NOT NULL
    AND dropoff_datetime IS NOT NULL
  GROUP BY id
),

weather_daily AS (
  SELECT
    date(datetime) AS weather_date,
    AVG(CAST(temp AS REAL)) AS temp,
    AVG(CAST(feelslike AS REAL)) AS feelslike,
    AVG(CAST(humidity AS REAL)) AS humidity,
    AVG(CAST(precip AS REAL)) AS precip,
    AVG(CAST(windspeed AS REAL)) AS windspeed,
    AVG(CAST(cloudcover AS REAL)) AS cloudcover,
    AVG(CAST(visibility AS REAL)) AS visibility,
    MAX(conditions) AS conditions
  FROM raw_weather
  WHERE datetime IS NOT NULL
  GROUP BY date(datetime)
)

SELECT
  t.id,
  t.vendor_id,
  t.pickup_datetime,
  t.dropoff_datetime,
  t.passenger_count,
  t.pickup_longitude,
  t.pickup_latitude,
  t.dropoff_longitude,
  t.dropoff_latitude,
  t.store_and_fwd_flag,
  t.trip_duration,

  t.trip_duration / 60.0 AS duration_minutes,

  date(t.pickup_datetime) AS pickup_date,
  CAST(strftime('%H', t.pickup_datetime) AS INTEGER) AS pickup_hour,
  CAST(strftime('%d', t.pickup_datetime) AS INTEGER) AS pickup_day,
  strftime('%w', t.pickup_datetime) AS pickup_weekday_number,

  w.temp,
  w.feelslike,
  w.humidity,
  w.precip,
  w.windspeed,
  w.cloudcover,
  w.visibility,
  COALESCE(w.conditions, 'Unknown') AS conditions,

  CASE
    WHEN COALESCE(w.precip, 0) > 0 THEN 1
    ELSE 0
  END AS is_rain,

  COALESCE(w.temp, 0) - COALESCE(w.feelslike, 0) AS temp_feelslike_diff,

  CASE
    WHEN t.store_and_fwd_flag = 'Y' THEN 1
    ELSE 0
  END AS store_and_fwd_flag_encoded

FROM taxi_clean t
LEFT JOIN weather_daily w
  ON date(t.pickup_datetime) = w.weather_date
WHERE t.trip_duration IS NOT NULL;