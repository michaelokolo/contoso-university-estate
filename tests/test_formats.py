from datetime import date

import pytest

from contoso import mess
from tests.conftest import load_service

sis = load_service("sis")


def test_sis_date_format():
    assert mess.sis_date(date(2026, 11, 4)) == "04-NOV-2026"


def test_finance_money_format():
    assert mess.money(9535) == "9,535.00"


def test_sis_parses_its_own_dates():
    assert sis.parse_sis_date("10-DEC-2008") == date(2008, 12, 10)


@pytest.mark.parametrize("bad", ["2008-12-10", "10/12/2008", "10-Dec-2008", "32-JAN-2008", ""])
def test_sis_rejects_other_date_formats(bad):
    with pytest.raises((sis.SisFault, ValueError)):
        sis.parse_sis_date(bad)
