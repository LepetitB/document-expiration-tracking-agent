# 📄 Document Expiration Tracking Agent

> ช่วยบริษัทขนส่งให้รถทุกคันพร้อมวิ่งถูกกฎหมาย — ไม่ลืมต่อ **ภาษีรถ · พ.ร.บ. · ประกันภัย · ใบขับขี่คนขับ** ถ่ายรูปเอกสาร ให้ AI อ่านวันหมดอายุ แล้วเตือนล่วงหน้าถึงธุรการและคนขับผ่าน LINE

**Domain:** บริษัทรับจ้างขนส่งสินค้า (SME) — บริษัทสมมติ *สยามฟลีท ทรานสปอร์ต* รถบรรทุก 40 คัน
**Pain point:** รถ 40 คัน × เอกสาร 3 อย่าง = ต้องต่ออายุ 120 ครั้งต่อปี แต่ธุรการยังพิมพ์วันหมดอายุลง Excel เองและต้องจำเองว่าต้องเปิดดูเมื่อไร → ภาษี/พ.ร.บ. ขาด = รถวิ่งไม่ได้และถูกปรับ, ประกันขาด = เกิดอุบัติเหตุแล้วเคลมไม่ได้

## ✨ ความสามารถ
- 📤 ถ่ายรูป / สแกน ป้ายภาษี กรมธรรม์ พ.ร.บ. กรมธรรม์ประกันภัย → AI **อ่านทะเบียนรถ เลขที่ และวันหมดอายุให้เอง** (Vision LLM)
- 🗓️ รองรับวันที่ภาษาไทย ปี **พ.ศ.** เลขไทย และกรมธรรม์ภาษาอังกฤษ (แปลงเป็น ค.ศ. ด้วยโค้ด)
- ✅ **Human-in-the-loop** — ค่าที่ AI ไม่มั่นใจจะส่งให้คนตรวจก่อน
- 🚛 **สถานะรายคัน** (รวมใบขับขี่ของคนขับประจำรถ) — ⛔ ห้ามออกวิ่ง / ⚠️ ต้องรีบต่อ / ✅ พร้อมวิ่ง
- 💬 **LINE ถึงคนขับ** เมื่อใบขับขี่ของตัวเองใกล้หมด หรือรถที่ตัวเองขับห้ามออกวิ่ง (เดโมเป็นการจำลอง; ใส่ `LINE_CHANNEL_TOKEN` เพื่อส่งจริง)
- 🔎 **เทียบกับข้อมูลหลัก** — ชื่อคนขับ/ทะเบียนที่ AI อ่านต้องตรงกับในระบบ ไม่ตรงส่งคนตรวจ
- 🔔 แจ้งเตือนล่วงหน้า 90/60/30/7 วัน และวันหมดอายุ (Email / Discord / LINE)
- 💬 **Agent chat** ถามเป็นภาษาไทย เช่น "รถคันไหนห้ามออกวิ่งบ้าง"

## 📚 เอกสารออกแบบ
| เอกสาร | เนื้อหา |
|--------|--------|
| [00 — ทีมและขอบเขต](docs/00-team-and-scope.md) | บทบาทสมาชิก, domain, user stories, success criteria |
| [01 — Rationale](docs/01-rationale.md) | ทำไมต้องทำ: pain point จากหน้างาน, root causes, ค่าปรับและผลเสียพร้อมแหล่งอ้างอิง, สถานการณ์ตัวอย่าง |
| [02 — Literature Review](docs/02-literature-review.md) | โซลูชันที่มีอยู่ 9 กลุ่ม, ข้อดีข้อเสีย, ตารางเปรียบเทียบตามเกณฑ์, เหตุผลที่เลือกแนวทางนี้ |
| [03 — Proposed Solution](docs/03-proposed-solution.md) | Problem → Solution, สถาปัตยกรรม, pipeline, data model, agent tools, UI, evaluation |
| [04 — แผนงานและการนำเสนอ](docs/04-plan-and-presentation.md) | แผน 4 สัปดาห์, โครงวิดีโอ 20 นาทีตาม rubric, checklist ส่งงาน |
| [05 — Results](docs/05-results.md) | Methodology ที่ใช้พัฒนา + ผลลัพธ์ (tests, ความแม่นยำ, ปัญหาที่พบและวิธีแก้) |

