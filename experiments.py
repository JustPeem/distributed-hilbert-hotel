"""การทดลอง A, B, C (หัวข้อ 7) และการทดลองเสริม D, E

รัน:  python experiments.py            (ชุดเต็ม)
      python experiments.py --quick    (ขนาดเล็ก ใช้ตรวจว่าสคริปต์ทำงาน)
ผลลัพธ์อยู่ในโฟลเดอร์ results/ แล้วสร้างกราฟด้วย python make_plots.py

ทุกการทดลองทำ 3 รอบ โดยใช้ salt "0", "1", "2"
ภายในรอบเดียวกัน Consistent Hashing กับ hash mod N ใช้รหัสแขก รหัสอาคาร และ salt เดียวกัน
"""

import os
import platform
import statistics
import sys
from datetime import datetime

from hotel.benchmark import (channel_counts, measure_memory, measure_timing,
                             node_change)
from hotel.csv_export import write_rows

SALTS = ["0", "1", "2"]
CHANNELS = 10
NODE_OP_REPEATS = 5          # เวลาเพิ่ม/ลบอาคาร ทำซ้ำ 5 ครั้งต่อรอบแล้วใช้มัธยฐาน
RESULTS = "results"


def summarize(rows, group_keys, metrics):
    """มัธยฐาน ต่ำสุด สูงสุด ของแต่ละ metric ข้าม 3 รอบ (salt)"""
    groups = {}
    for row in rows:
        groups.setdefault(tuple(row[k] for k in group_keys), []).append(row)
    out = []
    for key, items in groups.items():
        rec = dict(zip(group_keys, key))
        rec["rounds"] = len(items)
        for m in metrics:
            values = [r[m] for r in items if r[m] is not None]
            if values:
                rec[f"{m}_median"] = statistics.median(values)
                rec[f"{m}_min"] = min(values)
                rec[f"{m}_max"] = max(values)
        out.append(rec)
    return out


def save(name, rows):
    if not rows:
        return
    header = list(rows[0].keys())
    for r in rows:
        for k in r:
            if k not in header:
                header.append(k)
    path = os.path.join(RESULTS, name)
    write_rows(path, header, ([r.get(k, "") for k in header] for r in rows))
    print(f"  -> {path} ({len(rows)} แถว)")


def median_time(method, op, n, v, k, salt, node):
    reports = [node_change(method, op, n, v, k, salt, node) for _ in range(NODE_OP_REPEATS)]
    first = reports[0]
    assert all(set(r.moves) == set(first.moves) for r in reports)
    pick = lambda attr: statistics.median(getattr(r, attr) for r in reports) * 1e3
    return first, {
        "total_ms": statistics.median(r.total_s for r in reports) * 1e3,
        "ring_update_ms": pick("ring_update_s"),
        "find_ms": pick("find_s"),
        "apply_ms": pick("apply_s"),
    }


def experiment_a(ks, n=10, v=32):
    print(f"[A] ขนาดข้อมูล K = {ks}, N = {n}, V = {v}")
    raw, mem = [], []
    for salt in SALTS:
        for k in ks:
            t = measure_timing(n, v, k, salt, CHANNELS)
            raw.append({"experiment": "A", "salt": salt, "N": n, "V": v, "K": k, **t})
            m = measure_memory(n, v, k, salt, CHANNELS)
            mem.append({"experiment": "A", "salt": salt, "N": n, "V": v, "K": k, **m})
            print(f"    salt={salt} K={k}: assign {t['assign_guests_ms']:.1f} ms, "
                  f"peak {m['system_peak_mib']:.2f} MiB")
    save("exp_a_timing_raw.csv", raw)
    save("exp_a_memory_raw.csv", mem)
    tmetrics = [k for k in raw[0] if k.endswith(("_ms", "_us"))]
    mmetrics = [k for k in mem[0] if k.endswith("_mib")]
    save("exp_a_timing_summary.csv", summarize(raw, ["N", "V", "K"], tmetrics))
    save("exp_a_memory_summary.csv", summarize(mem, ["N", "V", "K"], mmetrics))


