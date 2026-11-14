"""Parse Thai / English date strings and normalise Buddhist Era (พ.ศ.) years to ค.ศ.

The LLM returns the raw date text it read; we convert it here in code so that
year arithmetic (พ.ศ. - 543) never depends on the model.
"""
from __future__ import annotations

import re
from datetime import date

THAI_MONTHS = {
    # full names
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4, "พฤษภาคม": 5, "มิถุนายน": 6,
    "กรกฎาคม": 7, "สิงหาคม": 8, "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
    # abbreviations (with and without dots)
    "ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6,
    "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12,
    "มค": 1, "กพ": 2, "มีค": 3, "เมย": 4, "พค": 5, "มิย": 6,
    "กค": 7, "สค": 8, "กย": 9, "ตค": 10, "พย": 11, "ธค": 12,
}
EN_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def normalize_year(year: int, assume_buddhist: bool | None = None) -> int:
    """Return a Gregorian year.

    * 4-digit year > 2400  -> Buddhist Era, subtract 543
    * 2-digit year         -> if assume_buddhist (default when ambiguous: True for >= 50)
                              treat as 25xx BE, else 20xx CE
    """
    if year >= 2400:
        return year - 543
    if year < 100:
        if assume_buddhist is None:
            # Thai docs commonly write "28/02/70" meaning 2570 BE.
            assume_buddhist = year >= 50
        return (2500 + year - 543) if assume_buddhist else (2000 + year)
    return year


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date(text: str | None, assume_buddhist: bool | None = None) -> date | None:
    """Best-effort parse of a single date string. Returns None if not understood."""
    if not text:
        return None
    s = str(text).strip().translate(THAI_DIGITS)
    s = re.sub(r"^(วันที่|ถึง|หมดอายุ|expiry|expires|exp\.?)[:\s]*", "", s, flags=re.I).strip()
    s = s.replace("พ.ศ.", "").replace("ค.ศ.", "").strip()

    # ISO yyyy-mm-dd
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return _safe_date(normalize_year(y), mo, d)

    # dd/mm/yyyy, dd-mm-yy, dd.mm.yyyy
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
    if m:
        d, mo, y = map(int, m.groups())
        return _safe_date(normalize_year(y, assume_buddhist), mo, d)

    # dd <thai month> yyyy
    for name, mo in sorted(THAI_MONTHS.items(), key=lambda kv: -len(kv[0])):
        if name in s:
            nums = re.findall(r"\d+", s)
            if len(nums) >= 2:
                d, y = int(nums[0]), int(nums[-1])
                return _safe_date(normalize_year(y, assume_buddhist), mo, d)

    # dd Mon yyyy / Mon dd, yyyy (English)
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?,?\s+(\d{2,4})", s)
    if m:
        d, mon, y = m.groups()
        mo = EN_MONTHS.get(mon.lower())
        if mo:
            return _safe_date(normalize_year(int(y), False), mo, int(d))
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{2,4})", s)
    if m:
        mon, d, y = m.groups()
        mo = EN_MONTHS.get(mon.lower())
        if mo:
            return _safe_date(normalize_year(int(y), False), mo, int(d))
    return None


DATE_PATTERN = re.compile(
    r"(\d{1,2}\s*(?:%s)\s*\d{2,4}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}"
    r"|\d{1,2}\s+[A-Za-z]{3,9}\.?,?\s+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})"
    % "|".join(re.escape(k) for k in sorted(THAI_MONTHS, key=len, reverse=True))
)


def find_dates(text: str) -> list[tuple[str, date]]:
    """Find every date-looking substring in free text."""
    text = text.translate(THAI_DIGITS)
    out = []
    for m in DATE_PATTERN.finditer(text):
        d = parse_date(m.group(0))
        if d:
            out.append((m.group(0), d))
    return out


def to_thai(d: date | None) -> str:
    """Format a date as Thai display text, e.g. 28 ก.พ. 2570."""
    if not d:
        return "-"
    abbr = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    return f"{d.day} {abbr[d.month - 1]} {d.year + 543}"
