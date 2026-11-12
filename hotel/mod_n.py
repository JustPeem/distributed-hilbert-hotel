"""วิธีเปรียบเทียบ: เลือกอาคารด้วย H(guest) mod N 

H(guest) ใช้ตำแหน่ง 64 บิตเดียวกับ Consistent Hashing (SHA-256 + salt เดียวกัน)
"""

import time

from .errors import (DuplicateGuestError, DuplicateNodeError, InvalidInputError,
                     LastNodeError, NodeNotFoundError)
from .guest import Guest, cantor_room
from .hashing import guest_position
from .hotel_system import Move, MoveReport, compute_load_stats
from .validation import require_int


class ModNHotel:
    def __init__(self, node_ids, salt="", guest_position_fn=None):
        ids = list(node_ids)
        if not ids:
            raise InvalidInputError("ต้องมีอาคารอย่างน้อย 1 หลัง (N ≥ 1)")
        for node_id in ids:
            require_int("รหัสอาคาร", node_id, 0)
        if len(set(ids)) != len(ids):
            raise DuplicateNodeError("รายการอาคารเริ่มต้นมีรหัสซ้ำ")
        self._nodes = ids                    
        self._salt = str(salt)
        if guest_position_fn is None:
            salt_text = self._salt
            guest_position_fn = lambda c, s: guest_position(c, s, salt_text)
        self._guest_pos_fn = guest_position_fn
        self._guests = {}                      # (c, s) -> Guest
        self._room_index = {}                  # (node_id, room_no) -> Guest

    @property
    def guest_count(self):
        return len(self._guests)

    @property
    def node_count(self):
        return len(self._nodes)

    def node_ids_in_order(self):
        return list(self._nodes)

    def route(self, position):
        """O(1): ดัชนี = position mod N"""
        return self._nodes[position % len(self._nodes)]

    def add_guests(self, keys):
        keys = list(keys)
        seen = set()
        for c, s in keys:
            require_int("c (ช่องทาง)", c, 1)
            require_int("s (ลำดับ)", s, 1)
            if (c, s) in self._guests or (c, s) in seen:
                raise DuplicateGuestError(f"รหัสแขก ({c}, {s}) ซ้ำ — ปฏิเสธทั้งชุด")
            seen.add((c, s))
        for c, s in keys:
            pos = self._guest_pos_fn(c, s)
            g = Guest(c, s, cantor_room(c, s), pos, self.route(pos))
            self._guests[(c, s)] = g
            self._room_index[g.address] = g

    def find_by_guest(self, c, s):
        return self._guests.get((c, s))

    def assignments(self):
        return {k: g.address for k, g in self._guests.items()}

    def load_stats(self):
        counts = {nid: 0 for nid in self._nodes}
        for g in self._guests.values():
            counts[g.node_id] += 1
        return compute_load_stats(counts)

    def _rescan(self, report, t0, t1):
        moves = []
        for g in self._guests.values():               # ต้องตรวจครบ K คนเสมอ
            new_node = self.route(g.position)
            if new_node != g.node_id:
                moves.append(Move(g.c, g.s, g.node_id, new_node, g.room_no))
        t2 = time.perf_counter()
        for m in moves:
            g = self._guests[(m.channel_id, m.sequence_id)]
            del self._room_index[(m.old_node, m.room_no)]
            g.node_id = m.new_node
            self._room_index[(m.new_node, m.room_no)] = g
        t3 = time.perf_counter()
        report.moves = moves
        report.ring_update_s, report.find_s, report.apply_s = t1 - t0, t2 - t1, t3 - t2
        return report

    def add_node(self, node_id):
        require_int("รหัสอาคาร", node_id, 0)
        if node_id in self._nodes:
            raise DuplicateNodeError(f"มีอาคารรหัส {node_id} อยู่แล้ว")
        report = MoveReport("add_node", node_id, "mod-n", len(self._guests), len(self._nodes))
        t0 = time.perf_counter()
        self._nodes.append(node_id)                     
        t1 = time.perf_counter()
        return self._rescan(report, t0, t1)

    def remove_node(self, node_id):
        require_int("รหัสอาคาร", node_id, 0)
        if node_id not in self._nodes:
            raise NodeNotFoundError(f"ไม่มีอาคารรหัส {node_id}")
        if len(self._nodes) == 1:
            raise LastNodeError("ลบอาคารสุดท้ายไม่ได้ (N ≥ 1)")
        report = MoveReport("remove_node", node_id, "mod-n", len(self._guests), len(self._nodes))
        t0 = time.perf_counter()
        self._nodes.remove(node_id)                   
        t1 = time.perf_counter()
        return self._rescan(report, t0, t1)
