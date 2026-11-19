"""Build CRM import files for a sample of portal applicants and their applications."""
import csv
import json
from datetime import date, datetime
from pathlib import Path

SOURCE = Path("output/portal/applications.jsonl")
OUT = Path("output/crm")
SAMPLE_SIZE = 200


def programme_code(code_with_year):
    """'CS-BSC-2027' -> 'CS-BSC': the CRM holds the course, not the intake."""
    head, _, tail = code_with_year.rpartition("-")
    return head if tail.isdigit() else code_with_year


def uk_date(iso_date):
    return date.fromisoformat(iso_date).strftime("%d/%m/%Y")


def uk_datetime(iso_timestamp):
    return datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")


with SOURCE.open(encoding="utf-8") as f:
    applications = [json.loads(line) for line in f][:SAMPLE_SIZE]

OUT.mkdir(parents=True, exist_ok=True)

# 1. Contacts first (parents), one per unique email
contacts = {}
for app in applications:
    person = app["applicant"]
    email = person["email"].strip().lower()
    contacts.setdefault(email, person)

with (OUT / "contacts_import.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["First Name", "Last Name", "Email", "Birthday", "Mobile Phone"])
    for email, person in contacts.items():
        writer.writerow([person["firstName"], person["lastName"], email,
                         uk_date(person["dateOfBirth"]), person["phone"]])

# 2. Applications (children), pointing to contacts by email and programmes by code
with (OUT / "applications_import.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Application reference", "Applicant", "Programme", "Entry year",
                     "Route", "Status", "Submitted on"])
    for app in applications:
        writer.writerow([
            app["applicationId"],
            app["applicant"]["email"].strip().lower(),
            programme_code(app["programme"]["code"]),
            app["programme"]["entryYear"],
            "Portal",
            app["status"],
            uk_datetime(app["submittedAt"]),
        ])

print(f"Wrote {len(contacts)} contacts and {len(applications)} applications to {OUT}")
