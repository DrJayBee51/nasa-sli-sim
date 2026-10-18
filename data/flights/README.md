Flight data exports go here: altimeter CSVs (for scripts/fit_cd.py) and full
flight-computer logs with IMU and GPS channels (for scripts/compare_flight.py).

Generated practice data (synthetic_*.csv) is gitignored - recreate it with:
  python scripts/make_synthetic_flight.py --cd-scale 1.18
That writes synthetic_vdf.csv (altimeter only) and synthetic_telemetry.csv
(altitude, accelerometer, gyro, GPS).
