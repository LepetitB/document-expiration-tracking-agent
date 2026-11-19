# Evaluation — engine `claude`, model `claude-sonnet-5-5`, files `*.png`

Documents: **9** · measured 2026-11-19T22:12:23

| Field | Accuracy |
|---|---|
| doc_type | 78% |
| expiry_date | 100% |
| doc_number | 100% |
| plate | 89% |

- All fields correct: 6/9
- Sent to human review: 3/9
- **False-confident** (wrong but auto-confirmed): 0/9
- Latency: avg **3.9 s**, p95 4.7 s per document
- Tokens per document: ~2391 in / ~376 out
- Cost: **0.299 THB per document** · 2.69 THB this run · ~39 THB/year for 130 documents (1 USD = 35.0 THB)

| File | type | expiry | number | plate/driver | extracted expiry | conf. | review | s | tokens in/out | THB |
|---|---|---|---|---|---|---|---|---|---|---|
| 01_tax_70-1234 | ✅ | ✅ | ✅ | ✅ | 26/11/69 → 2026-11-26 | 0.85 | - | 4.4 | 2464/394 | 0.310 |
| 02_tax_72-4410 | ✅ | ✅ | ✅ | ✅ | 22 กรกฎาคม 2570 → 2027-07-22 | 0.90 | - | 3.4 | 2371/351 | 0.289 |
| 03_prb_71-0099 | ✅ | ✅ | ✅ | ✅ | ๑ ธ.ค. ๒๕๖๙ → 2026-12-01 | 0.92 | - | 3.6 | 2392/355 | 0.292 |
| 04_prb_70-5678 | ✅ | ✅ | ✅ | ✅ | 17/12/2569 → 2026-12-17 | 0.90 | - | 3.9 | 2371/324 | 0.279 |
| 05_insurance_70-1234 | ❌ | ✅ | ✅ | ✅ | 18 กุมภาพันธ์ 2570 → 2027-02-18 | 0.50 | 🟣 | 4.4 | 2320/452 | 0.321 |
| 06_insurance_72-9045_english | ✅ | ✅ | ✅ | ✅ | 4 Dec 2026 → 2026-12-04 | 0.90 | - | 3.4 | 2320/315 | 0.273 |
| 07_insurance_71-3307 | ❌ | ✅ | ✅ | ✅ | 29 ธ.ค. 2569 → 2026-12-29 | 0.50 | 🟣 | 4.7 | 2371/509 | 0.344 |
| 08_driver_license_surachai | ✅ | ✅ | ✅ | ❌ | 2 ธันวาคม 2569 → 2026-12-02 | 0.45 | 🟣 | 3.9 | 2464/347 | 0.294 |
| 09_driver_license_boonlert | ✅ | ✅ | ✅ | ✅ | 9 Jul 2027 → 2027-07-09 | 0.93 | - | 3.6 | 2445/341 | 0.290 |
