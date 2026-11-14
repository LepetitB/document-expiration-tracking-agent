# 03 — Proposed Solution: การออกแบบโซลูชัน

## 0. โซลูชันนี้แก้ปัญหาอย่างไร (Problem → Solution)

ทุกส่วนของระบบออกแบบมาเพื่อปิด root cause ใน [01 — Rationale](01-rationale.md) และช่องว่างของโซลูชันเดิมใน [02 — Literature Review](02-literature-review.md)

| Root cause (จาก Rationale) | ส่วนของโซลูชันที่แก้ | อยู่ในโค้ด | วัดผลอย่างไร |
|---------------------------|--------------------|-----------|------------|
| 1. ข้อมูลติดอยู่ในภาพ/กระดาษ | **Vision LLM** จำแนกประเภทและดึงฟิลด์เป็น JSON ตาม schema | `app/extraction/extractor.py` | ความแม่นยำรายฟิลด์ (`eval/evaluate.py`) |
| 2. พิมพ์ผิด พ.ศ. ↔ ค.ศ. | ให้ LLM **คัดลอกวันที่ดิบ** แล้วแปลงด้วยโค้ด + กฎ "ปีไกลเกินจริง = น่าจะอ่านปีผิด" | `thai_date.py`, `validator.py` | unit tests 10+ รูปแบบวันที่ไทย |
| 3. หลายวันที่ในเอกสารเดียว | prompt ระบุชัดว่าต้องการวันไหน + กฎ "วันหมดอายุ > วันออก" | `extractor.py`, `validator.py` | accuracy ของ `expiry_date` |
| (จุดอ่อนของ LLM) มั่นใจแต่ผิด | **confidence score + human-in-the-loop**: ต่ำกว่า 85% หรือผิดกฎ ให้ส่งคนตรวจ | `validator.py`, หน้า "ตรวจทาน" | **false-confident rate** (ผิดแต่ผ่านอัตโนมัติ) ต้องเป็น 0 |
| 4. ไม่มีการเตือนเชิงรุก | ตัวตรวจรายวัน + เตือน 90/60/30/7/0 วัน ไม่ส่งซ้ำ ส่ง Email/LINE/Discord | `notifier.py`, `run.py` | จำลองย้อนหลัง: 0 missed alerts |
| 5. ความรู้อยู่กับคนคนเดียว | ฐานข้อมูลกลาง + Dashboard ที่ใครก็เปิดดูได้ + ผูกเอกสารกับเจ้าของ (คน/รถ/บริษัท) | `database.py`, Dashboard | — |
| 6. ตอบคำถามง่าย ๆ ไม่ได้ | **Agent** ถามภาษาไทย เรียก tools ค้น DB จริง | `app/agent/` | ตอบถูกจากชุดคำถามทดสอบ |
| (ต่ออายุแล้วยังเตือน) | อัปโหลดฉบับใหม่ ระบบจะ mark ฉบับเก่าว่า "ต่ออายุแล้ว" อัตโนมัติ | `database.py` | test `renewal_supersedes` |

**ทำไมเป็นแบบนี้ (ย่อจาก Literature Review):**
- โซลูชันในตลาดที่ "เตือนเก่ง" (Fleet management, CLM) ไม่อ่านเอกสารไทยให้
- ส่วนโซลูชันที่ "อ่านเก่ง" (OCR, Document AI) ไม่มีระบบติดตามและต้องเทรนต่อประเภท
- เราจึงรวม **Vision LLM (อ่าน) + กฎ (กันผิด) + คน (ตรวจเมื่อไม่มั่นใจ) + Tracker/Agent (เตือนและตอบ)** ไว้ในระบบเดียวที่ SME ใช้ได้

## 1. ภาพรวม (To-Be)

**Document Expiration Tracking Agent** = ระบบที่ *อ่าน → เข้าใจ → จำ → เตือน → ตอบคำถาม* เกี่ยวกับเอกสารที่มีวันหมดอายุ

```
 ┌──────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────┐   ┌──────────────┐
 │ 1. Ingest    │──▶│ 2. Extract   │──▶│ 3. Validate & │──▶│ 4. Store     │──▶│ 5. Monitor & │
 │ อัปโหลด/อีเมล │   │ OCR + LLM    │   │ Human Review  │   │ Registry DB  │   │ Notify       │
 └──────────────┘   └──────────────┘   └───────────────┘   └──────┬───────┘   └──────────────┘
                                                                 │
                                                         ┌───────▼────────┐
                                                         │ 6. Agent Chat  │  "เดือนหน้าต้องต่ออะไรบ้าง?"
                                                         │ (Tool use)     │
                                                         └────────────────┘
```

