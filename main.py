"""ส่วนติดต่อผู้ใช้แบบเมนูข้อความ (ไม่มีตรรกะหลักอยู่ในไฟล์นี้)

รัน:   python main.py          เมนูโต้ตอบ
       python main.py --demo   สาธิตอัตโนมัติครบทุกฟังก์ชันและกรณีขอบ
"""

import os
import sys

from hotel import HotelError, HotelSystem
from hotel.benchmark import compare_with_mod_n, measure_memory, measure_timing
from hotel.csv_export import export_guests, export_moves

PREVIEW_ROWS = 20
OUTPUT_DIR = "output"


# ---------------------------------------------------------------- แสดงผล
def fmt_rate(report):
    if report.move_rate is None:
        return "ไม่คำนวณอัตรา เพราะไม่มีแขก (K = 0)"
    return f"{report.move_rate:.4f} ({report.move_rate * 100:.2f}%)"


def show_move_report(report, preview=PREVIEW_ROWS):
    action = "เพิ่ม" if report.operation == "add_node" else "ลบ"
    print(f"  {action}อาคาร {report.node_id} [{report.method}]  "
          f"N ก่อนคำสั่ง = {report.nodes_before}, K = {report.guests_total}")
    print(f"  จำนวนแขกที่ย้าย = {report.moved_count}  อัตราการย้าย = {fmt_rate(report)}")
    print(f"  เวลา: ปรับวงแหวน {report.ring_update_s * 1e3:.3f} ms | "
          f"หาแขกที่ย้าย {report.find_s * 1e3:.3f} ms | "
          f"ปรับข้อมูล/ดัชนี {report.apply_s * 1e3:.3f} ms")
    moves = report.sorted_moves()
    if moves:
        print(f"  {'รหัสแขก':>14} {'อาคารเดิม':>9} {'อาคารใหม่':>9} {'room_no':>10}")
        for m in moves[:preview]:
            print(f"  {str((m.channel_id, m.sequence_id)):>14} {m.old_node:>9} "
                  f"{m.new_node:>9} {m.room_no:>10}")
        if len(moves) > preview:
            print(f"  ... แสดง {preview} จากทั้งหมด {len(moves)} รายการ (ส่งออก CSV เพื่อดูครบ)")


def show_load(system):
    st = system.load_stats()
    print(f"  N = {system.node_count}, V = {system.v}, K = {st.total}")
    for node_id, count in st.counts.items():
        print(f"    อาคาร {node_id:>4}: {count:>7} คน")
    print(f"  สูงสุด {st.maximum}  ต่ำสุด {st.minimum}  เฉลี่ย {st.mean:.2f}  SD {st.std:.2f}")
    print("  CV = " + ("ไม่คำนวณ เพราะไม่มีแขก" if st.cv is None else f"{st.cv:.4f}"))


def show_rooms(system, preview=PREVIEW_ROWS):
    rooms = system.list_rooms()
    print(f"  ห้องที่มีผู้พักทั้งหมด {len(rooms)} ห้อง (เรียงตาม node_id แล้ว room_no)")
    for g in rooms[:preview]:
        print(f"    อาคาร {g.node_id:>4}  ห้อง {g.room_no:>10}  แขก ({g.c}, {g.s})")
    if len(rooms) > preview:
        print(f"    ... แสดง {preview} จากทั้งหมด {len(rooms)} ห้อง")


def show_guest(system, c, s):
    g = system.find_by_guest(c, s)
    if g is None:
        print(f"  ไม่พบแขก ({c}, {s})")
    else:
        print(f"  แขก ({c}, {s}) -> อาคาร {g.node_id} ห้อง {g.room_no} "
              f"(คำนวณจากวงแหวนตอนนี้ได้อาคาร {system.compute_node(c, s)})")


def show_room(system, node_id, room_no):
    g = system.find_by_room(node_id, room_no)
    if g is None:
        print(f"  ไม่พบผู้พักที่อาคาร {node_id} ห้อง {room_no}")
    else:
        print(f"  อาคาร {node_id} ห้อง {room_no} -> แขก ({g.c}, {g.s})")


def attempt(label, fn, *args):
    """เรียกคำสั่ง ถ้าถูกปฏิเสธให้แสดงเหตุผลแล้วทำงานต่อ"""
    try:
        return fn(*args)
    except HotelError as exc:
        print(f"  [ปฏิเสธ] {label}: {exc}")
        return None


