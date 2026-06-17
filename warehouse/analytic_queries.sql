-- 1. Total perjalanan
SELECT 
  COUNT(*) AS total_trip
FROM fact_trip;

-- 2. Rata-rata durasi perjalanan
SELECT 
  AVG(duration_minutes) AS avg_duration_minutes
FROM fact_trip;

-- 3. Rata-rata jarak perjalanan
SELECT 
  AVG(distance_km) AS avg_distance_km
FROM fact_trip;

-- 4. Rata-rata kecepatan perjalanan
SELECT 
  AVG(speed_kmh) AS avg_speed_kmh
FROM fact_trip;

-- 5. Jumlah trip per jam
SELECT 
  dt.pickup_hour,
  COUNT(*) AS total_trip
FROM fact_trip ft
JOIN dim_time dt 
  ON ft.time_id = dt.time_id
GROUP BY dt.pickup_hour
ORDER BY dt.pickup_hour;

-- 6. Rata-rata durasi per jam
SELECT 
  dt.pickup_hour,
  AVG(ft.duration_minutes) AS avg_duration_minutes
FROM fact_trip ft
JOIN dim_time dt 
  ON ft.time_id = dt.time_id
GROUP BY dt.pickup_hour
ORDER BY dt.pickup_hour;

-- 7. Perbandingan perjalanan saat hujan dan tidak hujan
SELECT 
  ft.is_rain,
  COUNT(*) AS total_trip,
  AVG(ft.duration_minutes) AS avg_duration_minutes,
  AVG(ft.speed_kmh) AS avg_speed_kmh
FROM fact_trip ft
GROUP BY ft.is_rain;

-- 8. Rata-rata durasi berdasarkan vendor
SELECT 
  dv.vendor_id,
  COUNT(*) AS total_trip,
  AVG(ft.duration_minutes) AS avg_duration_minutes,
  AVG(ft.distance_km) AS avg_distance_km
FROM fact_trip ft
JOIN dim_vendor dv 
  ON ft.vendor_key = dv.vendor_key
GROUP BY dv.vendor_id;

-- 9. Pengaruh curah hujan terhadap durasi
SELECT 
  CASE
    WHEN dw.precip = 0 THEN 'no_precip'
    WHEN dw.precip > 0 AND dw.precip <= 1 THEN 'low_precip'
    ELSE 'high_precip'
  END AS precip_category,
  COUNT(*) AS total_trip,
  AVG(ft.duration_minutes) AS avg_duration_minutes
FROM fact_trip ft
JOIN dim_weather dw 
  ON ft.weather_id = dw.weather_id
GROUP BY precip_category;

-- 10. Tren trip berdasarkan tanggal
SELECT 
  dt.pickup_date,
  COUNT(*) AS total_trip,
  AVG(ft.duration_minutes) AS avg_duration_minutes
FROM fact_trip ft
JOIN dim_time dt 
  ON ft.time_id = dt.time_id
GROUP BY dt.pickup_date
ORDER BY dt.pickup_date;