| ขั้น | ทำอะไร | ส่วน Document Intelligence |
|-----|-------|--------------------------|
| 1. Ingest | อัปโหลด PDF/JPG/PNG (หลายไฟล์พร้อมกัน), (ต่อยอด) ดึงไฟล์แนบจากอีเมล | Pre-processing: แปลง PDF→ภาพ, หมุน/ปรับความชัด |
| 2. Extract | จำแนกประเภทเอกสาร + ดึงฟิลด์เป็น JSON | **Classification + Key Information Extraction** ด้วย Vision LLM |
| 3. Validate | ตรวจกฎ (วันหมดอายุ > วันออก, รูปแบบทะเบียนรถ/เลขบัตร), แปลง พ.ศ.→ค.ศ., ให้คะแนนความมั่นใจ | **Post-processing + Confidence scoring** |
| 4. Store | บันทึกเอกสาร + ผูกกับ "เจ้าของ" (คน/รถ/บริษัท) | Entity linking (จับคู่ชื่อ/ทะเบียนกับข้อมูลที่มีอยู่) |
| 5. Notify | Scheduler รันทุกวัน เช็ค 90/60/30/7/0 วัน → แจ้งเตือน | — |
| 6. Agent | ตอบคำถามภาษาไทย, สรุปรายการต่ออายุ, ร่างอีเมลเตือนพนักงาน | **LLM Agent with tools** |

---

## 2. สถาปัตยกรรมและเทคโนโลยี

| Layer | เทคโนโลยี | เหตุผล |
|-------|----------|-------|
| UI | **Flask + HTML/CSS** | เบา รันบน localhost ได้ทุกเครื่อง (Streamlit ถูก Windows Smart App Control บล็อกไลบรารีบางตัว) |
| Backend / Logic | **Python 3.11+** | ภาษาเดียวทั้งระบบ |
| OCR / Vision | **Claude (vision)** อ่านภาพตรง + fallback **Tesseract (`tha+eng`)** | Vision LLM อ่านเอกสารไทยที่ถ่ายเอียง/แสงไม่ดีได้ดีกว่า OCR ดั้งเดิม |
| Extraction | **Claude API** + structured output (JSON schema) | ได้ข้อมูลตรง schema, ลด parse error |
| Agent | Claude **tool use** | ให้ LLM เรียกฟังก์ชันค้นฐานข้อมูลจริง แทนการเดา |
| Database | **SQLite** + SQLAlchemy | ไม่ต้องติดตั้ง server, ย้ายไป PostgreSQL ได้ภายหลัง |
| Scheduler | **APScheduler** (หรือปุ่ม "Run check now" สำหรับเดโม) | เตือนอัตโนมัติรายวัน |
| Notification | **Email (SMTP)** + **LINE Messaging API** / Discord webhook | ช่องทางที่ SME ไทยใช้จริง |
| Testing / Eval | pytest + สคริปต์ประเมินความแม่นยำ | วัดผลเป็นตัวเลขในวิดีโอ |

> **โมเดล:** ค่าเริ่มต้น `claude-opus-5-5` เปลี่ยนได้ด้วย `CLAUDE_MODEL` ใน `.env` (เช่น `claude-sonnet-5-5` หรือ `claude-haiku-5-5` เพื่อลดค่าใช้จ่าย)
> **ห้าม commit API key** — ใช้ `.env` + `.env.example` และใส่ `.env` ใน `.gitignore`

### โครงสร้าง Repository
```
document-expiration-tracking-agent/
├── README.md
├── .env.example                # ANTHROPIC_API_KEY=, LINE_TOKEN=, SMTP_...
├── requirements.txt
├── app/
│   ├── web/                    # Flask server + templates
│   ├── ui/                     # pages: dashboard, upload, review, chat, settings
│   ├── extraction/
│   │   ├── preprocess.py       # pdf→image, resize, rotate
│   │   ├── classifier.py       # ประเภทเอกสาร
│   │   ├── extractor.py        # LLM → JSON
│   │   ├── schemas.py          # Pydantic schema ต่อประเภทเอกสาร
│   │   └── thai_date.py        # parse วันที่ไทย, พ.ศ.→ค.ศ.
│   ├── core/
│   │   ├── validator.py        # rule checks + confidence
│   │   ├── status.py           # คำนวณ VALID / EXPIRING / EXPIRED
│   │   └── notifier.py         # email / LINE
│   ├── agent/
│   │   ├── tools.py            # ฟังก์ชันที่ agent เรียกได้
│   │   └── agent.py            # tool-use loop
│   └── db/
│       ├── models.py
│       └── repository.py
├── data/
│   ├── samples/                # เอกสารตัวอย่าง (สังเคราะห์/ปิดข้อมูลส่วนตัว)
│   └── ground_truth.json
├── eval/
│   └── evaluate.py             # วัด accuracy ต่อฟิลด์
├── tests/
└── docs/
```

