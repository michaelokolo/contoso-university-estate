"""Turn the code map into a CRM import file containing only CRM-owned columns."""
import csv
from pathlib import Path

SOURCE = Path("output/reference/code_map.csv")
TARGET = Path("output/crm/programmes_import.csv")

with SOURCE.open(newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

TARGET.parent.mkdir(parents=True, exist_ok=True)
with TARGET.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Programme title", "Programme code", "Level", "Award", "Faculty",
        "Duration (years)", "Mode", "UCAS course code", "Open for applications",
    ])
    for row in rows:
        writer.writerow([
            row["crm_title"], row["crm_code"], row["level"], row["award"],
            row["faculty_code"], row["duration_years"], row["mode"],
            row["ucas_code"], "Yes",
        ])

print(f"Wrote {len(rows)} programmes to {TARGET}")