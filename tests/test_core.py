from datetime import date

import pytest

from app.core import validator
from app.core.notifier import due_threshold
from app.core.status import compute_status
from app.extraction.thai_date import find_dates, normalize_year, parse_date, to_thai


@pytest.mark.parametrize("text,expected", [
    ("28 ก.พ. 2570", date(2027, 2, 28)),
    ("15 มกราคม 2570", date(2027, 1, 15)),
    ("๑ ธ.ค. ๒๕๖๙", date(2026, 12, 1)),
    ("26/11/69", date(2026, 11, 26)),
    ("26/11/2569", date(2026, 11, 26)),
    ("26/11/2026", date(2026, 11, 26)),
    ("2027-03-31", date(2027, 3, 31)),
    ("31 Mar 2027", date(2027, 3, 31)),
    ("March 31, 2027", date(2027, 3, 31)),
    ("หมดอายุ 1 ม.ค. 2571", date(2028, 1, 1)),
])
def test_parse_date(text, expected):
    assert parse_date(text) == expected


def test_invalid_date_returns_none():
    assert parse_date("31 ก.พ. 2570") is None
    assert parse_date("ไม่มีวันที่") is None


def test_normalize_year():
    assert normalize_year(2569) == 2026
    assert normalize_year(2026) == 2026
    assert normalize_year(69, assume_buddhist=True) == 2026
    assert normalize_year(26, assume_buddhist=False) == 2026


def test_find_dates_and_thai_format():
    found = find_dates("ตั้งแต่ 18 กุมภาพันธ์ 2569 ถึง 18 กุมภาพันธ์ 2570")
    assert [d for _, d in found] == [date(2026, 2, 18), date(2027, 2, 18)]
    assert to_thai(date(2027, 2, 28)) == "28 ก.พ. 2570"


def test_status_rules():
    today = date(2026, 11, 14)
    assert compute_status({"doc_type": "VEHICLE_TAX", "expiry_date": "2026-11-01"}, today) == "EXPIRED"
    assert compute_status({"doc_type": "VEHICLE_TAX", "expiry_date": "2026-12-01"}, today) == "EXPIRING"
    assert compute_status({"doc_type": "VEHICLE_TAX", "expiry_date": "2027-06-01"}, today) == "VALID"
    # work permits use a longer 60-day window
    assert compute_status({"doc_type": "WORK_PERMIT", "expiry_date": "2027-01-05"}, today) == "EXPIRING"
    assert compute_status({"review_status": "PENDING_REVIEW", "expiry_date": "2027-06-01"}, today) == "PENDING_REVIEW"


def test_validator_catches_year_errors():
    today = date(2026, 11, 14)
    good = {"doc_type": "DRIVER_LICENSE", "doc_number": "1", "holder_name": "x",
            "issue_date": date(2022, 1, 15), "expiry_date": date(2027, 1, 15)}
    assert validator.validate(good, today) == []
    # BE year not converted -> 543 years in the future
    bad = dict(good, expiry_date=date(2570, 1, 15))
    assert any("พ.ศ." in p for p in validator.validate(bad, today))
    swapped = dict(good, issue_date=date(2027, 1, 15), expiry_date=date(2022, 1, 15))
    assert validator.validate(swapped, today)


def test_vehicle_doc_requires_plate():
    ex = {"doc_type": "VEHICLE_TAX", "doc_number": "1", "holder_name": "x", "expiry_date": date(2027, 1, 1)}
    assert any("ทะเบียน" in p for p in validator.validate(ex, date(2026, 11, 14)))


def test_confidence_and_review():
    ex = {"field_confidence": {"doc_type": 0.99, "expiry_date": 0.95, "doc_number": 0.9, "holder_name": 0.92}}
    assert validator.score(ex, []) == 0.9
    assert validator.score(ex, ["problem"]) == 0.45
    assert not validator.needs_review(0.9, [])
    assert validator.needs_review(0.9, ["problem"])
    assert validator.needs_review(0.7, [])


@pytest.mark.parametrize("left,expected", [(120, None), (90, 90), (75, 90), (30, 30), (7, 7), (3, 7), (0, 0), (-5, 0)])
def test_due_threshold(left, expected):
    assert due_threshold(left) == expected
