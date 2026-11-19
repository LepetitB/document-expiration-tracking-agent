# Evaluation — engine `claude`, model `claude-haiku-5-5`, files `*.png`

Documents: **9** · measured 2026-11-19T22:13:03

| Field | Accuracy |
|---|---|
| doc_type | 100% |
| expiry_date | 100% |
| doc_number | 100% |
| plate | 89% |

- All fields correct: 8/9
- Sent to human review: 3/9
- **False-confident** (wrong but auto-confirmed): 0/9
- Latency: avg **4.5 s**, p95 5.6 s per document
- Tokens per document: ~2391 in / ~823 out
- Cost: **0.023 THB per document** · 0.20 THB this run · ~3 THB/year for 130 documents (1 USD = 35.0 THB)

| File | type | expiry | number | plate/driver | extracted expiry | conf. | review | s | tokens in/out | THB |
|---|---|---|---|---|---|---|---|---|---|---|
| 01_tax_70-1234 | ✅ | ✅ | ✅ | ✅ | 26/11/69 → 2026-11-26 | 0.70 | 🟣 | 5.6 | 2464/1000 | 0.026 |
| 02_tax_72-4410 | ✅ | ✅ | ✅ | ✅ | 22 กรกฎาคม 2570 → 2027-07-22 | 0.85 | - | 4.5 | 2371/754 | 0.021 |
| 03_prb_71-0099 | ✅ | ✅ | ✅ | ✅ | ๑ ธ.ค. ๒๕๖๙ → 2026-12-01 | 0.90 | - | 5.3 | 2392/1077 | 0.027 |
| 04_prb_70-5678 | ✅ | ✅ | ✅ | ✅ | 17/12/2569 → 2026-12-17 | 0.90 | - | 4.3 | 2371/768 | 0.022 |
| 05_insurance_70-1234 | ✅ | ✅ | ✅ | ✅ | 18 กุมภาพันธ์ 2570 → 2027-02-18 | 0.90 | - | 4.3 | 2320/859 | 0.023 |
| 06_insurance_72-9045_english | ✅ | ✅ | ✅ | ✅ | 4 Dec 2026 → 2026-12-04 | 0.85 | - | 4.3 | 2320/774 | 0.022 |
| 07_insurance_71-3307 | ✅ | ✅ | ✅ | ✅ | 29 ธ.ค. 2569 → 2026-12-29 | 0.80 | 🟣 | 5.0 | 2371/1063 | 0.027 |
| 08_driver_license_surachai | ✅ | ✅ | ✅ | ❌ | 2 ธันวาคม 2569 → 2026-12-02 | 0.45 | 🟣 | 4.2 | 2464/750 | 0.022 |
| 09_driver_license_boonlert | ✅ | ✅ | ✅ | ✅ | 9 Jul 2027 → 2027-07-09 | 0.90 | - | 2.7 | 2445/361 | 0.015 |
