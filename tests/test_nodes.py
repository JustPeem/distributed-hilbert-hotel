"""คนที่ 3 — เพิ่ม/ลบอาคารและการย้าย (add_node, remove_node ใน hotel_system.py, mod_n.py)


รัน:  python -m unittest -v tests.test_nodes
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hotel.errors import NodeNotFoundError  # noqa: E402
from hotel.guest import cantor_room  # noqa: E402
from hotel.hotel_system import HotelSystem  # noqa: E402
from hotel.mod_n import ModNHotel  # noqa: E402


# ตัวอย่างวงแหวนเล็กในหัวข้อ 9.1 (ตำแหน่งกำหนดไว้ล่วงหน้า ไม่ใช่ SHA-256)
# รหัสอาคาร A, B, C, D แทนด้วย 1, 2, 3, 4
A, B, C, D = 1, 2, 3, 4
SMALL_NODE_POS = {A: 20, B: 50, C: 80, D: 35}
SMALL_GUEST_POS = [10, 20, 25, 35, 50, 70, 90]          # แขก (1, 1) .. (1, 7)
EXPECT_START = [A, A, B, B, B, C, A]
EXPECT_ADD_D = [A, A, D, D, B, C, A]
EXPECT_REMOVE_B = [A, A, C, C, C, C, A]


def small_hotel(reassign="range"):
    guest_pos = {(1, i + 1): p for i, p in enumerate(SMALL_GUEST_POS)}
    hotel = HotelSystem([A, B, C], 1, reassign=reassign,
                        guest_position_fn=lambda c, s: guest_pos[(c, s)],
                        node_position_fn=lambda node_id, j: SMALL_NODE_POS[node_id])
    hotel.add_group(1, 1, len(SMALL_GUEST_POS))
    return hotel


def nodes_of(hotel):
    return [hotel.find_by_guest(1, s).node_id for s in range(1, len(SMALL_GUEST_POS) + 1)]


class TestSmallRingExample(unittest.TestCase):
    """หัวข้อ 9.1"""

    def test_initial_assignment(self):
        self.assertEqual(nodes_of(small_hotel()), EXPECT_START)

    def test_add_node_d(self):
        for method in ("range", "scan"):
            hotel = small_hotel(method)
            rooms = {k: g.room_no for k, g in ((k, hotel.find_by_guest(*k)) for k in hotel.guest_keys())}
            report = hotel.add_node(D)
            self.assertEqual(nodes_of(hotel), EXPECT_ADD_D)
            self.assertEqual(report.moved_count, 2)
            self.assertTrue(all(m.new_node == D for m in report.moves))
            self.assertTrue(all(rooms[(m.channel_id, m.sequence_id)] == m.room_no for m in report.moves))
            self.assertEqual(hotel.check_consistency(), [])

    def test_remove_node_b(self):
        for method in ("range", "scan"):
            hotel = small_hotel(method)
            report = hotel.remove_node(B)
            self.assertEqual(nodes_of(hotel), EXPECT_REMOVE_B)
            self.assertEqual(report.moved_count, 3)
            self.assertTrue(all(m.old_node == B for m in report.moves))
            self.assertEqual(hotel.check_consistency(), [])

    def test_wraparound_guest_at_90(self):
        hotel = small_hotel()
        self.assertEqual(hotel.find_by_guest(1, 7).node_id, A)


class TestRingChangesWithGuests(unittest.TestCase):
    """หัวข้อ 9.2 ข้อ 4 ส่วนที่มีแขกและมีการเพิ่ม/ลบอาคาร"""

    def test_collision_on_add_node(self):
        positions = {(1, 0): 20, (3, 0): 50, (0, 0): 50, (7, 0): 50}
        guest_pos = {(1, 1): 30, (1, 2): 50, (1, 3): 60}
        hotel = HotelSystem([1, 3], 1, node_position_fn=lambda n, j: positions[(n, j)],
                            guest_position_fn=lambda c, s: guest_pos[(c, s)])
        hotel.add_group(1, 1, 3)
        # อาคาร 7 ชนที่ 50 แต่เรียงหลังอาคาร 3 -> ไม่ได้รับแขกเลย
        self.assertEqual(hotel.add_node(7).moved_count, 0)
        # อาคาร 0 ชนที่ 50 และเรียงก่อนอาคาร 3 -> รับแขกที่ 30 และ 50
        report = hotel.add_node(0)
        self.assertEqual(sorted((m.channel_id, m.sequence_id) for m in report.moves), [(1, 1), (1, 2)])
        self.assertEqual(hotel.check_consistency(), [])

    def test_guests_with_same_position(self):
        hotel = HotelSystem([1, 2], 4, guest_position_fn=lambda c, s: 12345)
        hotel.add_group(1, 1, 5)
        nodes = {hotel.find_by_guest(1, s).node_id for s in range(1, 6)}
        rooms = {hotel.find_by_guest(1, s).room_no for s in range(1, 6)}
        self.assertEqual(len(nodes), 1)
        self.assertEqual(len(rooms), 5)
        hotel.add_node(3)
        hotel.remove_node(1)
        self.assertEqual(hotel.check_consistency(), [])

    def test_readd_uses_current_ring(self):
        hotel = HotelSystem.create(4, 8, [200])
        hotel.remove_guest(1, 7)
        hotel.add_node(5)
        hotel.remove_node(2)
        g = hotel.add_guest(1, 7)
        self.assertEqual(g.node_id, hotel.compute_node(1, 7))
        self.assertEqual(g.room_no, cantor_room(1, 7))


class TestNodeChanges(unittest.TestCase):
    """หัวข้อ 9.2 ข้อ 5 (V > 1)"""

    def check_add(self, hotel, node_id):
        before = hotel.assignments()
        k = hotel.guest_count
        report = hotel.add_node(node_id)
        after = hotel.assignments()
        moved = {key for key in before if before[key][0] != after[key][0]}
        self.assertEqual(len(moved), report.moved_count)
        self.assertEqual({(m.channel_id, m.sequence_id) for m in report.moves}, moved)
        for m in report.moves:
            self.assertEqual(m.new_node, node_id)
            self.assertEqual(before[(m.channel_id, m.sequence_id)], (m.old_node, m.room_no))
            self.assertEqual(after[(m.channel_id, m.sequence_id)], (node_id, m.room_no))
        self.assertEqual(hotel.guest_count, k)
        self.assertEqual(hotel.check_consistency(), [])
        return report

    def check_remove(self, hotel, node_id):
        before = hotel.assignments()
        k = hotel.guest_count
        report = hotel.remove_node(node_id)
        after = hotel.assignments()
        for key, (old, room) in before.items():
            if old != node_id:
                self.assertEqual(after[key], (old, room))        # อาคารอื่นไม่ขยับ
            else:
                self.assertNotEqual(after[key][0], node_id)
                self.assertEqual(after[key][1], room)
        self.assertEqual(report.moved_count, sum(1 for o, _ in before.values() if o == node_id))
        self.assertTrue(all(m.old_node == node_id for m in report.moves))
        self.assertEqual(hotel.guest_count, k)
        self.assertEqual(hotel.check_consistency(), [])
        return report

    def test_add_and_remove_many_times(self):
        hotel = HotelSystem.create(5, 16, [400] * 5, salt="2")
        self.check_add(hotel, 6)
        self.check_add(hotel, 100)
        self.check_remove(hotel, 3)
        self.check_remove(hotel, 6)
        self.check_add(hotel, 3)
        self.check_remove(hotel, 1)

    def test_range_equals_scan(self):
        for salt in ("0", "1", "2"):
            a = HotelSystem.create(10, 32, [500] * 10, salt=salt, reassign="range")
            b = HotelSystem.create(10, 32, [500] * 10, salt=salt, reassign="scan")
            ra, rb = a.add_node(11), b.add_node(11)
            self.assertEqual(set(ra.moves), set(rb.moves))
            ra, rb = a.remove_node(4), b.remove_node(4)
            self.assertEqual(set(ra.moves), set(rb.moves))
            self.assertEqual(a.assignments(), b.assignments())

    def test_room_index_after_move(self):
        """ตัวอย่างข้อมูลหลายส่วนที่ต้องสอดคล้องกัน: ค้นด้วยที่อยู่ใหม่ได้ ที่อยู่เก่าไม่พบ"""
        hotel = HotelSystem.create(4, 8, [300])
        report = hotel.add_node(9)
        self.assertGreater(report.moved_count, 0)
        for m in report.moves:
            self.assertEqual(hotel.find_by_room(9, m.room_no).key, (m.channel_id, m.sequence_id))
            self.assertIsNone(hotel.find_by_room(m.old_node, m.room_no))

    def test_report_rate(self):
        hotel = HotelSystem.create(4, 8, [250] * 4)
        report = hotel.add_node(5)
        self.assertAlmostEqual(report.move_rate, report.moved_count / 1000)


class TestModN(unittest.TestCase):
    """หัวข้อ 7.1"""

    def test_mod_n_moves_most_guests_and_uses_real_ids(self):
        keys = [(c, s) for c in range(1, 11) for s in range(1, 1001)]
        mod = ModNHotel(range(1, 11), "0")
        mod.add_guests(keys)
        before = mod.assignments()
        report = mod.add_node(11)
        after = mod.assignments()
        self.assertEqual(report.moved_count, sum(1 for k in keys if before[k][0] != after[k][0]))
        self.assertGreater(report.move_rate, 0.8)
        report = mod.remove_node(1)
        self.assertEqual(mod.node_ids_in_order(), list(range(2, 12)))
        with self.assertRaises(NodeNotFoundError):
            mod.remove_node(1)

    def test_same_hash_as_consistent_hashing(self):
        hotel = HotelSystem.create(3, 4, [10], salt="1")
        mod = ModNHotel([1, 2, 3], "1")
        mod.add_guests(hotel.guest_keys())
        for key in hotel.guest_keys():
            self.assertEqual(mod.find_by_guest(*key).position, hotel.find_by_guest(*key).position)


if __name__ == "__main__":
    unittest.main(verbosity=2)
