"""Write each system's view of the data in that system's own format.

    _truth/     the clean answer key. Integrations must NEVER read it.
    reference/  shared reference data and the code map
    ucas/       daily XML transaction files (UCAS-style link)
    portal/     JSON Lines from the modern application portal
    sis/        pipe-delimited legacy exports from the student record system
    finance/    Windows-1252 CSV exports from the finance system
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from . import mess
from .people import Application, Person, Student, as_dict
from .reference import Programme


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_reference(out: Path, programmes: list[Programme], periods: list[dict], fees: dict) -> None:
    ref = _ensure(out / "reference")
    faculties = sorted({(p.faculty_code, p.faculty_name) for p in programmes})
    with open(ref / "faculties.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["faculty_code", "faculty_name"])
        w.writerows(faculties)
    with open(ref / "code_map.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["crm_code", "crm_title", "sis_route", "sis_title", "sis_status", "ucas_code",
                    "finance_code", "faculty_code", "level", "award", "duration_years", "mode", "notes"])
        for p in programmes:
            w.writerow([p.crm_code, p.full_title, p.sis_route, p.title_sis, p.status_sis, p.ucas_code or "",
                        p.finance_code, p.faculty_code, p.level, p.award, p.duration_years, p.mode, "; ".join(p.notes)])
    with open(ref / "academic_periods.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(periods[0].keys()))
        w.writeheader()
        w.writerows(periods)
    with open(ref / "fees.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["level", "fee_status", "annual_fee_gbp"])
        for (level, status), amount in fees.items():
            w.writerow([level, status, amount])


def write_truth(out: Path, people: list[Person], apps: list[Application], students: list[Student]) -> None:
    truth = _ensure(out / "_truth")
    for name, rows in (("people", people), ("applications", apps), ("students", students)):
        with open(truth / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(as_dict(row), default=str, ensure_ascii=False) + "\n")


def write_ucas(out: Path, apps: list[Application], people_by_key: dict[str, Person], rng: random.Random) -> int:
    """One XML file per day, like a provider's daily UCAS transaction download.

    Transaction types: APP (new application), RPL (applicant reply to an offer).
    """
    folder = _ensure(out / "ucas")
    by_day: dict[str, list[ET.Element]] = defaultdict(list)
    for a in apps:
        if not a.ucas_personal_id:
            continue
        p = people_by_key[a.person_key]
        t = ET.Element("Transaction", type="APP", seq=a.application_id[-6:])
        ET.SubElement(t, "PersonalId").text = a.ucas_personal_id
        ET.SubElement(t, "Forename").text = p.first_name
        ET.SubElement(t, "Surname").text = p.last_name
        ET.SubElement(t, "DateOfBirth").text = p.date_of_birth.isoformat()
        ET.SubElement(t, "Email").text = p.email
        ET.SubElement(t, "CourseCode").text = a.programme_ucas_code
        ET.SubElement(t, "EntryYear").text = str(a.entry_year)
        ET.SubElement(t, "PointOfEntry").text = "1"
        ET.SubElement(t, "FeeStatus").text = "H" if p.fee_status == "Home" else "O"
        ET.SubElement(t, "ApplicationScheme").text = "CL" if a.route == "Clearing" else "UG"
        if a.school:
            ET.SubElement(t, "School").text = a.school
        if a.predicted_grades:
            ET.SubElement(t, "PredictedGrades").text = a.predicted_grades
        by_day[a.submitted_at.strftime("%Y%m%d")].append(t)
        if a.reply and a.reply != "No reply" and a.decision_at:
            reply_at = a.decision_at + (a.decision_at - a.submitted_at) / 3
            rt = ET.Element("Transaction", type="RPL", seq=a.application_id[-6:])
            ET.SubElement(rt, "PersonalId").text = a.ucas_personal_id
            ET.SubElement(rt, "CourseCode").text = a.programme_ucas_code
            ET.SubElement(rt, "Reply").text = {"Firm": "F", "Insurance": "I", "Declined": "D"}[a.reply]
            by_day[reply_at.strftime("%Y%m%d")].append(rt)
    for day, transactions in sorted(by_day.items()):
        root = ET.Element("UcasTransactions", provider="C99", date=f"{day[:4]}-{day[4:6]}-{day[6:]}",
                          count=str(len(transactions)))
        root.extend(transactions)
        ET.indent(root)
        ET.ElementTree(root).write(folder / f"ucas_{day}.xml", encoding="utf-8", xml_declaration=True)
    return len(by_day)


def write_portal(out: Path, apps: list[Application], people_by_key: dict[str, Person], rng: random.Random) -> int:
    """Direct and postgraduate applications from the modern portal, as JSON Lines."""
    folder = _ensure(out / "portal")
    count = 0
    with open(folder / "applications.jsonl", "w", encoding="utf-8") as f:
        for a in apps:
            if a.route != "Direct":
                continue
            p = people_by_key[a.person_key]
            email = mess.invalid_email(p.email, rng) if rng.random() < 0.005 else p.email
            doc = {
                "applicationId": a.application_id,
                "submittedAt": a.submitted_at.isoformat() + "Z",
                "applicant": {
                    "firstName": p.first_name,
                    "lastName": p.last_name,
                    "preferredName": p.preferred_name,
                    "dateOfBirth": p.date_of_birth.isoformat(),
                    "email": email,
                    "phone": mess.maybe_blank(p.phone, rng, 0.03),
                    "address": {"line1": p.address_line1, "city": p.city,
                                "postcode": mess.maybe_blank(p.postcode, rng, 0.02), "country": p.country},
                    "feeStatus": p.fee_status,
                    "marketingConsent": p.marketing_consent,
                },
                "programme": {"code": a.programme_crm_code, "level": a.level, "entryYear": a.entry_year},
                "status": a.status,
            }
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_sis(out: Path, students: list[Student], people_by_key: dict[str, Person],
              programmes: list[Programme], rng: random.Random) -> None:
    """Legacy student record exports: pipe-delimited, upper-case surnames, DD-MON-YYYY dates."""
    folder = _ensure(out / "sis")
    with open(folder / "STU_EXTRACT.txt", "w", newline="", encoding="utf-8") as f:
        f.write("STU_CODE|STU_SURN|STU_FNM1|STU_DOB|STU_EMAD|STU_PCOD|STU_FEES|ROUTE|ENTRY_YR|STU_YEAR|STU_STAT\n")
        for s in students:
            p = people_by_key[s.person_key]
            row = [
                s.sis_student_id,
                mess.maybe_trailing_space(p.last_name.upper(), rng),
                p.first_name,
                mess.sis_date(p.date_of_birth),
                p.email,
                p.postcode or "",
                "H" if s.fee_status == "Home" else "O",
                s.sis_route,
                str(s.entry_year),
                str(s.year_of_study),
                {"Enrolled": "EN", "Interrupted": "IN", "Withdrawn": "WD"}[s.status],
            ]
            f.write("|".join(row) + "\n")
    with open(folder / "ROUTES.txt", "w", newline="", encoding="utf-8") as f:
        f.write("ROU_CODE|ROU_NAME|ROU_LEVL|ROU_STAT\n")
        for p in programmes:
            f.write(f"{p.sis_route}|{p.award} {p.title_sis}|{p.level}|{'A' if p.status_sis == 'Active' else 'R'}\n")


def write_finance(out: Path, students: list[Student], people_by_key: dict[str, Person],
                  programmes_by_route: dict[str, Programme], rng: random.Random) -> None:
    """Finance exports: Windows-1252 encoding, UK dates, money as '9,535.00', awkward headers."""
    folder = _ensure(out / "finance")
    with open(folder / "customers_export.csv", "w", newline="", encoding="cp1252", errors="replace") as f:
        w = csv.writer(f)
        w.writerow(["Customer No", "Customer Name", "Student Ref", "Fee Code", "Academic Year",
                    "Invoice Date", "Invoice Amount", "Amount Paid", "Balance", "Account Status"])
        for i, s in enumerate(students, start=1):
            if s.status == "Withdrawn" and rng.random() < 0.5:
                continue
            p = people_by_key[s.person_key]
            prog = programmes_by_route[s.sis_route]
            paid = s.annual_fee if rng.random() < 0.7 else rng.choice([0, s.annual_fee / 2, s.annual_fee / 3])
            w.writerow([
                f"C{100000 + i}",
                f"{p.last_name}, {p.first_name}",
                s.sis_student_id if rng.random() > 0.01 else "",   # a few customers lost their student link
                prog.finance_code,
                "AY2627",
                mess.finance_date(datetime(2026, 9, rng.randint(1, 30))),
                mess.money(s.annual_fee),
                mess.money(paid),
                mess.money(s.annual_fee - paid),
                "Open" if paid < s.annual_fee else "Settled",
            ])
