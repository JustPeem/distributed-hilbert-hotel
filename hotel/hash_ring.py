
"""Consistent Hashing ring with Virtual Nodes (หัวข้อ 4.3, 4.4)

Data structures ที่ใช้ในวงแหวน

- _points : list ของ (position, node_id, j) เรียงจากน้อยไปมาก
  ถ้ามี position ซ้ำ จะเรียงต่อด้วย node_id และ j

- _node_points : dict node_id -> list ของจุดในอาคารนั้น
  เอาไว้เช็คว่าอาคารมีอยู่แล้วหรือยัง และใช้ดูจุดของแต่ละอาคาร
  อีกอย่างคือ dict จะจำลำดับที่เพิ่มข้อมูลเข้ามาได้
  เลยเอาไปใช้กับวิธี mod N ได้ด้วย
"""

from bisect import bisect_left

from .errors import (DuplicateNodeError, EmptyRingError, LastNodeError,
                     NodeNotFoundError)
from .hashing import RING_MAX, node_position
from .validation import require_int


class HashRing:
    def __init__(self, v, salt="", position_fn=None):
        """สร้าง HashRing โดยกำหนดจำนวน virtual nodes ต่ออาคาร

        v = จำนวน virtual nodes ของแต่ละอาคาร (ไม่เปลี่ยนระหว่างใช้งาน)
        position_fn ใช้แทน SHA-256 ตอน testing ได้
        เช่น การทดลองวงแหวนขนาด 100 ในหัวข้อ 9.1
        """
        self._v = require_int("V", v, 1)
        self._salt = str(salt)

        if position_fn is None:
            salt_text = self._salt
            position_fn = lambda node_id, j: node_position(node_id, j, salt_text)

        self._position_fn = position_fn
        self._points = []
        self._node_points = {}

    # Basic information

    @property
    def v(self):
        return self._v

    @property
    def salt(self):
        return self._salt

    def __len__(self):
        """จำนวนจุดทั้งหมดบนวงแหวน (M)"""
        return len(self._points)

    @property
    def node_count(self):
        """จำนวนอาคารทั้งหมด (N)"""
        return len(self._node_points)

    def has_node(self, node_id):
        return node_id in self._node_points

    def node_ids(self):
        """คืนรหัสอาคารโดยเรียงจากน้อยไปมาก"""
        return sorted(self._node_points)

    def node_ids_in_order(self):
        """คืนรหัสอาคารตามลำดับที่เพิ่มเข้ามา ใช้ในวิธี mod N"""
        return list(self._node_points)

    def points(self):
        """คืนจุดทั้งหมดบนวงแหวนเป็น tuple"""
        return tuple(self._points)

    def points_of(self, node_id):
        """ดูจุดทั้งหมดของอาคารที่ระบุ"""
        if node_id not in self._node_points:
            raise NodeNotFoundError(f"ไม่มีอาคารรหัส {node_id}")

        return tuple(self._node_points[node_id])

    # Create / Add / Remove nodes

    def _make_points(self, node_id):
        """สร้าง virtual nodes ทั้ง V จุดของอาคาร แล้วเรียงตาม position"""
        return sorted(
            (self._position_fn(node_id, j), node_id, j)
            for j in range(self._v)
        )

    def build(self, node_ids):
        """สร้าง HashRing ตอนเริ่มต้น โดยสร้างจุดของทุกอาคารแล้วเรียงทั้งหมด"""
        if self._node_points:
            raise RuntimeError("build() ใช้ได้เฉพาะตอนที่วงแหวนยังว่าง")

        ids = list(node_ids)

        for node_id in ids:
            require_int("รหัสอาคาร", node_id, 0)

        if len(set(ids)) != len(ids):
            raise DuplicateNodeError("มีรหัสอาคารซ้ำในรายการเริ่มต้น")

        all_points = []

        for node_id in ids:
            pts = self._make_points(node_id)
            self._node_points[node_id] = pts
            all_points.extend(pts)

        all_points.sort()
        self._points = all_points

    def add_node(self, node_id):
        """เพิ่มอาคารใหม่เข้าไปในวงแหวน

        สร้างแค่ V จุดของอาคารใหม่ ส่วนจุดเดิมไม่ต้องสร้างใหม่
        จากนั้นเอามารวมกับ list เดิมและ sort อีกครั้ง
        """
        require_int("รหัสอาคาร", node_id, 0)

        if node_id in self._node_points:
            raise DuplicateNodeError(f"มีอาคารรหัส {node_id} อยู่แล้ว ไม่เพิ่มซ้ำ")

        new_points = self._make_points(node_id)

        merged = self._points + new_points
        merged.sort()

        self._points = merged
        self._node_points[node_id] = new_points

        return list(new_points)

    def remove_node(self, node_id):
        """ลบอาคารออกจากวงแหวน รวมถึง virtual nodes ทั้งหมดของอาคารนั้น"""
        if node_id not in self._node_points:
            raise NodeNotFoundError(f"ไม่มีอาคารรหัส {node_id} จึงไม่ได้ลบอะไร")

        if len(self._node_points) == 1:
            raise LastNodeError(
                "ลบอาคารสุดท้ายไม่ได้ ระบบต้องมีอาคารอย่างน้อย 1 หลัง (N ≥ 1)"
            )

        # เอาจุดที่เป็นของอาคารนี้ออกจากวงแหวน
        self._points = [p for p in self._points if p[1] != node_id]

        return self._node_points.pop(node_id)

    # Search

    def locate_index(self, position):
        """หาตำแหน่ง index ของจุดแรกที่มี position >= ค่าที่รับเข้ามา

        ถ้าหาไม่เจอจะวนกลับไปใช้จุดแรกของวงแหวน
        ใช้ binary search จึงมีความซับซ้อน O(log M)

        ใช้ (position,) ใน bisect_left เพราะเป็น tuple ที่มีสมาชิกตัวเดียว
        ทำให้ได้จุดแรกเมื่อมีหลายจุดที่ position เท่ากัน
        """
        if not self._points:
            raise EmptyRingError("วงแหวนว่าง ไม่มีอาคารให้เลือก")

        i = bisect_left(self._points, (position,))

        if i == len(self._points):
            return 0

        return i

    def locate(self, position):
        """หา node_id ของอาคารที่รับผิดชอบ position นี้"""
        return self._points[self.locate_index(position)][1]

    def owned_arcs(self, node_id):
        """หา range บนวงแหวนที่เป็นของอาคารที่ระบุ

        คืนค่าเป็น list ของ (lo, hi)
        หมายถึงตำแหน่งที่ lo < x <= hi
        ถ้า lo = -1 แปลว่าเริ่มนับตั้งแต่ตำแหน่ง 0

        แต่ละจุดจะรับผิดชอบช่วงตั้งแต่จุดก่อนหน้ามาจนถึงตัวเอง
        ถ้าจุดก่อนหน้ามี position เท่ากัน แปลว่าจุดนี้ไม่ได้รับช่วงใดเลย

        สำหรับจุดแรกจะมีช่วงที่วนกลับมาจากท้ายวงแหวนด้วย
        """
        if node_id not in self._node_points:
            raise NodeNotFoundError(f"ไม่มีอาคารรหัส {node_id}")

        pts = self._points
        arcs = []

        for p in self._node_points[node_id]:
            i = bisect_left(pts, p)
            pos = p[0]

            if i > 0:
                prev_pos = pts[i - 1][0]

                if prev_pos == pos:
                    continue

                arcs.append((prev_pos, pos))

            else:
                arcs.append((-1, pos))

                last_pos = pts[-1][0]
                if last_pos < RING_MAX:
                    arcs.append((last_pos, RING_MAX))

        return arcs