## 👥 สมาชิก
| บทบาท | ชื่อ | รหัสนิสิต |
|------|-----|---------|
| Project Lead & Product Owner | [ชื่อ] | [รหัส] |
| AI / Document Intelligence Engineer | [ชื่อ] | [รหัส] |
| Agent & Backend Engineer | [ชื่อ] | [รหัส] |
| Frontend / UX Engineer | [ชื่อ] | [รหัส] |
| Data & QA / Evaluation Lead | [ชื่อ] | [รหัส] |

## 🛠️ Tech Stack
Python · Flask (เว็บแอปบน localhost) · Claude API `claude-opus-5-5` (vision + structured outputs + tool use) · SQLite · pypdf · pytest

## 🚀 วิธีรัน (localhost)
**Windows: ดับเบิลคลิก `start.bat`** ครั้งแรกจะสร้าง `.venv` และติดตั้งไลบรารีให้ จากนั้นเบราว์เซอร์จะเปิด http://localhost:5000 เอง

หรือรันเอง:
```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python run.py
```

- **ไม่มี API key ก็ใช้ได้** แอปจะทำงานใน *โหมดออฟไลน์* โดยอ่านไฟล์ .txt/.pdf ด้วยระบบกฎ และ Agent ตอบคำถามแบบง่ายได้
- **เปิดใช้ AI:** คัดลอก `.env.example` เป็น `.env` แล้วใส่ `ANTHROPIC_API_KEY` จะอ่านรูปถ่าย/สแกนด้วย Claude Vision และคุยกับ Agent ได้เต็มรูปแบบ
- **แจ้งเตือนจริง:** ใส่ `DISCORD_WEBHOOK_URL` หรือค่า LINE / SMTP ใน `.env` ถ้าไม่ใส่ ข้อความจะถูกเขียนลง `data/outbox/`
- เอกสารตัวอย่าง (ข้อมูลสมมติ) อยู่ใน `data/samples/` สร้างใหม่ได้ด้วย `python scripts/make_samples.py`
- ทดสอบ: `.venv\Scripts\python -m pytest`
- วัดความแม่นยำ: `.venv\Scripts\python -m eval.evaluate --engine rules` (หรือ `--engine claude --ext png`)

### หน้าจอในแอป
| หน้า | ทำอะไร |
|------|-------|
| 📊 Dashboard | การ์ดจำนวนรถ (⛔ ห้ามวิ่ง / ⚠️ ต้องรีบต่อ / ✅ พร้อมวิ่ง), **ตารางสถานะรายคัน** (ภาษี / พ.ร.บ. / ประกัน), กราฟ 12 เดือน, ตารางเอกสารทั้งหมด |
| 📤 อัปโหลดเอกสาร | ลากวางหลายไฟล์ แล้ว AI จะจำแนกประเภท ดึงข้อมูล แปลง พ.ศ.→ค.ศ. และให้คะแนนความมั่นใจ |
| ✅ ตรวจทาน | แสดงภาพเอกสารคู่กับฟอร์ม ไฮไลต์ฟิลด์ที่ไม่มั่นใจ แล้วกดยืนยัน (human-in-the-loop) |
| ➕ เพิ่มเอง | กรอกข้อมูลเอกสารด้วยมือ |
| 💬 ถาม Agent | ถามเป็นภาษาไทย Agent จะเรียก tools ค้นฐานข้อมูลจริง |
| 🔔 แจ้งเตือน | ตรวจและส่งแจ้งเตือนรอบ 90/60/30/7/0 วัน (ไม่ส่งซ้ำ), ดูประวัติและ outbox |

### โครงสร้างโค้ด
```
run.py                 # จุดเริ่มรัน (Flask + ตัวตรวจรายวัน)
app/config.py          # ประเภทเอกสาร, ช่วงแจ้งเตือน, ค่าจาก .env
app/extraction/        # thai_date.py (พ.ศ.→ค.ศ.), extractor.py (Claude / ระบบกฎ)
app/core/              # status.py, validator.py (กฎ + confidence), notifier.py
app/agent/             # tools.py (5 tools), agent.py (Claude tool-use loop + โหมดออฟไลน์)
app/db/database.py     # SQLite
app/web/               # server.py + templates/ + static/
eval/evaluate.py       # วัดความแม่นยำรายฟิลด์
tests/                 # pytest 34 tests
```

## 🎥 วิดีโอนำเสนอ
[YouTube link — TBD]

---
*โปรเจคนี้ใช้ AI agent ช่วยในการออกแบบและพัฒนา (อนุญาตตามโจทย์)*
