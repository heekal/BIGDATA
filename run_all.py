import subprocess

commands = [
  "python etl_pipeline/01_extract_etl.py",
  "python etl_pipeline/02_transform_etl.py",
  "python etl_pipeline/03_load_etl.py",
  "python elt_pipeline/01_extract_load_elt.py",
  "python elt_pipeline/03_run_elt_transform.py",
  "python create_dashboard_table.py"
]

for command in commands:
  print("\nRunning:", command)

  result = subprocess.run(command, shell=True)

  if result.returncode != 0:
    raise RuntimeError(f"Command failed: {command}")

print("\nFinish!")
print("All pipeline ran successfully")
print("dashboard_trip is ready for Power BI refresh")
