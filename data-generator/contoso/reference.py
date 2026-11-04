"""Reference data for Contoso University: faculties, programmes and the codes
each system uses for the same programme.

Every system names programmes differently, exactly like a real university:

    CRM (Dataverse)        CS-BSC-2027      readable code + intake year
    Student records (SIS)  UG0451           legacy route code, no year
    UCAS                   G400             4-character UCAS course code
    Finance (ERP)          F-SCI-0451       fee code, grouped by faculty

The mapping between them lives in code_map.csv. Integrations must use it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

FACULTIES = {
    "SCI": ("Faculty of Science and Engineering", [
        ("Computer Science", "CS", "G400"), ("Software Engineering", "SE", "G600"),
        ("Data Science", "DS", "G300"), ("Cyber Security", "CY", "G550"),
        ("Artificial Intelligence", "AI", "G700"), ("Mechanical Engineering", "ME", "H300"),
        ("Electrical and Electronic Engineering", "EE", "H600"), ("Civil Engineering", "CE", "H200"),
        ("Robotics Engineering", "RE", "H670"), ("Mathematics", "MA", "G100"),
        ("Physics", "PH", "F300"), ("Chemistry", "CH", "F100"),
        ("Biomedical Science", "BM", "B900"), ("Forensic Science", "FS", "F410"),
        ("Environmental Science", "ES", "F850"),
    ]),
    "HEA": ("Faculty of Health and Life Sciences", [
        ("Adult Nursing", "AN", "B740"), ("Children's Nursing", "CN", "B730"),
        ("Mental Health Nursing", "MN", "B760"), ("Midwifery", "MW", "B720"),
        ("Paramedic Science", "PS", "B950"), ("Physiotherapy", "PT", "B160"),
        ("Psychology", "PY", "C800"), ("Sport and Exercise Science", "SX", "C600"),
        ("Nutrition", "NU", "B400"), ("Occupational Therapy", "OT", "B920"),
    ]),
    "BUS": ("Faculty of Business and Law", [
        ("Accounting and Finance", "AF", "N400"), ("Business Management", "BM2", "N200"),
        ("Marketing", "MK", "N500"), ("Economics", "EC", "L100"),
        ("Law", "LW", "M100"), ("Criminology", "CR", "L370"),
        ("International Business", "IB", "N120"), ("Human Resource Management", "HR", "N600"),
        ("Tourism Management", "TM", "N800"), ("Events Management", "EV", "N820"),
    ]),
    "ART": ("Faculty of Arts, Humanities and Education", [
        ("English Literature", "EL", "Q300"), ("History", "HI", "V100"),
        ("Fine Art", "FA", "W100"), ("Graphic Design", "GD", "W210"),
        ("Games Design", "GM", "I620"), ("Film Production", "FP", "W610"),
        ("Music Production", "MP", "J930"), ("Journalism", "JN", "P500"),
        ("Primary Education", "PE", "X100"), ("Social Work", "SW", "L500"),
    ]),
}

UG_AWARDS = {"SCI": ["BSc", "MEng"], "HEA": ["BSc"], "BUS": ["BSc", "BA", "LLB"], "ART": ["BA"]}
PG_AWARDS = {"SCI": ["MSc"], "HEA": ["MSc"], "BUS": ["MSc", "MA", "LLM"], "ART": ["MA"]}

# Annual tuition fees in pounds (illustrative, not real fee levels)
FEES = {
    ("UG", "Home"): 9535, ("UG", "International"): 17500,
    ("PG", "Home"): 10500, ("PG", "International"): 19000,
}


@dataclass
class Programme:
    faculty_code: str
    faculty_name: str
    title: str
    level: str          # UG or PG
    award: str          # BSc, MSc, ...
    duration_years: int
    mode: str           # Full-time / Part-time
    crm_code: str       # CS-BSC (intake year added per cycle)
    sis_route: str      # UG0451
    ucas_code: str | None  # only UG programmes go through UCAS
    finance_code: str   # F-SCI-0451
    status_sis: str = "Active"     # Active / Retired
    title_sis: str = ""            # SIS sometimes holds an older title
    notes: list[str] = field(default_factory=list)

    @property
    def full_title(self) -> str:
        return f"{self.award} (Hons) {self.title}" if self.level == "UG" and self.award not in ("MEng", "LLB") else f"{self.award} {self.title}"


def build_programmes(rng: random.Random) -> list[Programme]:
    programmes: list[Programme] = []
    route_no = 401
    for fac_code, (fac_name, subjects) in FACULTIES.items():
        for title, abbr, ucas_base in subjects:
            for award in UG_AWARDS[fac_code]:
                if award == "MEng" and title not in ("Mechanical Engineering", "Electrical and Electronic Engineering", "Civil Engineering", "Robotics Engineering", "Software Engineering"):
                    continue
                if award == "LLB" and title != "Law":
                    continue
                if award in ("BSc", "BA") and title == "Law":
                    continue
                if fac_code == "BUS" and award == "BA" and title not in ("Business Management", "Marketing", "Tourism Management", "Events Management", "Criminology"):
                    continue
                if fac_code == "BUS" and award == "BSc" and title in ("Criminology", "Tourism Management", "Events Management"):
                    continue
                route = f"UG{route_no:04d}"
                ucas = ucas_base if award in ("BSc", "BA", "LLB") else ucas_base[0] + str(int(ucas_base[1:]) + 4).zfill(3)
                programmes.append(Programme(
                    fac_code, fac_name, title, "UG", award, 4 if award == "MEng" else 3, "Full-time",
                    f"{abbr}-{award.upper()}", route, ucas, f"F-{fac_code}-{route_no:04d}",
                ))
                route_no += 1
                # Most UK degrees also run "with Foundation Year": one extra year, its own UCAS code
                if award != "MEng" and fac_code != "HEA":
                    route = f"UG{route_no:04d}"
                    programmes.append(Programme(
                        fac_code, fac_name, f"{title} with Foundation Year", "UG", award, 4, "Full-time",
                        f"{abbr}-{award.upper()}-FY", route, ucas[0] + str(int(ucas[1:]) + 3).zfill(3),
                        f"F-{fac_code}-{route_no:04d}",
                    ))
                    route_no += 1
            for award in PG_AWARDS[fac_code]:
                if award == "LLM" and title != "Law":
                    continue
                if fac_code == "BUS" and award == "MA" and title not in ("Marketing", "Human Resource Management", "International Business"):
                    continue
                if title == "Law" and award != "LLM":
                    continue
                if rng.random() < 0.25:  # not every subject has a postgraduate course
                    continue
                route = f"PG{route_no:04d}"
                programmes.append(Programme(
                    fac_code, fac_name, title, "PG", award, 1, rng.choice(["Full-time", "Full-time", "Part-time"]),
                    f"{abbr}-{award.upper()}", route, None, f"F-{fac_code}-{route_no:04d}",
                ))
                route_no += 1

    # UCAS codes must be unique per university: bump the number on any clash (e.g. BA vs BSc)
    seen: set[str] = set()
    for p in programmes:
        if not p.ucas_code:
            continue
        code = p.ucas_code
        while code in seen:
            code = code[0] + str(int(code[1:]) + 1).zfill(3)
        p.ucas_code = code
        seen.add(code)

    # --- Real-world drift between systems (deliberate) -------------------
    # 1. Three programmes were retired in the SIS but are still live in the CRM.
    for p in rng.sample(programmes, 3):
        p.status_sis = "Retired"
        p.notes.append("Retired in SIS, still open in CRM")
    # 2. Two programmes were renamed in the CRM; the SIS still has the old title.
    renames = {"Business Management": "Business and Management", "Games Design": "Games Design and Development"}
    for p in programmes:
        p.title_sis = p.title
        if p.title in renames and p.level == "UG":
            p.title_sis = p.title
            p.notes.append(f"CRM title differs from SIS title '{p.title}'")
            p.title = renames[p.title]
    return programmes


def academic_periods() -> list[dict]:
    rows = []
    for start in range(2024, 2029):
        rows.append({
            "crm_name": f"{start}/{str(start + 1)[2:]}",          # 2027/28
            "sis_code": f"{start}/{start + 1}",                  # 2027/2028
            "finance_code": f"AY{str(start)[2:]}{str(start + 1)[2:]}",  # AY2728
            "start_date": f"{start}-09-21",
            "end_date": f"{start + 1}-06-30",
        })
    return rows