---

## 3. Data Model

```
Owner (เจ้าของเอกสาร)
  id, type [EMPLOYEE | VEHICLE | COMPANY | CUSTOMER], name, identifier (เลขพนักงาน/ทะเบียนรถ),
  contact_email, line_user_id, responsible_person

Document
  id, owner_id → Owner, doc_type, doc_number, holder_name,
  issue_date, expiry_date (ค.ศ., ISO-8601), issuing_authority,
  file_path, raw_extraction (JSON), confidence (0–1),
  review_status [PENDING_REVIEW | CONFIRMED], status [VALID | EXPIRING | EXPIRED | RENEWED],
  replaced_by → Document (เมื่อต่ออายุแล้ว), created_at, updated_at

Notification
  id, document_id, threshold_days (90/60/30/7/0), channel, sent_at, delivered (bool)
  -- unique(document_id, threshold_days) กันส่งซ้ำ
```

**กฎสถานะ**
- `EXPIRED` : expiry_date < วันนี้
- `EXPIRING`: เหลือ ≤ 30 วัน (ปรับได้ต่อประเภทเอกสาร เช่น Work Permit ใช้ 60 วัน เพราะต่ออายุนาน)
- `VALID`   : อื่น ๆ
- `RENEWED` : เมื่ออัปโหลดฉบับใหม่ของ owner+doc_type เดียวกัน → ฉบับเก่าเลิกเตือน

---

## 4. Extraction Pipeline (หัวใจของ Document Intelligence)

```
ไฟล์ ─▶ preprocess ─▶ [Vision LLM] classify + extract ─▶ JSON ─▶ thai_date normalize
     ─▶ validator (rules) ─▶ confidence ─▶ ≥ 0.85 & ผ่านกฎ ? auto-confirm : ส่งเข้าหน้า Review
```

### ตัวอย่าง Output Schema
```json
{
  "doc_type": "VEHICLE_TAX",
  "doc_number": "1234567",
  "holder_name": "บริษัท สยามฟลีท ทรานสปอร์ต จำกัด",
  "vehicle_plate": "70-1234 ชลบุรี",
  "issue_date": "2026-03-01",
  "expiry_date": "2027-02-28",
  "expiry_date_raw": "28 ก.พ. 2570",
  "field_confidence": { "expiry_date": 0.97, "doc_number": 0.88 },
  "notes": "ปีในเอกสารเป็น พ.ศ."
}
```

### ประเด็นทางเทคนิคที่ต้องจัดการ (ใช้เล่าในวิดีโอได้ดี)
1. **พ.ศ. vs ค.ศ.** — ให้ LLM คืน `expiry_date_raw` ด้วย แล้วแปลงด้วยโค้ดเอง (ไม่เชื่อ LLM คำนวณวันที่); ถ้าปี > 2400 ถือเป็น พ.ศ. → ลบ 543
2. **เดือนย่อภาษาไทย** — ม.ค., ก.พ., มี.ค. … และรูปแบบ `28/02/70`
3. **หลายวันที่ในเอกสารเดียว** (วันออก, วันเกิด, วันหมดอายุ) — prompt ระบุชัดว่าต้องการวันไหน + กฎ expiry > issue
4. **ภาพเบลอ/เอียง** — preprocess + ถ้า confidence ต่ำส่งให้คนตรวจ
5. **ข้อมูลส่วนบุคคล (PDPA)** — ใช้ข้อมูลสังเคราะห์ใน repo สาธารณะ, ปิดเลขบัตรประชาชนบางส่วนเมื่อแสดงผล

### Confidence Score
`confidence = min(field_confidence ของฟิลด์สำคัญ) × (1 ถ้าผ่านกฎทั้งหมด, 0.5 ถ้าไม่ผ่าน)`
→ ทำให้อธิบายได้ว่า "ทำไมเอกสารนี้ต้องให้คนตรวจ"

---

## 5. Agent Design

Agent ใช้ Claude แบบ **tool use** — LLM ไม่ตอบจากความจำ แต่เรียก tool เพื่อดึงข้อมูลจริงจาก DB

