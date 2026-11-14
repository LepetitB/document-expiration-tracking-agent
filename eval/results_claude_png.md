# Evaluation — engine `claude`, files `*.png`

Documents: **9**

| Field | Accuracy |
|---|---|
| doc_type | 9/9 (100%) |
| expiry_date | 9/9 (100%) |
| doc_number | 9/9 (100%) |
| plate | 8/9 (89%) |

- Sent to human review: 1/9
- **False-confident** (wrong but auto-confirmed): 0/9

| File | type | expiry | number | plate/driver | extracted expiry | confidence |
|---|---|---|---|---|---|---|
| 01_tax_70-1234 | ✅ | ✅ | ✅ | ✅ | 26/11/69 → 2026-11-26 | 0.90 |
| 02_tax_72-4410 | ✅ | ✅ | ✅ | ✅ | 22 กรกฎาคม 2570 → 2027-07-22 | 0.90 |
| 03_prb_71-0099 | ✅ | ✅ | ✅ | ✅ | ๑ ธ.ค. ๒๕๖๙ → 2026-12-01 | 0.93 |
| 04_prb_70-5678 | ✅ | ✅ | ✅ | ✅ | 17/12/2569 → 2026-12-17 | 0.93 |
| 05_insurance_70-1234 | ✅ | ✅ | ✅ | ✅ | 18 กุมภาพันธ์ 2570 → 2027-02-18 | 0.95 |
| 06_insurance_72-9045_english | ✅ | ✅ | ✅ | ✅ | 4 Dec 2026 → 2026-12-04 | 0.93 |
| 07_insurance_71-3307 | ✅ | ✅ | ✅ | ✅ | 29 ธ.ค. 2569 → 2026-12-29 | 0.93 |
| 08_driver_license_surachai | ✅ | ✅ | ✅ | ❌ | 2 ธันวาคม 2569 → 2026-12-02 | 0.45 |
| 09_driver_license_boonlert | ✅ | ✅ | ✅ | ✅ | 9 Jul 2027 → 2027-07-09 | 0.93 |
