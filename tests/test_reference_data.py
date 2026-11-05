import random

from contoso.reference import build_programmes


def programmes():
    return build_programmes(random.Random(2027))


def test_enough_programmes():
    assert len(programmes()) >= 100


def test_ucas_codes_are_unique():
    codes = [p.ucas_code for p in programmes() if p.ucas_code]
    assert len(codes) == len(set(codes))


def test_crm_and_sis_codes_are_unique():
    ps = programmes()
    assert len({p.crm_code for p in ps}) == len(ps)
    assert len({p.sis_route for p in ps}) == len(ps)


def test_deliberate_drift_exists():
    ps = programmes()
    assert sum(p.status_sis == "Retired" for p in ps) == 3
    assert any(p.title != p.title_sis for p in ps)


def test_postgraduate_has_no_ucas_code():
    assert all(p.ucas_code is None for p in programmes() if p.level == "PG")
