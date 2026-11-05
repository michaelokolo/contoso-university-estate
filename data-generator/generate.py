"""Contoso University data generator.

Creates one admissions cycle (2027 entry) plus current students, and writes each
system's own imperfect copy of the data.

    python generate.py                      # full size: about 20,000 applications
    python generate.py --applications 2000  # small run for quick tests
    python generate.py --seed 7             # a different (but repeatable) world
"""

from __future__ import annotations

import argparse
import random
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

from contoso import mess
from contoso.people import PeopleFactory
from contoso.reference import FEES, academic_periods, build_programmes
from contoso.writers import write_finance, write_portal, write_reference, write_sis, write_truth, write_ucas

# Key dates in the 2027-entry cycle (illustrative)
CYCLE_OPENS = datetime(2026, 9, 2)
EQUAL_CONSIDERATION = datetime(2027, 1, 27)
CYCLE_MAIN_ENDS = datetime(2027, 6, 30)
RESULTS_DAY = datetime(2027, 8, 12, 8, 0)   # Clearing spike starts here


def random_ucas_date(rng: random.Random) -> datetime:
    """Most UCAS applications land just before the January deadline."""
    if rng.random() < 0.55:
        start, end = EQUAL_CONSIDERATION - timedelta(days=21), EQUAL_CONSIDERATION
    elif rng.random() < 0.7:
        start, end = CYCLE_OPENS, EQUAL_CONSIDERATION
    else:
        start, end = EQUAL_CONSIDERATION, CYCLE_MAIN_ENDS
    return start + timedelta(seconds=rng.randint(0, int((end - start).total_seconds())))


def random_clearing_date(rng: random.Random) -> datetime:
    """About 60% of Clearing applications arrive on results day itself."""
    day = 0 if rng.random() < 0.6 else rng.choice([1, 1, 2, 3, 4, 7, 10])
    return RESULTS_DAY + timedelta(days=day, minutes=rng.randint(0, 12 * 60))


def random_direct_date(rng: random.Random) -> datetime:
    start, end = datetime(2026, 9, 1), datetime(2027, 8, 31)
    return start + timedelta(seconds=rng.randint(0, int((end - start).total_seconds())))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--applications", type=int, default=20000, help="total applications (default 20000)")
    parser.add_argument("--students", type=int, default=6000, help="current students (default 6000)")
    parser.add_argument("--seed", type=int, default=2027, help="random seed, so runs are repeatable")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "output")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    fake = Faker("en_GB")
    Faker.seed(args.seed)
    factory = PeopleFactory(rng, fake)

    programmes = build_programmes(rng)
    ug = [p for p in programmes if p.level == "UG"]
    pg = [p for p in programmes if p.level == "PG"]
    by_route = {p.sis_route: p for p in programmes}

    # Shares of the cycle: UCAS 65%, Clearing 15%, direct UG 7.5%, PG 12.5%
    n = args.applications
    plan = [("UCAS", ug, int(n * 0.65)), ("Clearing", ug, int(n * 0.15)),
            ("Direct", ug, int(n * 0.075)), ("Direct", pg, n - int(n * 0.65) - int(n * 0.15) - int(n * 0.075))]

    people, apps = [], []
    for route, pool, count in plan:
        for _ in range(count):
            level_pg = pool is pg
            person = factory.person(age_range=(21, 40) if level_pg else (17, 19), intl_share=0.45 if level_pg else 0.18)
            programme = rng.choice(pool)
            submitted = {"UCAS": random_ucas_date, "Clearing": random_clearing_date}.get(route, random_direct_date)(rng)
            people.append(person)
            apps.append(factory.application(person, programme, route, submitted))

    # Duplicates: about 2% of people apply twice (UCAS and direct, or two direct forms),
    # with their details typed slightly differently. The truth keeps the same person_key.
    people_by_key = {p.person_key: p for p in people}
    dupes = 0
    for a in rng.sample(apps, int(len(apps) * 0.02)):
        original = people_by_key[a.person_key]
        twin = factory.person()
        twin.person_key = original.person_key
        twin.first_name, twin.last_name = mess.variant_name(original.first_name, original.last_name, rng)
        twin.date_of_birth, twin.country, twin.fee_status = original.date_of_birth, original.country, original.fee_status
        twin.email = mess.typo_email(original.email, rng)
        twin.postcode, twin.city = original.postcode, original.city
        programme = by_route[a.programme_sis_route]
        dup_app = factory.application(twin, programme, "Direct", a.submitted_at + timedelta(days=rng.randint(1, 40)))
        apps.append(dup_app)
        people_by_key[f"{twin.person_key}#dup{dupes}"] = twin   # kept so writers can find the variant
        dup_app.person_key = f"{twin.person_key}#dup{dupes}"
        dupes += 1

    # Current students from the 2024-2026 intakes
    students = []
    for _ in range(args.students):
        entry = rng.choice([2024, 2025, 2026])
        programme = rng.choice([p for p in programmes if p.level == "UG" or entry == 2026])
        person = factory.person(age_range=(18 + 2026 - entry, 21 + 2026 - entry))
        people_by_key[person.person_key] = person
        students.append(factory.student(person, programme, entry))

    out: Path = args.out
    write_reference(out, programmes, academic_periods(), FEES)
    write_truth(out, list(people_by_key.values()), apps, students)
    ucas_days = write_ucas(out, apps, people_by_key, rng)
    portal_count = write_portal(out, apps, people_by_key, rng)
    write_sis(out, students, people_by_key, programmes, rng)
    write_finance(out, students, people_by_key, by_route, rng)

    routes = Counter(a.route for a in apps)
    print(f"Programmes:      {len(programmes)} ({len(ug)} UG, {len(pg)} PG)")
    print(f"Applications:    {len(apps)}  {dict(routes)}  (includes {dupes} duplicates)")
    print(f"UCAS files:      {ucas_days} daily XML files")
    print(f"Portal records:  {portal_count}")
    print(f"Students:        {len(students)}")
    print(f"Output folder:   {out}")


if __name__ == "__main__":
    main()
