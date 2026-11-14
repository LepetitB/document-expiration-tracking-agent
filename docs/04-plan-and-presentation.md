# 04 — แผนงานและการนำเสนอ (Plan & Presentation)

## 1. แผนงาน 4 สัปดาห์

| สัปดาห์ | เป้าหมาย | Lead | Member AI | Member Agent/Backend | Member Frontend | Member Data/QA |
|--------|---------|------|-----------|---------------------|-----------------|----------------|
| **1 — Foundation** | repo พร้อม, ข้อมูลตัวอย่างพร้อม | สร้าง repo + board, เขียน scope | ทดลอง prompt กับเอกสาร 3 ประเภท | DB models + repository | Flask skeleton 6 หน้า | สร้างเอกสารสังเคราะห์ + ground truth |
| **2 — Core pipeline** | อัปโหลด → ดึงข้อมูล → บันทึก ได้ครบ loop | รีวิว PR, เก็บ requirement เพิ่ม | extractor + schemas + `thai_date` | validator + status + upload API | หน้า Upload + Review | unit tests `thai_date`, validator |
| **3 — Agent & Alerts** | เตือนได้จริง + แชทได้ | เตรียมสคริปต์วิดีโอ | ปรับ prompt จากผล eval | agent tools + notifier + scheduler | Dashboard + Chat | รัน eval รอบแรก, รายงาน error |
| **4 — Polish & Ship** | เดโมลื่น, วิดีโอเสร็จ | README, ตรวจ checklist ส่งงาน | baseline Tesseract เปรียบเทียบ | แก้บั๊ก, seed data สำหรับเดโม | ตกแต่ง UI, screenshot | eval รอบสุดท้าย, ตัดต่อวิดีโอ |

**Milestones:** สิ้นสัปดาห์ 2 = end-to-end ใช้ได้ (แม้ยังไม่สวย) · สิ้นสัปดาห์ 3 = feature freeze · สัปดาห์ 4 = อัดวิดีโอ

---

## 2. โครงวิดีโอนำเสนอ (≤ 20 นาที — เป้า 18 นาที)

| เวลา | หัวข้อ | ผู้พูด | เนื้อหา |
|-----|-------|-------|--------|
| 0:00–0:45 | Intro | Lead | แนะนำทีม + บทบาท |
| 0:45–3:45 | **① Rationale** | Lead | เล่ากรณี A "เคลมไม่ได้เพราะ พ.ร.บ. ขาด 3 วัน", ตัวเลขเอกสาร ~225 ฉบับ / ~165 ครั้งต่อปี, ตารางค่าปรับพร้อมแหล่งอ้างอิง, root causes 6 ข้อ, ผลสัมภาษณ์ (ถ้ามี) |
| 3:45–6:15 | **② Literature Review** | Data/QA | 9 กลุ่มโซลูชันที่มีอยู่ + ข้อดีข้อเสีย, ตารางเกณฑ์ C1–C8, สรุปช่องว่างว่าทำไมไม่มีตัวไหนตอบโจทย์ SME ไทย |
| 6:15–7:30 | **③ Proposed Solution: ภาพรวม** | Lead / Agent | ตาราง Problem → Solution, As-Is vs To-Be, สถาปัตยกรรม 6 ขั้น |
| 7:30–10:00 | Document Intelligence Pipeline | AI | classification + extraction, schema, ปัญหา พ.ศ./ค.ศ., confidence score |
| 10:00–11:45 | Agent & Notification | Agent/Backend | tool use ทำงานยังไง, rule แจ้งเตือน 90/60/30/7, กันส่งซ้ำ |
| 11:45–15:30 | **Live Demo** | Frontend | อัปโหลดเอกสาร (ถ่ายมือถือ) → review ฟิลด์ที่ไม่มั่นใจ → dashboard เปลี่ยนสี → ถาม agent → รับแจ้งเตือนจริงบนมือถือ |
| 15:30–17:30 | **④ Results** | Data/QA | (a) Methodology: กระบวนการ Design→Build→Measure, หลักการออกแบบ, วิธีประเมิน (b) Results: ตาราง accuracy Claude vs baseline, false-confident rate, ปัญหาที่พบและวิธีแก้ (ดู docs/05-results.md) |
| 17:30–18:30 | Limitations & Future | Data/QA | ข้อจำกัด (PDPA, ค่า API), งานต่อยอด, ลิงก์ GitHub |

**เคล็ดลับ:** อัดเดโมแยกไว้ก่อน (screen record) เผื่อ API ล่มวันอัด, ทุกคนต้องปรากฏตัว/พูดในวิดีโอ

---

## 3. Checklist ก่อนส่ง

- [ ] Repo ตั้งเป็น **Public** และเปิดดูได้โดยไม่ต้อง login
- [ ] README มี: ปัญหา, วิธีติดตั้ง, วิธีรัน, screenshot, ลิงก์วิดีโอ YouTube, รายชื่อสมาชิก + บทบาท
- [ ] ไม่มี API key / `.env` / ข้อมูลส่วนบุคคลจริงใน repo (ตรวจด้วย `git log -p | grep -i key`)
- [ ] `requirements.txt` ครบ, คนนอกทีม clone แล้วรันได้ตาม README
- [ ] มีผล evaluation ใน `eval/results_*.md` และเติมตาราง B2 ใน `docs/05-results.md` ครบ
- [ ] วิดีโอ ≤ 20 นาที, อัปโหลด YouTube (Public หรือ Unlisted ตามที่อาจารย์กำหนด)
- [ ] ส่งลิงก์ YouTube + GitHub ใน Moodle
