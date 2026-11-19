# Evaluation — engine `rules`, model `-`, files `*.txt`

Documents: **9** · measured 2026-11-19T22:09:28

| Field | Accuracy |
|---|---|
| doc_type | 100% |
| expiry_date | 100% |
| doc_number | 100% |
| plate | 100% |

- All fields correct: 9/9
- Sent to human review: 9/9
- **False-confident** (wrong but auto-confirmed): 0/9
- Latency: avg **0.0 s**, p95 0.2 s per document
- Tokens per document: ~0 in / ~0 out
- Cost: **0.000 THB per document** · 0.00 THB this run · ~0 THB/year for 130 documents (1 USD = 35.0 THB)

| File | type | expiry | number | plate/driver | extracted expiry | conf. | review | s | tokens in/out | THB |
|---|---|---|---|---|---|---|---|---|---|---|
| 01_tax_70-1234 | ✅ | ✅ | ✅ | ✅ | 26/11/69 → 2026-11-26 | 0.60 | 🟣 | 0.2 | 0/0 | 0.000 |
| 02_tax_72-4410 | ✅ | ✅ | ✅ | ✅ | 22 กรกฎาคม 2570 → 2027-07-22 | 0.40 | 🟣 | 0.0 | 0/0 | 0.000 |
| 03_prb_71-0099 | ✅ | ✅ | ✅ | ✅ | 1 ธ.ค. 2569 → 2026-12-01 | 0.60 | 🟣 | 0.0 | 0/0 | 0.000 |
| 04_prb_70-5678 | ✅ | ✅ | ✅ | ✅ | 17/12/2569 → 2026-12-17 | 0.60 | 🟣 | 0.0 | 0/0 | 0.000 |
| 05_insurance_70-1234 | ✅ | ✅ | ✅ | ✅ | 18 กุมภาพันธ์ 2570 → 2027-02-18 | 0.60 | 🟣 | 0.0 | 0/0 | 0.000 |
| 06_insurance_72-9045_english | ✅ | ✅ | ✅ | ✅ | 4 Dec 2026 → 2026-12-04 | 0.60 | 🟣 | 0.0 | 0/0 | 0.000 |
| 07_insurance_71-3307 | ✅ | ✅ | ✅ | ✅ | 29 ธ.ค. 2569 → 2026-12-29 | 0.40 | 🟣 | 0.0 | 0/0 | 0.000 |
| 08_driver_license_surachai | ✅ | ✅ | ✅ | ✅ | 2 ธันวาคม 2569 → 2026-12-02 | 0.40 | 🟣 | 0.0 | 0/0 | 0.000 |
| 09_driver_license_boonlert | ✅ | ✅ | ✅ | ✅ | 9 Jul 2027 → 2027-07-09 | 0.60 | 🟣 | 0.0 | 0/0 | 0.000 |
