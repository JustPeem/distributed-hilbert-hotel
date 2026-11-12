"""คนที่ 2 — ข้อมูลแขก เลขห้อง และดัชนีค้นหา (guest.py, ส่วนแขกใน hotel_system.py)

รัน:  python -m unittest -v tests.test_guests
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hotel.errors import DuplicateGuestError, InvalidInputError  # noqa: E402
from hotel.guest import cantor_room, cantor_unpair  # noqa: E402
from hotel.hotel_system import HotelSystem  # noqa: E402


class TestRoomNumber(unittest.TestCase):
    """หัวข้อ 9.2 ข้อ 2"""

    def test_table_from_spec(self):
        table = {(1, 1): 1, (2, 1): 2, (1, 2): 3, (3, 1): 4, (2, 2): 5}
        for (c, s), room in table.items():
            self.assertEqual(cantor_room(c, s), room)

    def test_unique_and_bijective(self):
        seen = {}
        for c in range(1, 151):
            for s in range(1, 151):
                room = cantor_room(c, s)
                self.assertNotIn(room, seen, f"{(c, s)} ชนกับ {seen.get(room)}")
                seen[room] = (c, s)
                self.assertEqual(cantor_unpair(room), (c, s))
        # ห้อง 1..T(150) ถูกใช้ครบไม่มีช่องว่าง
        for room in range(1, 150 * 151 // 2 + 1):
            self.assertIn(room, seen)

    def test_large_ids_use_integer_math(self):
        c, s = 10 ** 30 + 7, 10 ** 30 + 11
        room = cantor_room(c, s)
        self.assertIsInstance(room, int)
        self.assertEqual(cantor_unpair(room), (c, s))

    def test_room_independent_of_node(self):
        hotel = HotelSystem.create(5, 8, [50, 50])
        for key in hotel.guest_keys():
            self.assertEqual(hotel.find_by_guest(*key).room_no, cantor_room(*key))

    def test_addresses_unique(self):
        hotel = HotelSystem.create(10, 16, [300] * 5)
        addresses = [g.address for g in hotel.list_rooms()]
        self.assertEqual(len(addresses), len(set(addresses)))


class TestGuestsDoNotMove(unittest.TestCase):
    """หัวข้อ 9.2 ข้อ 1"""

    def test_add_guests_old_and_new_channels(self):
        hotel = HotelSystem.create(10, 32, [200] * 4, salt="0")
        before = hotel.assignments()
        hotel.add_guest(2, 201)                  # ช่องทางเดิม
        hotel.add_group(1, 201, 300)             # ช่องทางเดิมเป็นกลุ่ม
        hotel.add_group(9, 1, 150)               # ช่องทางใหม่
        hotel.add_guest(12, 5)                   # ช่องทางใหม่รายบุคคล
        after = hotel.assignments()
        changed = [k for k, v in before.items() if after[k] != v]
        self.assertEqual(changed, [])
        self.assertEqual(hotel.guest_count, 800 + 1 + 300 + 150 + 1)
        self.assertEqual(hotel.check_consistency(), [])

    def test_remove_guest_does_not_move_others(self):
        hotel = HotelSystem.create(5, 8, [100, 100])
        before = hotel.assignments()
        hotel.remove_guest(1, 50)
        del before[(1, 50)]
        self.assertEqual(hotel.assignments(), before)


class TestDuplicates(unittest.TestCase):
    """หัวข้อ 9.2 ข้อ 3"""

    def test_duplicate_single(self):
        hotel = HotelSystem.create(3, 4, [10])
        snapshot = hotel.assignments()
        with self.assertRaises(DuplicateGuestError):
            hotel.add_guest(1, 3)
        self.assertEqual(hotel.assignments(), snapshot)

    def test_group_partially_overlapping_is_rejected_entirely(self):
        hotel = HotelSystem.create(3, 4, [10, 10])
        snapshot = hotel.assignments()
        with self.assertRaises(DuplicateGuestError):
            hotel.add_group(2, 8, 20)            # (2,8)..(2,10) ซ้ำ ส่วนที่เหลือใหม่
        self.assertEqual(hotel.assignments(), snapshot)
        self.assertIsNone(hotel.find_by_guest(2, 11))
        self.assertEqual(hotel.check_consistency(), [])

    def test_group_count_zero_and_negative(self):
        hotel = HotelSystem.create(3, 4, [10])
        snapshot = hotel.assignments()
        self.assertEqual(hotel.add_group(5, 1, 0), [])
        with self.assertRaises(InvalidInputError):
            hotel.add_group(5, 1, -3)
        with self.assertRaises(InvalidInputError):
            hotel.add_group(5, 1, 2.5)
        with self.assertRaises(InvalidInputError):
            hotel.add_guest(0, 1)
        self.assertEqual(hotel.assignments(), snapshot)


if __name__ == "__main__":
    unittest.main(verbosity=2)
