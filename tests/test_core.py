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
    assert compute_status({"review_status": "PENDING_REVIEW", "expiry_date": "2027-06-01"}, today) == "PENDING_REVIEW"


def test_validator_catches_year_errors():
    today = date(2026, 11, 14)
    good = {"doc_type": "COMPULSORY_INSURANCE", "doc_number": "1", "vehicle_plate": "70-1234 ชลบุรี",
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
    bad_plate = dict(ex, vehicle_plate="ABC")
    assert any("รูปแบบทะเบียน" in p for p in validator.validate(bad_plate, date(2026, 11, 14)))


def test_confidence_and_review():
    ex = {"field_confidence": {"doc_type": 0.99, "expiry_date": 0.95, "doc_number": 0.9, "vehicle_plate": 0.92}}
    assert validator.score(ex, []) == 0.9
    assert validator.score(ex, ["problem"]) == 0.45
    assert not validator.needs_review(0.9, [])
    assert validator.needs_review(0.9, ["problem"])
    assert validator.needs_review(0.7, [])


@pytest.mark.parametrize("left,expected", [(120, None), (90, 90), (75, 90), (30, 30), (7, 7), (3, 7), (0, 0), (-5, 0)])
def test_due_threshold(left, expected):
    assert due_threshold(left) == expected


def test_cost_and_usage_accounting():
    from types import SimpleNamespace

    from app import config
    from app.extraction.extractor import usage_of

    # 1M input + 1M output tokens on each model = its list price
    assert config.cost_usd("claude-opus-5-5", 1_000_000, 1_000_000) == 24.0
    assert config.cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == 0.6
    assert config.cost_usd("unknown-model", 10, 10) is None
    resp = SimpleNamespace(model="claude-sonnet-5-5",
                           usage=SimpleNamespace(input_tokens=1500, output_tokens=500,
                                                 cache_creation_input_tokens=0, cache_read_input_tokens=0))
    u = usage_of(resp, 3.14159)
    assert u["seconds"] == 3.14 and u["input_tokens"] == 1500 and u["output_tokens"] == 500
    assert abs(u["cost_usd"] - (1500 * 2 + 500 * 10) / 1e6) < 1e-12
    assert abs(u["cost_thb"] - u["cost_usd"] * config.USD_TO_THB) < 1e-3