def experiment_b(ns, k=10000, v=32):
    """เพิ่ม 1 อาคาร (รหัส N+1) และลบ 1 อาคาร (รหัส 1) แต่ละกรณีเริ่มจากสถานะเดิมใหม่"""
    print(f"[B] จำนวนอาคาร N = {ns}, K = {k}, V = {v}")
    raw = []
    for salt in SALTS:
        for n in ns:
            for op, node in (("add", n + 1), ("remove", 1)):
                expected = k / (n + 1) if op == "add" else k / n
                results = {}
                for method in ("ch-range", "ch-scan", "mod-n"):
                    report, times = median_time(method, op, n, v, k, salt, node)
                    results[method] = report
                    raw.append({"experiment": "B", "salt": salt, "N": n, "V": v, "K": k,
                                "operation": op, "changed_node": node, "method": method,
                                "moved": report.moved_count, "move_rate": report.move_rate,
                                "expected_moved_ch": round(expected, 2),
                                "expected_rate_ch": expected / k, **times})
                # ตรวจกติกา: สองแบบของ CH ได้ผลเหมือนกัน และผู้ย้ายเป็นไปตามกติกา
                assert set(results["ch-range"].moves) == set(results["ch-scan"].moves)
                if op == "add":
                    assert all(m.new_node == node for m in results["ch-range"].moves)
                else:
                    assert all(m.old_node == node for m in results["ch-range"].moves)
                print(f"    salt={salt} N={n} {op}: CH ย้าย {results['ch-range'].moved_count} "
                      f"(คาด {expected:.0f}), mod N ย้าย {results['mod-n'].moved_count}")
    save("exp_b_raw.csv", raw)
    save("exp_b_summary.csv", summarize(raw, ["N", "V", "K", "operation", "method"],
                                        ["moved", "move_rate", "total_ms", "ring_update_ms",
                                         "find_ms", "apply_ms"]))


def experiment_c(vs, n=10, k=10000):
    from hotel.hotel_system import HotelSystem
    print(f"[C] จำนวนจุดเสมือน V = {vs}, N = {n}, K = {k}")
    raw, loads = [], []
    for salt in SALTS:
        for v in vs:
            system = HotelSystem.create(n, v, channel_counts(k, CHANNELS), salt)
            st = system.load_stats()
            for node_id, count in st.counts.items():
                loads.append({"salt": salt, "N": n, "V": v, "K": k, "node_id": node_id,
                              "guests": count})
            mem = measure_memory(n, v, k, salt, CHANNELS)
            add_report, add_t = median_time("ch-range", "add", n, v, k, salt, n + 1)
            rm_report, rm_t = median_time("ch-range", "remove", n, v, k, salt, 1)
            raw.append({"experiment": "C", "salt": salt, "N": n, "V": v, "K": k,
                        "M": n * v, "max": st.maximum, "min": st.minimum, "mean": st.mean,
                        "std": st.std, "cv": st.cv,
                        "ring_current_mib": mem["ring_current_mib"],
                        "ring_peak_mib": mem["ring_peak_mib"],
                        "system_current_mib": mem["system_current_mib"],
                        "system_peak_mib": mem["system_peak_mib"],
                        "add_moved": add_report.moved_count, "add_rate": add_report.move_rate,
                        "add_ms": add_t["total_ms"],
                        "remove_moved": rm_report.moved_count, "remove_rate": rm_report.move_rate,
                        "remove_ms": rm_t["total_ms"]})
            print(f"    salt={salt} V={v}: CV {st.cv:.3f}, max {st.maximum}, min {st.minimum}, "
                  f"ring {mem['ring_current_mib'] * 1024:.1f} KiB")
    save("exp_c_raw.csv", raw)
    save("exp_c_loads.csv", loads)
    metrics = ["max", "min", "std", "cv", "ring_current_mib", "ring_peak_mib",
               "system_current_mib", "add_moved", "add_rate", "add_ms",
               "remove_moved", "remove_rate", "remove_ms"]
    save("exp_c_summary.csv", summarize(raw, ["N", "V", "K"], metrics))


def experiment_d(ks, n=10, v=32):
    """เสริม: เวลาหาแขกที่ต้องย้ายแบบ ก (ตรวจทุกคน) เทียบแบบ ข (เฉพาะช่วง) เมื่อ K โตขึ้น"""
    print(f"[D] แบบ ก vs แบบ ข, K = {ks}, N = {n}, V = {v}")
    raw = []
    for salt in SALTS:
        for k in ks:
            for op, node in (("add", n + 1), ("remove", 1)):
                for method in ("ch-range", "ch-scan"):
                    report, times = median_time(method, op, n, v, k, salt, node)
                    raw.append({"experiment": "D", "salt": salt, "N": n, "V": v, "K": k,
                                "operation": op, "method": method,
                                "moved": report.moved_count, **times})
            print(f"    salt={salt} K={k} เสร็จ")
    save("exp_d_raw.csv", raw)
    save("exp_d_summary.csv", summarize(raw, ["N", "V", "K", "operation", "method"],
                                        ["moved", "total_ms", "find_ms", "apply_ms"]))


