import argparse
import subprocess
import sys

from utils_common import ensure_directories, reset_generated_outputs


COMMANDS = [
  "python etl_pipeline/01_extract_etl.py",
  "python etl_pipeline/02_transform_etl.py",
  "python etl_pipeline/03_load_etl.py",
  "python elt_pipeline/01_extract_load_elt.py",
  "python elt_pipeline/03_run_elt_transform.py",
  "python create_dashboard_outputs.py"
]


def run_command(command):
  print("\nRunning:", command)
  result = subprocess.run(command, shell=True)

  if result.returncode != 0:
    raise RuntimeError(f"Command failed: {command}")


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--reset",
    action="store_true",
    help="hapus output lama sebelum pipeline dijalankan"
  )
  parser.add_argument(
    "--make-pbit",
    action="store_true",
    help="buat dashboard_etl_template.pbit dan dashboard_elt_template.pbit dari bigdata_project.pbit"
  )
  args = parser.parse_args()

  if args.reset:
    reset_generated_outputs()
  else:
    ensure_directories()

  for command in COMMANDS:
    run_command(command)

  if args.make_pbit:
    run_command("python make_dashboard_templates.py")

  print("\nFinish!")
  print("ETL output database: warehouse/warehouse_etl.db")
  print("ELT output database: warehouse/warehouse_elt.db")
  print("ETL dashboard data: dashboard_exports/dashboard_etl.csv")
  print("ELT dashboard data: dashboard_exports/dashboard_elt.csv")
  print("Summary: dashboard_exports/dashboard_pipeline_summary.csv")


if __name__ == "__main__":
  try:
    main()
  except Exception as error:
    print("\nERROR:", error)
    sys.exit(1)