| Tool | Input | ใช้ตอนไหน |
|------|-------|----------|
| `search_documents` | owner, doc_type, status | "เอกสารของนายสมชายมีอะไรบ้าง" |
| `list_expiring` | within_days | "30 วันข้างหน้ามีอะไรหมดบ้าง" |
| `get_owner_summary` | owner identifier | "รถ 70-1234 สถานะเป็นยังไง" |
| `get_stats` | — | "ตอนนี้มีเอกสารหมดอายุกี่ฉบับ" |
| `draft_reminder` | document_id, tone | "ร่างข้อความเตือนคนขับที่ใบขับขี่ใกล้หมด" |
| `send_notification` | document_id, channel | ส่งจริง — **ต้องให้ผู้ใช้กดยืนยันใน UI ก่อนเสมอ** |

**ตัวอย่างบทสนทนา**
> 👤 เดือนธันวาคมนี้ต้องต่ออะไรบ้าง
> 🤖 *(เรียก `list_expiring(within_days=47)`)* มี 6 รายการ: พ.ร.บ. 3 คัน (70-1234, 70-5678, 71-0099), ใบขับขี่ ท.2 ของนายสมชาย, Work Permit 2 คน — แนะนำเริ่มจาก Work Permit เพราะใช้เวลาดำเนินการนานที่สุด ต้องการให้ร่างข้อความแจ้งเตือนไหมครับ?

---

## 6. หน้าจอ (UI)

1. **Dashboard** — การ์ดสรุป (ทั้งหมด / ใกล้หมด / หมดแล้ว / รอตรวจ), timeline 90 วัน, ตารางกรองตามประเภท/เจ้าของ, สีเขียว-เหลือง-แดง
2. **Upload** — ลากวางหลายไฟล์ → แสดงผลการดึงข้อมูลทันที
3. **Review** — ภาพเอกสารซ้าย / ฟอร์มข้อมูลขวา, ไฮไลต์ฟิลด์ที่ confidence ต่ำ, ปุ่มยืนยัน
4. **Agent Chat** — ถามตอบภาษาไทย
5. **Settings** — ช่วงวันแจ้งเตือนต่อประเภทเอกสาร, ช่องทางแจ้งเตือน, ปุ่ม "Run expiry check now"

---

## 7. การประเมินผล (Evaluation)

- **ชุดข้อมูล:** เอกสารสังเคราะห์ 40–60 ฉบับ (7 ประเภท) — สร้างจาก template + ใส่ข้อมูลปลอม, พิมพ์แล้วถ่ายรูปด้วยมือถือบางส่วนเพื่อให้สมจริง (มุมเอียง/แสง)
- **Metrics:**
  - Classification accuracy (ประเภทเอกสาร)
  - Field-level exact match: `expiry_date`, `doc_number`, `holder_name/plate`
  - % เอกสารที่ถูกส่งให้คนตรวจ vs % ที่ผิดแต่ไม่ถูกส่ง (**false-confident rate** — ตัวนี้สำคัญที่สุด)
  - เวลาเฉลี่ยต่อเอกสาร: manual vs ระบบ
- **Baseline เปรียบเทียบ:** Tesseract + regex vs Vision LLM → แสดงตารางในวิดีโอ

---

## 8. ขอบเขต (Scope)

| MVP (ต้องมี) | Stretch (ถ้ามีเวลา) |
|-------------|-------------------|
| Upload + extraction 7 ประเภท | ดึงไฟล์แนบจาก Gmail อัตโนมัติ |
| พ.ศ.→ค.ศ. + validation + review | LINE bot ให้คนขับส่งรูปเอกสารเองได้ |
| Dashboard + สถานะสี | Export ปฏิทิน (.ics) |
| แจ้งเตือนอีเมล/Discord หรือ LINE | ประเมินค่าใช้จ่ายต่ออายุ/งบประมาณรายเดือน |
| Agent chat 4–5 tools | Deploy ขึ้น cloud (เช่น Render) |
| Evaluation script + ผลลัพธ์ | |

## 9. ความเสี่ยงและการรับมือ

| ความเสี่ยง | การรับมือ |
|-----------|----------|
| LLM อ่านวันที่ผิดแต่มั่นใจ | แปลงวันที่ด้วยโค้ด, กฎ validation, human review |
| ข้อมูลส่วนบุคคลหลุดใน repo สาธารณะ | ใช้ข้อมูลสังเคราะห์เท่านั้น, `.gitignore` โฟลเดอร์ uploads |
| ค่า API | ใช้ Haiku สำหรับงานง่าย, cache ผลลัพธ์ต่อไฟล์ (hash) |
| LINE API ตั้งค่ายาก | Email/Discord webhook เป็นทางเลือกหลักสำหรับเดโม |
| Agent ส่งข้อความเองโดยไม่ตั้งใจ | `send_notification` ต้องกดยืนยันใน UI |