def experiment_e(ns, k=10000, v=32, batch=1000):
    import random
    import time
    from hotel.hashing import guest_position
    from hotel.hotel_system import HotelSystem
    from hotel.mod_n import ModNHotel
    print(f"[E] การเลือกอาคารและโหลด CH vs mod N, N = {ns}, K = {k}, V = {v}")
    raw = []
    for salt in SALTS:
        for n in ns:
            counts = channel_counts(k, CHANNELS)
            keys = [(c, s) for c, cnt in enumerate(counts, 1) for s in range(1, cnt + 1)]
            ch = HotelSystem(range(1, n + 1), v, salt)
            ch.add_guests(keys)
            mod = ModNHotel(range(1, n + 1), salt)
            mod.add_guests(keys)
            rnd = random.Random(f"E|{salt}|{n}")
            sample = [keys[rnd.randrange(len(keys))] for _ in range(batch)]
            positions = [guest_position(c, s, salt) for c, s in sample]
            ring = ch.ring
            t0 = time.perf_counter()
            for c, s in sample:
                ch.compute_node(c, s)
            t1 = time.perf_counter()
            for p in positions:
                ring.locate(p)
            t2 = time.perf_counter()
            for c, s in sample:
                mod.route(guest_position(c, s, salt))
            t3 = time.perf_counter()
            for p in positions:
                mod.route(p)
            t4 = time.perf_counter()
            cs, ms = ch.load_stats(), mod.load_stats()
            raw.append({"experiment": "E", "salt": salt, "N": n, "V": v, "K": k,
                        "ch_hash_and_locate_us": (t1 - t0) / batch * 1e6,
                        "ch_locate_only_us": (t2 - t1) / batch * 1e6,
                        "mod_hash_and_route_us": (t3 - t2) / batch * 1e6,
                        "mod_route_only_us": (t4 - t3) / batch * 1e6,
                        "ch_cv": cs.cv, "mod_cv": ms.cv, "ch_max": cs.maximum, "mod_max": ms.maximum})
    save("exp_e_raw.csv", raw)
    save("exp_e_summary.csv", summarize(raw, ["N", "V", "K"],
                                        ["ch_hash_and_locate_us", "ch_locate_only_us",
                                         "mod_hash_and_route_us", "mod_route_only_us",
                                         "ch_cv", "mod_cv", "ch_max", "mod_max"]))


def environment(quick):
    rows = [
        {"key": "run_at", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"key": "python", "value": platform.python_version()},
        {"key": "implementation", "value": platform.python_implementation()},
        {"key": "platform", "value": platform.platform()},
        {"key": "machine", "value": platform.machine()},
        {"key": "cpu_count", "value": os.cpu_count()},
        {"key": "salts", "value": " ".join(SALTS)},
        {"key": "hash", "value": "SHA-256(UTF-8 text)[:8] big-endian, text = guest:c:s|salt:<salt>, node:id:j|salt:<salt>"},
        {"key": "channels", "value": CHANNELS},
        {"key": "lookup_batch", "value": 1000},
        {"key": "node_op_repeats_per_round", "value": NODE_OP_REPEATS},
        {"key": "add_node_id", "value": "N+1"},
        {"key": "remove_node_id", "value": "1"},
        {"key": "quick_mode", "value": quick},
    ]
    save("environment.csv", rows)


def sample_files():
    """ข้อมูลแขกตัวอย่างและรายการย้ายตัวอย่าง (N = 10, V = 32, K = 1,000, salt = "0")"""
    from hotel.csv_export import export_guests, export_moves
    from hotel.hotel_system import HotelSystem
    system = HotelSystem.create(10, 32, channel_counts(1000, CHANNELS), "0")
    n = export_guests(system, os.path.join(RESULTS, "sample_guests.csv"))
    add = system.add_node(11)
    export_moves(add, os.path.join(RESULTS, "sample_moves_add_node11.csv"))
    export_guests(system, os.path.join(RESULTS, "sample_guests_after_add_node11.csv"))
    rm = system.remove_node(1)
    export_moves(rm, os.path.join(RESULTS, "sample_moves_remove_node1.csv"))
    print(f"  ตัวอย่าง: แขก {n} แถว, เพิ่มอาคาร 11 ย้าย {add.moved_count}, "
          f"ลบอาคาร 1 ย้าย {rm.moved_count}")


def main():
    quick = "--quick" in sys.argv
    os.makedirs(RESULTS, exist_ok=True)
    environment(quick)
    sample_files()
    if quick:
        experiment_a([1000, 5000])
        experiment_b([5, 10], k=2000)
        experiment_c([1, 8, 32], k=2000)
        experiment_d([1000, 5000])
        experiment_e([5, 10], k=2000)
    else:
        experiment_a([1000, 10000, 100000])
        experiment_b([5, 10, 20])
        experiment_c([1, 8, 32, 128, 512])       # 128, 512 เป็นค่าเสริมนอกโจทย์
        experiment_d([1000, 10000, 100000])
        experiment_e([5, 10, 20])
    print("เสร็จ ใช้ python make_plots.py เพื่อสร้างกราฟ")


if __name__ == "__main__":
    main()
