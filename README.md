# โรงแรมอนันต์แบบกระจาย (Distributed Hilbert's Hotel) ด้วย Consistent Hashing

โครงงานรายวิชา Object Oriented Data Structure ภาคการศึกษา 1/2569

## ความต้องการของระบบ

- Python 3 (ตรวจสอบการทำงานในสภาพแวดล้อมนี้ด้วย Python 3.9.6)
- โปรแกรมหลักและชุดทดสอบใช้ไลบรารีมาตรฐานของ Python
- การสร้างกราฟต้องติดตั้ง `matplotlib`:

```bash
python3 -m pip install matplotlib
```

## วิธีเรียกโปรแกรม

```bash
python3 main.py          # เปิดเมนูโต้ตอบ
python3 main.py --demo   # สาธิตการทำงานและกรณีขอบโดยอัตโนมัติ
```

เมนูประกอบด้วยฟังก์ชันหลัก 14 ข้อ ได้แก่ เริ่มระบบ, เพิ่ม/นำแขกออก, เพิ่ม/ลบอาคาร,
ค้นหาด้วยรหัสแขกหรือที่อยู่ห้อง, แสดงรายการห้อง, รายงานโหลด, benchmark,
เปรียบเทียบกับ hash mod N, ส่งออก CSV และตรวจสอบความสอดคล้องของข้อมูล

## วิธีรันทดสอบ

```bash
python3 run_tests.py
python3 -m unittest discover -v
python3 -m unittest -v tests.test_edge_cases
```

`run_tests.py` รันทดสอบทั้งหมดและบันทึกผลไว้ที่ `results/test_results.txt`.

## วิธีรันการทดลองและสร้างกราฟ

```bash
python3 experiments.py          # การทดลอง A–E ด้วยชุดข้อมูลเต็ม
python3 experiments.py --quick  # ชุดข้อมูลเล็กลงสำหรับตรวจการทำงาน
python3 make_plots.py           # สร้างกราฟจากไฟล์ CSV ใน results/
```

การทดลองบันทึก CSV ลงใน `results/` และกราฟ PNG ลงใน `results/figures/`.
การทดลองใช้ salt `"0"`, `"1"` และ `"2"` เพื่อให้เปรียบเทียบผลซ้ำได้
เวลาในการทำงานขึ้นอยู่กับเครื่องที่ใช้

## โครงสร้างไฟล์

```text
main.py                 เมนูโต้ตอบและโหมด --demo
hotel/
  __init__.py           public API ของแพ็กเกจ
  benchmark.py          ฟังก์ชันวัดเวลาและหน่วยความจำ
  csv_export.py         ส่งออกรายชื่อแขกและรายการย้ายเป็น CSV
  hash_ring.py          consistent hash ring และ virtual nodes
  hotel_system.py       จัดการแขก อาคาร และรายงานการย้าย
  mod_n.py              วิธีเปรียบเทียบแบบ hash mod N
  hashing.py            การคำนวณตำแหน่งแฮช
  guest.py              ข้อมูลแขกและหมายเลขห้อง
  errors.py             ข้อยกเว้นของระบบ
  validation.py         ตรวจสอบข้อมูลนำเข้า
tests/
  test_edge_cases.py    กรณีขอบและการส่งออก CSV
  test_guests.py        การเพิ่ม/นำแขกออกและหมายเลขห้อง
  test_nodes.py         การเพิ่ม/ลบอาคารและการย้ายแขก
  test_ring.py          การแฮชและการค้นหาบนวงแหวน
run_tests.py            รันทดสอบทั้งหมดและบันทึกผล
experiments.py          ชุดการทดลอง A–E
make_plots.py           สร้างกราฟจากผลการทดลอง
```

## กติกาการคำนวณโดยย่อ

- ตำแหน่งบนวงแหวนมาจาก 8 ไบต์แรกของ SHA-256 อ่านแบบ big-endian
- รหัสแขกใช้ข้อความ `guest:<c>:<s>` และ virtual node ใช้ `node:<node_id>:<j>`;
  เมื่อกำหนด salt จะต่อท้ายด้วย `|salt:<salt>`
- เลือก virtual node แรกที่มีตำแหน่งไม่น้อยกว่าตำแหน่งแขก
  และวนกลับจุดแรกเมื่อเลยจุดสุดท้าย
- หมายเลขห้องคำนวณจาก Cantor pairing ของ `(c, s)` จึงไม่เปลี่ยนเมื่อแขกย้ายอาคาร
