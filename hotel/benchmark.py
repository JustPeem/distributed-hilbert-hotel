"""ฟังก์ชันวัดเวลาและหน่วยความจำ"""

import gc
import random
import time
import tracemalloc

from .hash_ring import HashRing
from .hotel_system import HotelSystem
from .mod_n import ModNHotel

MIB = 1024 * 1024
LOOKUP_BATCH = 1000


def channel_counts(k, channels=10):
    """แบ่ง K คนให้ 10 ช่องทางใกล้เคียงกัน (ต่างกันไม่เกิน 1)"""
    base, extra = divmod(k, channels)
    return [base + (1 if i < extra else 0) for i in range(channels)]


def keys_for_counts(counts):
    return [(c, s) for c, n in enumerate(counts, start=1) for s in range(1, n + 1)]


def measure_timing(n, v, k, salt, channels=10, batch=LOOKUP_BATCH):
    """การทดลอง A (รอบจับเวลา): คืน dict ของเวลาแต่ละขั้นตอน"""
    counts = channel_counts(k, channels)
    rng = random.Random(f"timing|{salt}|{n}|{v}|{k}")
    gc.collect()

    t0 = time.perf_counter()
    system = HotelSystem(range(1, n + 1), v, salt)          # สร้างวงแหวน
    t1 = time.perf_counter()
    for c, count in enumerate(counts, start=1):              # จัดแขกเริ่มต้น
        system.add_group(c, 1, count)
    t2 = time.perf_counter()

    keys = keys_for_counts(counts)
    sample = [keys[rng.randrange(len(keys))] for _ in range(batch)] if keys else []
    addresses = [system.find_by_guest(c, s).address for c, s in sample]

    t3 = time.perf_counter()
    for c, s in sample:
        system.find_by_guest(c, s)
    t4 = time.perf_counter()
    for node_id, room_no in addresses:
        system.find_by_room(node_id, room_no)
    t5 = time.perf_counter()
    for c, s in sample:
        system.compute_node(c, s)
    t6 = time.perf_counter()
    rooms = system.list_rooms()
    t7 = time.perf_counter()

    new_channel = channels + 1
    for s in range(1, batch + 1):
        system.add_guest(new_channel, s)
    t8 = time.perf_counter()
    for s in range(1, batch + 1):
        system.remove_guest(new_channel, s)
    t9 = time.perf_counter()

    per = max(len(sample), 1)
    return {
        "build_ring_ms": (t1 - t0) * 1e3,
        "assign_guests_ms": (t2 - t1) * 1e3,
        "lookup_guest_us": (t4 - t3) / per * 1e6,
        "lookup_room_us": (t5 - t4) / per * 1e6,
        "compute_node_us": (t6 - t5) / per * 1e6,
        "sort_rooms_ms": (t7 - t6) * 1e3,
        "add_guest_single_us": (t8 - t7) / batch * 1e6,
        "remove_guest_single_us": (t9 - t8) / batch * 1e6,
        "listed_rows": len(rooms),
    }


def measure_memory(n, v, k, salt, channels=10):
    counts = channel_counts(k, channels)
    gc.collect()
    tracemalloc.start()
    try:
        base, _ = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        ring = HashRing(v, salt)
        ring.build(range(1, n + 1))
        ring_current, ring_peak = tracemalloc.get_traced_memory()
        del ring
        gc.collect()

        base2, _ = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        system = HotelSystem(range(1, n + 1), v, salt)
        for c, count in enumerate(counts, start=1):
            system.add_group(c, 1, count)
        sys_current, sys_peak = tracemalloc.get_traced_memory()

        tracemalloc.reset_peak()
        rooms = system.list_rooms()
        list_current, list_peak = tracemalloc.get_traced_memory()
        del rooms
    finally:
        tracemalloc.stop()
    return {
        "ring_current_mib": (ring_current - base) / MIB,
        "ring_peak_mib": (ring_peak - base) / MIB,
        "system_current_mib": (sys_current - base2) / MIB,
        "system_peak_mib": (sys_peak - base2) / MIB,
        "list_rooms_extra_peak_mib": (list_peak - sys_current) / MIB,
    }


def node_change(method, op, n, v, k, salt, changed_node, channels=10):
    """ลอง B/C: สร้างระบบใหม่แล้วเพิ่มหรือลบอาคารหนึ่งครั้ง"""
    keys = keys_for_counts(channel_counts(k, channels))
    if method == "mod-n":
        hotel = ModNHotel(range(1, n + 1), salt)
    else:
        hotel = HotelSystem(range(1, n + 1), v, salt, reassign=method.split("-")[1])
    hotel.add_guests(keys)
    gc.collect()
    if op == "add":
        return hotel.add_node(changed_node)
    return hotel.remove_node(changed_node)


def compare_with_mod_n(system, op, node_id):
    order = system.ring.node_ids_in_order()
    keys = system.guest_keys()
    ch = HotelSystem(order, system.v, system.salt, reassign=system.reassign)
    ch.add_guests(keys)
    mod = ModNHotel(order, system.salt)
    mod.add_guests(keys)
    if op == "add":
        return ch.add_node(node_id), mod.add_node(node_id)
    return ch.remove_node(node_id), mod.remove_node(node_id)
