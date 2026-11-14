# Evaluation — engine `claude`, files `*.png`

Documents: **7**

| Field | Accuracy |
|---|---|
| doc_type | 7/7 (100%) |
| expiry_date | 7/7 (100%) |
| doc_number | 7/7 (100%) |
| plate | 7/7 (100%) |

- Sent to human review: 0/7
- **False-confident** (wrong but auto-confirmed): 0/7

| File | type | expiry | number | plate | extracted expiry | confidence |
|---|---|---|---|---|---|---|
| 01_tax_70-1234 | ✅ | ✅ | ✅ | ✅ | 26/11/69 → 2026-11-26 | 0.85 |
| 02_tax_72-4410 | ✅ | ✅ | ✅ | ✅ | 22 กรกฎาคม 2570 → 2027-07-22 | 0.93 |
| 03_prb_71-0099 | ✅ | ✅ | ✅ | ✅ | ๑ ธ.ค. ๒๕๖๙ → 2026-12-01 | 0.93 |
| 04_prb_70-5678 | ✅ | ✅ | ✅ | ✅ | 17/12/2569 → 2026-12-17 | 0.93 |
| 05_insurance_70-1234 | ✅ | ✅ | ✅ | ✅ | 18 กุมภาพันธ์ 2570 → 2027-02-18 | 0.95 |
| 06_insurance_72-9045_english | ✅ | ✅ | ✅ | ✅ | 4 Dec 2026 → 2026-12-04 | 0.93 |
| 07_insurance_71-3307 | ✅ | ✅ | ✅ | ✅ | 29 ธ.ค. 2569 → 2026-12-29 | 0.90 |