# ---------------------------------------------------------------- รับค่า
def ask(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw if raw else ("" if default is None else str(default))


def ask_int(prompt, default=None):
    while True:
        raw = ask(prompt, default)
        try:
            return int(raw)
        except ValueError:
            print("  ! กรุณาพิมพ์จำนวนเต็ม")


def ask_int_list(prompt, default):
    while True:
        raw = ask(prompt, default)
        try:
            return [int(x) for x in raw.replace(" ", "").split(",") if x != ""]
        except ValueError:
            print("  ! พิมพ์จำนวนเต็มคั่นด้วยจุลภาค เช่น 100,100,100")


# ---------------------------------------------------------------- เมนู
MENU = """
========== Distributed Hilbert's Hotel ==========
 1) เริ่มระบบใหม่ (N, V, จำนวนแขกต่อช่องทาง, salt)
 2) เพิ่มแขกรายบุคคล            3) เพิ่มแขกเป็นกลุ่ม
 4) นำแขกออก
 5) เพิ่มอาคาร                  6) ลบอาคาร
 7) ค้นหาด้วยรหัสแขก (c, s)      8) ค้นหาด้วยที่อยู่ห้อง (node_id, room_no)
 9) แสดงรายการห้องที่มีผู้พัก    10) รายงานความสมดุลของโหลด
11) วัดเวลาและหน่วยความจำ       12) เปรียบเทียบกับ hash mod N
13) ส่งออก CSV                  14) ตรวจความสอดคล้องของข้อมูล
 0) ออก"""


def menu_init(state):
    n = ask_int("จำนวนอาคาร N", 10)
    v = ask_int("จำนวน virtual node ต่ออาคาร V", 32)
    counts = ask_int_list("จำนวนแขกของแต่ละช่องทาง (คั่นด้วย ,)", "100,100,100")
    salt = ask("salt (เว้นว่างได้)", "")
    system = attempt("เริ่มระบบ", HotelSystem.create, n, v, counts, salt)
    if system is not None:
        state["system"] = system
        state["last_report"] = None
        print(f"  เริ่มระบบแล้ว: N = {n}, V = {v}, M = {len(system.ring)}, K = {system.guest_count}")


def run_menu():
    state = {"system": HotelSystem.create(10, 32, [100] * 3), "last_report": None}
    print("เริ่มต้นด้วยระบบตัวอย่าง N = 10, V = 32, 3 ช่องทาง ช่องทางละ 100 คน")
    while True:
        print(MENU)
        choice = ask("เลือก").strip()
        system = state["system"]
        if choice == "0":
            print("จบการทำงาน")
            return
        if choice == "1":
            menu_init(state)
        elif choice == "2":
            g = attempt("เพิ่มแขก", system.add_guest, ask_int("c"), ask_int("s"))
            if g:
                print(f"  เพิ่มแล้ว: ({g.c}, {g.s}) -> อาคาร {g.node_id} ห้อง {g.room_no}")
        elif choice == "3":
            added = attempt("เพิ่มแขกเป็นกลุ่ม", system.add_group,
                            ask_int("c"), ask_int("s_start", 1), ask_int("จำนวนแขก"))
            if added is not None:
                print(f"  เพิ่มแล้ว {len(added)} คน (K = {system.guest_count})")
        elif choice == "4":
            g = attempt("นำแขกออก", system.remove_guest, ask_int("c"), ask_int("s"))
            if g:
                print(f"  นำแขก ({g.c}, {g.s}) ออกจากอาคาร {g.node_id} ห้อง {g.room_no} แล้ว")
        elif choice in ("5", "6"):
            print(f"  อาคารปัจจุบัน: {system.node_ids()}")
            node_id = ask_int("รหัสอาคาร")
            fn = system.add_node if choice == "5" else system.remove_node
            report = attempt("เพิ่ม/ลบอาคาร", fn, node_id)
            if report:
                state["last_report"] = report
                show_move_report(report)
        elif choice == "7":
            attempt("ค้นหา", show_guest, system, ask_int("c"), ask_int("s"))
        elif choice == "8":
            attempt("ค้นหา", show_room, system, ask_int("node_id"), ask_int("room_no"))
        elif choice == "9":
            show_rooms(system)
        elif choice == "10":
            show_load(system)
        elif choice == "11":
            menu_benchmark(system)
        elif choice == "12":
            op = ask("add หรือ remove", "add")
            node_id = ask_int("รหัสอาคาร")
            result = attempt("เปรียบเทียบ", compare_with_mod_n, system,
                             "add" if op.startswith("a") else "remove", node_id)
            if result:
                for report in result:
                    show_move_report(report, preview=5)
                print("  (ทำบนสำเนา ระบบจริงไม่เปลี่ยน)")
        elif choice == "13":
            menu_export(state)
        elif choice == "14":
            problems = system.check_consistency()
            print("  ข้อมูลทุกชุดสอดคล้องกัน" if not problems else "\n".join(problems[:20]))
        else:
            print("  ! ไม่มีตัวเลือกนี้")


def menu_benchmark(system):
    n = ask_int("N", system.node_count)
    v = ask_int("V", system.v)
    k = ask_int("K", 10000)
    salt = ask("salt", system.salt or "0")
    if min(n, v) < 1 or k < 0:
        print("  ! ต้องมี N ≥ 1, V ≥ 1, K ≥ 0")
        return
    print(f"  พารามิเตอร์: N = {n}, V = {v}, K = {k}, salt = {salt!r}, 10 ช่องทาง")
    timing = measure_timing(n, v, k, salt)
    memory = measure_memory(n, v, k, salt)
    for key, value in timing.items():
        print(f"    {key:<26} {value:,.3f}")
    for key, value in memory.items():
        print(f"    {key:<26} {value:,.4f}")
    print("  (หน่วยความจำ = ที่ Python ติดตามผ่าน tracemalloc ไม่ใช่ของทั้งโปรเซส)")


def menu_export(state):
    system = state["system"]
    path = ask("ไฟล์รายชื่อแขก", os.path.join(OUTPUT_DIR, "guests.csv"))
    rows = export_guests(system, path)
    print(f"  เขียน {rows} แถว (แขกในระบบ {system.guest_count} คน) -> {path}")
    if state["last_report"] is not None:
        path = ask("ไฟล์รายการย้ายล่าสุด", os.path.join(OUTPUT_DIR, "moves.csv"))
        rows = export_moves(state["last_report"], path)
        print(f"  เขียน {rows} แถว -> {path}")


# ---------------------------------------------------------------- สาธิต
def run_demo():
    def title(text):
        print(f"\n--- {text} ---")

    title("1) เริ่มระบบ N = 3, V = 8, ช่องทาง 1–2 ช่องละ 5 คน")
    system = HotelSystem.create(3, 8, [5, 5])
    print(f"  M = {len(system.ring)} จุด, K = {system.guest_count}")
    show_rooms(system)

    title("2) เพิ่มแขกช่องทางเดิมและช่องทางใหม่ แล้วตรวจว่าแขกเดิมไม่ย้าย")
    before = system.assignments()
    system.add_guest(1, 6)
    system.add_group(3, 1, 4)
    after = system.assignments()
    unchanged = all(after[k] == v for k, v in before.items())
    print(f"  K = {system.guest_count}; แขกเดิม {len(before)} คนอยู่ที่เดิมทั้งหมด: {unchanged}")

    title("3) ค้นหาสองทาง")
    show_guest(system, 2, 3)
    g = system.find_by_guest(2, 3)
    show_room(system, g.node_id, g.room_no)

    title("4) เพิ่มอาคาร 4")
    report = system.add_node(4)
    show_move_report(report)
    print(f"  ผู้ย้ายเข้าอาคาร 4 ทั้งหมด: {all(m.new_node == 4 for m in report.moves)}")
    print(f"  ค้นด้วยที่อยู่ห้องใหม่ของผู้ย้ายยังถูกต้อง: "
          f"{all(system.find_by_room(4, m.room_no).key == (m.channel_id, m.sequence_id) for m in report.moves)}")

    title("5) ลบอาคาร 2")
    remove_report = system.remove_node(2)
    show_move_report(remove_report)
    print(f"  ผู้ย้ายมาจากอาคาร 2 ทั้งหมด: {all(m.old_node == 2 for m in remove_report.moves)}")

    title("6) รายงานโหลด")
    show_load(system)

    title("7) กรณีขอบ (หัวข้อ 4.5) — ทุกกรณีถูกปฏิเสธและข้อมูลเดิมคงอยู่")
    snapshot = system.assignments()
    attempt("เพิ่มอาคารที่มีอยู่แล้ว", system.add_node, 1)
    attempt("ลบอาคารที่ไม่มีอยู่", system.remove_node, 99)
    attempt("เพิ่มแขกซ้ำ", system.add_guest, 1, 1)
    attempt("เพิ่มกลุ่มที่ซ้ำบางรายการ", system.add_group, 1, 5, 3)
    attempt("จำนวนแขกติดลบ", system.add_group, 4, 1, -1)
    attempt("นำแขกที่ไม่มีอยู่ออก", system.remove_guest, 9, 9)
    show_guest(system, 9, 9)
    show_room(system, 1, 999999)
    print(f"  ข้อมูลไม่เปลี่ยน: {system.assignments() == snapshot}")
    single = HotelSystem.create(1, 4, [])
    attempt("ลบอาคารสุดท้าย (แม้ไม่มีแขก)", single.remove_node, 1)
    print("  ระบบที่ยังไม่มีแขก:")
    show_load(single)
    report = single.add_node(2)
    print(f"  เพิ่มอาคารเมื่อ K = 0: ย้าย {report.moved_count} คน, อัตรา: {fmt_rate(report)}")

    title("8) เปรียบเทียบกับ hash mod N (บนสำเนา ชุดแขกเดียวกัน)")
    big = HotelSystem.create(10, 32, [1000] * 10, salt="0")
    for r in compare_with_mod_n(big, "add", 11):
        show_move_report(r, preview=0)

    title("9) ส่งออก CSV")
    rows = export_guests(system, os.path.join(OUTPUT_DIR, "demo_guests.csv"))
    print(f"  demo_guests.csv: {rows} แถว, แขกในระบบ {system.guest_count} คน")
    rows = export_moves(remove_report, os.path.join(OUTPUT_DIR, "demo_moves.csv"))
    print(f"  demo_moves.csv (ลบอาคาร 2): {rows} แถว, รายงานว่าย้าย {remove_report.moved_count} คน")

    title("10) ตรวจความสอดคล้อง")
    print("  ไม่มีปัญหา" if not system.check_consistency() else system.check_consistency())


if __name__ == "__main__":
    try:
        if "--demo" in sys.argv:
            run_demo()
        else:
            run_menu()
    except (EOFError, KeyboardInterrupt):
        print("\nจบการทำงาน")
