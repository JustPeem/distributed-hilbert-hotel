from bisect import bisect_left

from .errors import (DuplicateNodeError, EmptyRingError, LastNodeError,
                     NodeNotFoundError)
from .hashing import RING_MAX, node_position
from .validation import require_int


class HashRing:
    def __init__(self, v, salt="", position_fn=None):
        self._v = require_int("V", v, 1) #จำนวน virtual node
        self._salt = str(salt)

        if position_fn is None:
            salt_text = self._salt
            position_fn = lambda node_id, j: node_position(node_id, j, salt_text)

        self._position_fn = position_fn
        self._points = []
        self._node_points = {}

    #getter /setterr

    @property
    def v(self):
        return self._v

    @property
    def salt(self):
        return self._salt

    def __len__(self): #node ทั้งหมด
        return len(self._points)

    @property
    def node_count(self): #อาคาร
        return len(self._node_points)

    def has_node(self, node_id): #เชค node
        return node_id in self._node_points

    def node_ids(self): # node ไอดีน้อยไปมา
        return sorted(self._node_points)

    def node_ids_in_order(self): #list อาคาร
        return list(self._node_points)

    def points(self): #หาทุก node
        return tuple(self._points)

    def points_of(self, node_id): #ดูจุดทั้งหมดตามอาคาร
        if node_id not in self._node_points:
            raise NodeNotFoundError(f"ไม่มีอาคารรหัส {node_id}")

        return tuple(self._node_points[node_id])

    # Create/Add/Remove nodes

    def _make_points(self, node_id):
        return sorted(
            (self._position_fn(node_id, j), node_id, j)
            for j in range(self._v)
        )

    def build(self, node_ids): #สร้าง hashring ตอนเริ่ม
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

    def add_node(self, node_id): #เพิ่มอาคาร
        require_int("รหัสอาคาร", node_id, 0)

        if node_id in self._node_points:
            raise DuplicateNodeError(f"มีอาคารรหัส {node_id} อยู่แล้ว ไม่เพิ่มซ้ำ")

        new_points = self._make_points(node_id)
        merged = self._points + new_points
        merged.sort()
        self._points = merged
        self._node_points[node_id] = new_points

        return list(new_points)

    def remove_node(self, node_id): #ลบอาคาร
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

    def locate_index(self, position): #หาจุดตา่ม index
        if not self._points:
            raise EmptyRingError("วงแหวนว่าง ไม่มีอาคารให้เลือก")

        i = bisect_left(self._points, (position,))

        if i == len(self._points):
            return 0

        return i

    def locate(self, position): #หา id อาคาร
        return self._points[self.locate_index(position)][1]

    def owned_arcs(self, node_id): #หา range ของ อาคาร
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
