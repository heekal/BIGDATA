import re
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory


DB_PATH_PATTERN = r'db_path\s*=\s*r?\\"\\"[^\r\n]+?\\"\\"'


def to_powerbi_safe_path(path):
  return Path(path).resolve().as_posix()


def patch_schema_text(schema_text, db_path):
  safe_db_path = to_powerbi_safe_path(db_path)

  def replacement(_match):
    return f'db_path = r\\"\\"{safe_db_path}\\"\\"'

  patched_text, replacements = re.subn(DB_PATH_PATTERN, replacement, schema_text)

  if replacements == 0:
    raise RuntimeError(
      "Baris db_path di DataModelSchema tidak ditemukan. "
      "Pastikan bigdata_project.pbit berasal dari dashboard lama yang memakai Python source."
    )

  return patched_text, replacements, safe_db_path


def patch_pbit(template_path, output_path, db_path):
  template_path = Path(template_path)
  output_path = Path(output_path)
  db_path = Path(db_path)

  if not template_path.exists():
    raise FileNotFoundError(f"Template PBIT tidak ditemukan: {template_path}")

  if not db_path.exists():
    raise FileNotFoundError(f"Database tidak ditemukan: {db_path}")

  with TemporaryDirectory() as temp_dir_raw:
    temp_dir = Path(temp_dir_raw)

    with zipfile.ZipFile(template_path, "r") as source_zip:
      source_zip.extractall(temp_dir)

    schema_path = temp_dir / "DataModelSchema"
    if not schema_path.exists():
      raise FileNotFoundError("DataModelSchema tidak ditemukan di dalam PBIT.")

    schema_text = schema_path.read_text(encoding="utf-16le")
    schema_text, replacements, safe_db_path = patch_schema_text(schema_text, db_path)
    schema_path.write_text(schema_text, encoding="utf-16le")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
      output_path.unlink()

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as output_zip:
      for file_path in temp_dir.rglob("*"):
        if file_path.is_file():
          output_zip.write(file_path, file_path.relative_to(temp_dir).as_posix())

  print(f"Created: {output_path}")
  print(f"Patched db_path: {safe_db_path}")
  print(f"Replacements: {replacements}")


def main():
  template_path = "bigdata_project.pbit"

  patch_pbit(
    template_path=template_path,
    output_path="dashboard_etl_template.pbit",
    db_path="C:/Users/haika/Develop/bigdata_revision_code_only_v3/warehouse/warehouse_etl.db"
  )

  patch_pbit(
    template_path=template_path,
    output_path="dashboard_elt_template.pbit",
    db_path="C:/Users/haika/Develop/bigdata_revision_code_only_v3/warehouse/warehouse_elt.db"
  )

  print("Open each generated PBIT in Power BI, refresh, then save as:")
  print("- dashboard_etl.pbix")
  print("- dashboard_elt.pbix")


if __name__ == "__main__":
  main()
