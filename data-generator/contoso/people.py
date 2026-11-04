"""People: applicants for the 2027 intake and current students from earlier intakes.

The generator first creates the *truth*: one clean record per real person.
Each system then gets its own (imperfect) copy, see mess.py and writers.py.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta

from faker import Faker

from .reference import FEES, Programme

# Names Faker's en_GB list rarely produces, so data has the variety a real UK university sees.
EXTRA_FIRST = ["Zoë", "José", "Siobhán", "Chloé", "Niamh", "Aoife", "Oluwaseun", "Chukwuemeka", "Adaeze",
               "Mohammed", "Aisha", "Priya", "Arjun", "Wei", "Mei", "Hiroshi", "Søren", "Łukasz", "Kateřina",
               "Björn", "Fatima", "Yusuf", "Amara", "Kwame", "Tomás", "Renée", "Anaïs", "Ngozi", "Seo-yeon", "Dmitri"]
EXTRA_LAST = ["O'Brien", "O'Connor", "McDonald", "Smith-Jones", "Okafor", "Adeyemi", "Nwosu", "Khan", "Patel",
              "Singh", "Chen", "Nguyen", "Kowalski", "Müller", "García", "D'Souza", "Fernández", "Ó Súilleabháin",
              "van der Berg", "Bianchi", "Haddad", "Mensah", "Ivanova", "Kim", "Lee-Wright"]

COUNTRIES_INTL = ["Nigeria", "India", "China", "Pakistan", "Ghana", "Malaysia", "United States", "Saudi Arabia",
                  "Vietnam", "Kenya", "Germany", "Italy", "Spain", "Poland", "Bangladesh"]

SCHOOLS = ["Derby College", "Nottingham High School", "Leicester College", "Sheffield Sixth Form",
           "Birmingham Metropolitan College", "Chesterfield College", "Burton and South Derbyshire College",
           "Loughborough College", "Wilmorton Academy", "Lincoln College", "Stoke Sixth Form College",
           "Online / overseas qualification"]

A_LEVEL_GRADES = ["A*", "A", "B", "C", "D", "E"]
APPLICATION_STATUSES_UG = ["Submitted", "Offer - Conditional", "Offer - Unconditional", "Unsuccessful", "Withdrawn"]
REPLY_STATUSES = ["Firm", "Insurance", "Declined", "No reply"]


@dataclass
class Person:
    person_key: str               # hidden "truth" ID: the same real human across every system
    first_name: str
    last_name: str
    preferred_name: str | None
    date_of_birth: date
    email: str
    phone: str | None
    address_line1: str
    city: str
    postcode: str | None
    country: str
    fee_status: str               # Home / International
    marketing_consent: bool


@dataclass
class Application:
    application_id: str           # portal ID, e.g. APP-2027-004512 (CRM alternate key)
    person_key: str
    route: str                    # UCAS / Direct / Clearing
    ucas_personal_id: str | None  # 123-456-7890, UG via UCAS only
    programme_crm_code: str
    programme_ucas_code: str | None
    programme_sis_route: str
    level: str
    entry_year: int
    submitted_at: datetime
    school: str | None
    predicted_grades: str | None
    status: str
    decision_at: datetime | None
    reply: str | None
    enrolled: bool = False
    sis_student_id: str | None = None
    history: list[dict] = field(default_factory=list)


@dataclass
class Student:
    sis_student_id: str           # 8 digits, assigned by the SIS
    person_key: str
    sis_route: str
    entry_year: int
    year_of_study: int
    status: str                   # Enrolled / Interrupted / Withdrawn / Completed
    fee_status: str
    annual_fee: int


class PeopleFactory:
    def __init__(self, rng: random.Random, faker: Faker):
        self.rng = rng
        self.fake = faker
        self._person_no = 0
        self._app_no = 0
        self._student_no = 10020000
        self._ucas_ids: set[str] = set()

    # -- people -----------------------------------------------------------
    def person(self, age_range=(17, 19), intl_share=0.22) -> Person:
        r, f = self.rng, self.fake
        self._person_no += 1
        first = r.choice(EXTRA_FIRST) if r.random() < 0.18 else f.first_name()
        last = r.choice(EXTRA_LAST) if r.random() < 0.18 else f.last_name()
        intl = r.random() < intl_share
        today = date(2026, 9, 1)
        dob = today - timedelta(days=r.randint(age_range[0] * 365, age_range[1] * 365 + 364))
        # Email addresses are plain ASCII even when names are not: Siobhán García -> siobhan.garcia
        ascii_name = unicodedata.normalize("NFKD", f"{first}.{last}").encode("ascii", "ignore").decode()
        local = ascii_name.lower().replace(" ", "").replace("'", "")
        email = f"{local}{r.randint(1, 999) if r.random() < 0.6 else ''}@{r.choice(['gmail.com', 'outlook.com', 'yahoo.co.uk', 'hotmail.com', 'icloud.com'])}"
        return Person(
            person_key=f"P{self._person_no:06d}",
            first_name=first,
            last_name=last,
            preferred_name=(r.choice([first[:3], f.first_name()]) if r.random() < 0.07 else None),
            date_of_birth=dob,
            email=email,
            phone=(f.phone_number() if r.random() > 0.04 else None),
            address_line1=f.street_address().replace("\n", ", "),
            city=f.city() if not intl else r.choice(["Lagos", "Delhi", "Beijing", "Lahore", "Accra", "Kuala Lumpur", "Boston", "Riyadh", "Hanoi", "Nairobi", "Berlin", "Milan", "Madrid", "Warsaw", "Dhaka"]),
            postcode=(f.postcode() if not intl else None),
            country=("United Kingdom" if not intl else r.choice(COUNTRIES_INTL)),
            fee_status=("International" if intl else "Home"),
            marketing_consent=r.random() < 0.63,
        )

    def ucas_id(self) -> str:
        while True:
            raw = f"{self.rng.randint(100, 999)}-{self.rng.randint(100, 999)}-{self.rng.randint(1000, 9999)}"
            if raw not in self._ucas_ids:
                self._ucas_ids.add(raw)
                return raw

    # -- applications for the 2027 intake ---------------------------------
    def application(self, person: Person, programme: Programme, route: str, submitted: datetime) -> Application:
        r = self.rng
        self._app_no += 1
        app = Application(
            application_id=f"APP-2027-{self._app_no:06d}",
            person_key=person.person_key,
            route=route,
            ucas_personal_id=self.ucas_id() if route in ("UCAS", "Clearing") and programme.level == "UG" else None,
            programme_crm_code=f"{programme.crm_code}-2027",
            programme_ucas_code=programme.ucas_code if programme.level == "UG" else None,
            programme_sis_route=programme.sis_route,
            level=programme.level,
            entry_year=2027,
            submitted_at=submitted,
            school=(r.choice(SCHOOLS) if programme.level == "UG" else None),
            predicted_grades=("".join(sorted(r.choices(A_LEVEL_GRADES[:4], k=3), key=A_LEVEL_GRADES.index)) if programme.level == "UG" else None),
            status="Submitted",
            decision_at=None,
            reply=None,
        )
        app.history.append({"at": submitted.isoformat(), "status": "Submitted"})
        if route == "Clearing":
            # Clearing decisions are fast and mostly unconditional
            app.status = r.choices(["Offer - Unconditional", "Unsuccessful"], weights=[85, 15])[0]
            app.decision_at = submitted + timedelta(hours=r.randint(1, 30))
            app.reply = "Firm" if app.status.startswith("Offer") and r.random() < 0.8 else None
        else:
            app.status = r.choices(APPLICATION_STATUSES_UG, weights=[18, 46, 14, 14, 8])[0]
            if app.status != "Submitted":
                app.decision_at = submitted + timedelta(days=r.randint(3, 75))
            if app.status.startswith("Offer"):
                app.reply = r.choices(REPLY_STATUSES, weights=[45, 20, 20, 15])[0]
        if app.decision_at:
            app.history.append({"at": app.decision_at.isoformat(), "status": app.status})
        return app

    # -- current students (earlier intakes) --------------------------------
    def student(self, person: Person, programme: Programme, entry_year: int) -> Student:
        r = self.rng
        self._student_no += r.randint(1, 3)
        year_of_study = min(2026 - entry_year + 1, programme.duration_years)
        status = r.choices(["Enrolled", "Interrupted", "Withdrawn"], weights=[90, 4, 6])[0]
        return Student(
            sis_student_id=str(self._student_no),
            person_key=person.person_key,
            sis_route=programme.sis_route,
            entry_year=entry_year,
            year_of_study=year_of_study,
            status=status,
            fee_status=person.fee_status,
            annual_fee=FEES[(programme.level, person.fee_status)],
        )


def as_dict(obj) -> dict:
    d = asdict(obj)
    for k, v in d.items():
        if isinstance(v, (date, datetime)):
            d[k] = v.isoformat()
    return d
