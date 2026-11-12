"""คนที่ 1 — วงแหวนและการเลือกอาคาร (hashing.py, hash_ring.py)

รัน:  python -m unittest -v tests.test_ring
"""

import hashlib
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hotel.hash_ring import HashRing  # noqa: E402
from hotel.hashing import RING_MAX, guest_position, ring_position  # noqa: E402


class TestHashing(unittest.TestCase):
    """หัวข้อ 4.3 ข้อ 1–2"""

    def test_stable_across_processes(self):
        """ค่าแฮชต้องเหมือนเดิมแม้เปิดโปรแกรมใหม่ด้วย PYTHONHASHSEED ต่างกัน"""
        code = ("from hotel.hashing import guest_position, node_position; "
                "print(guest_position(3, 15), node_position(7, 2, '1'))")
        outputs = set()
        for seed in ("1", "2", "random"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                                 capture_output=True, text=True, check=True).stdout
            outputs.add(out)
        self.assertEqual(len(outputs), 1)

    def test_known_value_and_range(self):
        expected = int.from_bytes(hashlib.sha256(b"guest:1:1").digest()[:8], "big")
        self.assertEqual(guest_position(1, 1), expected)
        self.assertEqual(ring_position("x"), ring_position("x"))
        for text in ("a", "guest:1:1", "node:1:0"):
            self.assertTrue(0 <= ring_position(text) <= RING_MAX)

    def test_salt_changes_positions(self):
        self.assertNotEqual(guest_position(1, 1, "0"), guest_position(1, 1, "1"))
        self.assertEqual(guest_position(1, 1, ""), guest_position(1, 1))


class TestRingLookup(unittest.TestCase):
    """หัวข้อ 9.2 ข้อ 4 (ระดับวงแหวน ไม่มีแขก)"""

    def ring(self, positions, v=1):
        r = HashRing(v, position_fn=lambda node_id, j: positions[(node_id, j)])
        r.build(sorted({nid for nid, _ in positions}))
        return r

    def test_exact_between_after_last(self):
        r = self.ring({(1, 0): 20, (2, 0): 50, (3, 0): 80})
        self.assertEqual(r.locate(20), 1)       # ตรงจุดพอดี
        self.assertEqual(r.locate(21), 2)       # ระหว่างจุด
        self.assertEqual(r.locate(0), 1)        # ก่อนจุดแรก
        self.assertEqual(r.locate(81), 1)       # หลังจุดสุดท้าย วนกลับ
        self.assertEqual(r.locate(RING_MAX), 1)

    def test_virtual_node_collision_tiebreak(self):
        # อาคาร 2 j=0 กับอาคาร 1 j=1 ชนที่ 50 -> เรียงด้วย (ตำแหน่ง, node_id, j) อาคาร 1 ชนะ
        r = self.ring({(1, 0): 10, (1, 1): 50, (2, 0): 50, (2, 1): 90}, v=2)
        self.assertEqual(len(r), 4)             # เก็บไว้ทุกจุด
        self.assertEqual(r.locate(50), 1)
        self.assertEqual(r.locate(30), 1)
        self.assertEqual(r.locate(60), 2)
        # ชนกันภายในอาคารเดียวกัน: เก็บไว้ทั้งสองจุด
        r2 = self.ring({(5, 0): 40, (5, 1): 40}, v=2)
        self.assertEqual(len(r2), 2)
        self.assertEqual(r2.locate(99), 5)

    def test_single_point_owns_everything(self):
        r = HashRing(1, position_fn=lambda n, j: 1000)
        r.build([4])
        self.assertEqual(r.owned_arcs(4), [(-1, 1000), (1000, RING_MAX)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
