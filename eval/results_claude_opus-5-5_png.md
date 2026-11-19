# Evaluation — engine `claude`, model `claude-opus-5-5`, files `*.png`

Documents: **9** · measured 2026-11-19T22:11:47

| Field | Accuracy |
|---|---|
| doc_type | 100% |
| expiry_date | 100% |
| doc_number | 100% |
| plate | 100% |

- All fields correct: 9/9
- Sent to human review: 0/9
- **False-confident** (wrong but auto-confirmed): 0/9
- Latency: avg **6.3 s**, p95 14.2 s per document
- Tokens per document: ~2391 in / ~456 out
- Cost: **0.654 THB per document** · 5.88 THB this run · ~85 THB/year for 130 documents (1 USD = 35.0 THB)

| File | type | expiry | number | plate/driver | extracted expiry | conf. | review | s | tokens in/out | THB |
|---|---|---|---|---|---|---|---|---|---|---|
| 01_tax_70-1234 | ✅ | ✅ | ✅ | ✅ | 26/11/69 → 2026-11-26 | 0.85 | - | 14.2 | 2464/477 | 0.679 |
| 02_tax_72-4410 | ✅ | ✅ | ✅ | ✅ | 22 กรกฎาคม 2570 → 2027-07-22 | 0.90 | - | 4.4 | 2371/367 | 0.589 |
| 03_prb_71-0099 | ✅ | ✅ | ✅ | ✅ | ๑ ธ.ค. ๒๕๖๙ → 2026-12-01 | 0.93 | - | 5.3 | 2392/480 | 0.671 |
| 04_prb_70-5678 | ✅ | ✅ | ✅ | ✅ | 17/12/2569 → 2026-12-17 | 0.95 | - | 5.0 | 2371/412 | 0.620 |
| 05_insurance_70-1234 | ✅ | ✅ | ✅ | ✅ | 18 กุมภาพันธ์ 2570 → 2027-02-18 | 0.96 | - | 5.0 | 2320/395 | 0.601 |
| 06_insurance_72-9045_english | ✅ | ✅ | ✅ | ✅ | 4 Dec 2026 → 2026-12-04 | 0.93 | - | 5.2 | 2320/417 | 0.617 |
| 07_insurance_71-3307 | ✅ | ✅ | ✅ | ✅ | 29 ธ.ค. 2569 → 2026-12-29 | 0.90 | - | 7.6 | 2371/718 | 0.835 |
| 08_driver_license_surachai | ✅ | ✅ | ✅ | ✅ | 2 ธันวาคม 2569 → 2026-12-02 | 0.85 | - | 5.0 | 2464/448 | 0.659 |
| 09_driver_license_boonlert | ✅ | ✅ | ✅ | ✅ | 9 Jul 2027 → 2027-07-09 | 0.93 | - | 4.9 | 2445/389 | 0.615 |
