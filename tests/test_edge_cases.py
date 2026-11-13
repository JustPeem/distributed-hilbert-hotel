"""Edge cases and listing/CSV export tests for the hotel system."""

import csv
import os
import tempfile
import unittest

from hotel import (DuplicateNodeError, GuestNotFoundError, HotelSystem,
                   InvalidInputError, LastNodeError, NodeNotFoundError)
from hotel.csv_export import export_guests, export_moves


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.hotel = HotelSystem.create(3, 4, [20, 20])
        self.snapshot = self.hotel.assignments()

    def assertUnchanged(self):
        self.assertEqual(self.hotel.assignments(), self.snapshot)
        self.assertEqual(self.hotel.check_consistency(), [])

    def test_add_existing_node(self):
        with self.assertRaises(DuplicateNodeError):
            self.hotel.add_node(2)
        self.assertEqual(len(self.hotel.ring), 3 * 4)
        self.assertUnchanged()

    def test_remove_missing_node(self):
        with self.assertRaises(NodeNotFoundError):
            self.hotel.remove_node(42)
        self.assertUnchanged()

    def test_remove_last_node_even_without_guests(self):
        single = HotelSystem.create(1, 4, [])
        with self.assertRaises(LastNodeError):
            single.remove_node(1)
        self.assertEqual(single.node_ids(), [1])
        self.assertEqual(single.compute_node(1, 1), 1)

        self.hotel.remove_node(1)
        self.hotel.remove_node(2)
        with self.assertRaises(LastNodeError):
            self.hotel.remove_node(3)

    def test_empty_initial_nodes(self):
        with self.assertRaises(InvalidInputError):
            HotelSystem([], 4)
        with self.assertRaises(InvalidInputError):
            HotelSystem.create(0, 4, [1])

    def test_remove_missing_guest(self):
        with self.assertRaises(GuestNotFoundError):
            self.hotel.remove_guest(9, 9)
        self.assertEqual(self.hotel.guest_count, 40)
        self.assertUnchanged()

    def test_search_not_found(self):
        self.assertIsNone(self.hotel.find_by_guest(9, 9))
        self.assertIsNone(self.hotel.find_by_room(1, 10 ** 9))
        self.assertIsNone(self.hotel.find_by_room(77, 1))

    def test_no_guests(self):
        empty = HotelSystem.create(3, 4, [])
        stats = empty.load_stats()
        self.assertEqual((stats.total, stats.maximum, stats.minimum, stats.mean, stats.std),
                         (0, 0, 0, 0.0, 0.0))
        self.assertIsNone(stats.cv)
        self.assertEqual(stats.counts, {1: 0, 2: 0, 3: 0})
        report = empty.add_node(4)
        self.assertEqual(report.moved_count, 0)
        self.assertIsNone(report.move_rate)
        self.assertEqual(empty.list_rooms(), [])

    def test_load_includes_zero_nodes(self):
        hotel = HotelSystem.create(5, 1, [3])
        stats = hotel.load_stats()
        self.assertEqual(sorted(stats.counts), [1, 2, 3, 4, 5])
        self.assertEqual(sum(stats.counts.values()), 3)

    def test_invalid_v(self):
        with self.assertRaises(InvalidInputError):
            HotelSystem([1], 0)


class TestListingAndCsv(unittest.TestCase):
    def test_listing_order(self):
        hotel = HotelSystem.create(12, 8, [40] * 6)
        rooms = [(guest.node_id, guest.room_no) for guest in hotel.list_rooms()]
        self.assertEqual(rooms, sorted(rooms))
        self.assertEqual(len(rooms), hotel.guest_count)

    def test_csv_rows_match_guest_count(self):
        hotel = HotelSystem.create(5, 8, [100, 37, 0, 5])
        hotel.remove_guest(1, 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "guests.csv")
            rows = export_guests(hotel, path)
            with open(path, encoding="utf-8", newline="") as file:
                data = list(csv.reader(file))
            self.assertEqual(data[0][:4], ["channel_id", "sequence_id", "node_id", "room_no"])
            self.assertEqual(rows, hotel.guest_count)
            self.assertEqual(len(data) - 1, hotel.guest_count)

            report = hotel.add_node(6)
            moves_path = os.path.join(tmp, "nested", "moves.csv")
            self.assertEqual(export_moves(report, moves_path), report.moved_count)
            with open(moves_path, encoding="utf-8", newline="") as file:
                moves = list(csv.reader(file))
            self.assertEqual(len(moves) - 1, report.moved_count)


if __name__ == "__main__":
    unittest.main(verbosity=2)
