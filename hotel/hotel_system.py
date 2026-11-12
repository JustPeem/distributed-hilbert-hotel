import math
import time
from bisect import bisect_left
from dataclasses import dataclass, field

from .errors import (DuplicateGuestError, DuplicateNodeError,
                     GuestNotFoundError, InvalidInputError, LastNodeError,
                     NodeNotFoundError)
from .guest import Guest, cantor_room
from .hash_ring import HashRing
from .hashing import guest_position
from .validation import require_int


@dataclass(frozen=True)
class Move:
    """แขกหนึ่งคนที่เปลี่ยนอาคาร (room_no คงเดิมเสมอ)"""
    channel_id: int
    sequence_id: int
    old_node: int
    new_node: int
    room_no: int


@dataclass
class MoveReport:
    """ผลของคำสั่งเพิ่ม/ลบอาคารหนึ่งครั้ง (หัวข้อ 4.4)"""
    operation: str            # "add_node" หรือ "remove_node"
    node_id: int
    method: str               # "ch-range" (แบบ ข), "ch-scan" (แบบ ก), "mod-n"
    guests_total: int         # K ก่อนคำสั่ง
    nodes_before: int         # N ก่อนคำสั่ง
    moves: list = field(default_factory=list)
    ring_update_s: float = 0.0   # (ก) ปรับวงแหวน / รายการอาคาร
    find_s: float = 0.0          # (ข) หาแขกที่ได้รับผลกระทบ
    apply_s: float = 0.0         # (ค) ปรับข้อมูลและดัชนีของแขกที่ย้าย

    @property
    def moved_count(self):
        return len(self.moves)

    @property
    def move_rate(self):
        """จำนวนแขกที่ย้าย / K หรือ None เมื่อ K = 0 (ไม่คำนวณอัตรา)"""
        if self.guests_total == 0:
            return None
        return self.moved_count / self.guests_total

    @property
    def total_s(self):
        return self.ring_update_s + self.find_s + self.apply_s

    def sorted_moves(self):
        return sorted(self.moves, key=lambda m: (m.channel_id, m.sequence_id))


@dataclass
class LoadStats:
    counts: dict
    total: int
    maximum: int
    minimum: int
    mean: float
    std: float
    cv: object


def compute_load_stats(counts):
    ordered = {nid: counts[nid] for nid in sorted(counts)}
    values = list(ordered.values())
    total = sum(values)
    if total == 0 or not values:
        return LoadStats(ordered, 0, 0, 0, 0.0, 0.0, None)
    n = len(values)
    mean = total / n
    std = math.sqrt(sum((x - mean) ** 2 for x in values) / n)
    return LoadStats(ordered, total, max(values), min(values), mean, std, std / mean)


class HotelSystem:
    def __init__(self, node_ids, v, salt="", reassign="range",
                 guest_position_fn=None, node_position_fn=None):
        if reassign not in ("range", "scan"):
            raise InvalidInputError("reassign ต้องเป็น 'range' หรือ 'scan'")
        ids = list(node_ids)
        if not ids:
            raise InvalidInputError("ต้องมีอาคารอย่างน้อย 1 หลัง (N ≥ 1)")
        self._salt = str(salt)
        if guest_position_fn is None:
            salt_text = self._salt
            guest_position_fn = lambda c, s: guest_position(c, s, salt_text)
        self._guest_pos_fn = guest_position_fn
        self._node_pos_fn = node_position_fn
        self._ring = HashRing(v, self._salt, node_position_fn)
        self._ring.build(ids)
        self._guests = {}
        self._room_index = {}
        self._node_guests = {node_id: set() for node_id in ids}
        self._sorted = []
        self.reassign = reassign

    @classmethod
    def create(cls, n_nodes, v, channel_counts, salt="", **kwargs):
        require_int("จำนวนอาคาร N", n_nodes, 1)
        counts = list(channel_counts)
        for i, count in enumerate(counts, start=1):
            require_int(f"จำนวนแขกของช่องทาง {i}", count, 0)
        system = cls(range(1, n_nodes + 1), v, salt, **kwargs)
        keys = [(c, s) for c, count in enumerate(counts, start=1)
                for s in range(1, count + 1)]
        system.add_guests(keys)
        return system

    @property
    def ring(self):
        return self._ring

    @property
    def salt(self):
        return self._salt

    @property
    def v(self):
        return self._ring.v

    @property
    def guest_count(self):
        return len(self._guests)

    @property
    def node_count(self):
        return self._ring.node_count

    def node_ids(self):
        return self._ring.node_ids()

    def guest_keys(self):
        return list(self._guests)

    def _make_guest(self, c, s):
        position = self._guest_pos_fn(c, s)
        return Guest(c, s, cantor_room(c, s), position, self._ring.locate(position))

    def _index_guest(self, guest):
        key = guest.key
        address = guest.address
        if address in self._room_index:
            raise RuntimeError(f"ที่อยู่ห้อง {address} ถูกใช้แล้ว")
        self._guests[key] = guest
        self._room_index[address] = guest
        self._node_guests[guest.node_id].add(key)

    def add_guest(self, c, s):
        require_int("c (ช่องทาง)", c, 1)
        require_int("s (ลำดับ)", s, 1)
        if (c, s) in self._guests:
            raise DuplicateGuestError(f"แขก ({c}, {s}) อยู่ในระบบแล้ว ไม่เพิ่มซ้ำ")
        guest = self._make_guest(c, s)
        self._index_guest(guest)
        entry = (guest.position, c, s)
        self._sorted.insert(bisect_left(self._sorted, entry), entry)
        return guest

    def add_group(self, c, s_start, count):
        require_int("c (ช่องทาง)", c, 1)
        require_int("s_start", s_start, 1)
        require_int("จำนวนแขก", count, 0)
        if count == 0:
            return []
        keys = [(c, s) for s in range(s_start, s_start + count)]
        conflicts = [k for k in keys if k in self._guests]
        if conflicts:
            sample = ", ".join(str(k) for k in conflicts[:5])
            more = " ..." if len(conflicts) > 5 else ""
            raise DuplicateGuestError(
                f"ช่วง ({c}, {s_start})–({c}, {s_start + count - 1}) ทับกับแขกที่มีอยู่ "
                f"{len(conflicts)} คน เช่น {sample}{more} — ปฏิเสธทั้งกลุ่ม ข้อมูลเดิมไม่เปลี่ยน")
        return self._insert_many(keys)

    def add_guests(self, keys):
        keys = list(keys)
        seen = set()
        for c, s in keys:
            require_int("c (ช่องทาง)", c, 1)
            require_int("s (ลำดับ)", s, 1)
            if (c, s) in self._guests or (c, s) in seen:
                raise DuplicateGuestError(f"รหัสแขก ({c}, {s}) ซ้ำ — ปฏิเสธทั้งชุด ข้อมูลเดิมไม่เปลี่ยน")
            seen.add((c, s))
        return self._insert_many(keys)

    def _insert_many(self, keys):
        new_guests = [self._make_guest(c, s) for c, s in keys]
        for guest in new_guests:
            self._index_guest(guest)
        entries = sorted((g.position, g.c, g.s) for g in new_guests)
        merged = self._sorted + entries
        merged.sort()
        self._sorted = merged
        return new_guests

    def remove_guest(self, c, s):
        require_int("c (ช่องทาง)", c, 1)
        require_int("s (ลำดับ)", s, 1)
        guest = self._guests.get((c, s))
        if guest is None:
            raise GuestNotFoundError(f"ไม่พบแขก ({c}, {s}) จึงไม่ได้นำใครออก")
        del self._guests[(c, s)]
        del self._room_index[guest.address]
        self._node_guests[guest.node_id].discard((c, s))
        entry = (guest.position, c, s)
        i = bisect_left(self._sorted, entry)
        if i == len(self._sorted) or self._sorted[i] != entry:
            raise RuntimeError("ดัชนีตำแหน่งไม่สอดคล้องกับข้อมูลแขก")
        del self._sorted[i]
        return guest

    def find_by_guest(self, c, s):
        require_int("c (ช่องทาง)", c, 1)
        require_int("s (ลำดับ)", s, 1)
        return self._guests.get((c, s))

    def find_by_room(self, node_id, room_no):
        require_int("รหัสอาคาร", node_id, 0)
        require_int("room_no", room_no, 1)
        return self._room_index.get((node_id, room_no))

    def compute_node(self, c, s):
        require_int("c (ช่องทาง)", c, 1)
        require_int("s (ลำดับ)", s, 1)
        return self._ring.locate(self._guest_pos_fn(c, s))

    def list_rooms(self):
        result = []
        for node_id in sorted(self._node_guests):
            group = [self._guests[k] for k in self._node_guests[node_id]]
            group.sort(key=lambda g: g.room_no)
            result.extend(group)
        return result

    def load_counts(self):
        return {nid: len(keys) for nid, keys in self._node_guests.items()}

    def load_stats(self):
        return compute_load_stats(self.load_counts())

    def assignments(self):
        return {k: g.address for k, g in self._guests.items()}

    def add_node(self, node_id):
        """ฟังก์ชันที่ 4 (เพิ่ม): แขกที่ย้ายต้องย้ายเข้าอาคารใหม่เท่านั้น"""
        require_int("รหัสอาคาร", node_id, 0)
        if self._ring.has_node(node_id):
            raise DuplicateNodeError(f"มีอาคารรหัส {node_id} อยู่แล้ว ไม่เพิ่มซ้ำ")
        report = MoveReport("add_node", node_id, "ch-" + self.reassign,
                            len(self._guests), self._ring.node_count)
        t0 = time.perf_counter()
        self._ring.add_node(node_id)
        self._node_guests[node_id] = set()
        t1 = time.perf_counter()
        if self.reassign == "range":
            moves = []
            sorted_entries = self._sorted
            for lo, hi in self._ring.owned_arcs(node_id):
                start = bisect_left(sorted_entries, (lo + 1,))
                end = bisect_left(sorted_entries, (hi + 1,))
                for idx in range(start, end):
                    _, c, s = sorted_entries[idx]
                    guest = self._guests[(c, s)]
                    moves.append(Move(c, s, guest.node_id, node_id, guest.room_no))
        else:
            moves = self._scan_changes()
        t2 = time.perf_counter()
        self._apply_moves(moves)
        t3 = time.perf_counter()
        report.moves = moves
        report.ring_update_s, report.find_s, report.apply_s = t1 - t0, t2 - t1, t3 - t2
        return report

    def remove_node(self, node_id):
        """ฟังก์ชันที่ 4 (ลบ): แขกในอาคารอื่นต้องไม่ย้าย"""
        require_int("รหัสอาคาร", node_id, 0)
        if not self._ring.has_node(node_id):
            raise NodeNotFoundError(f"ไม่มีอาคารรหัส {node_id} จึงไม่ได้ลบอะไร (ไม่มีแขกย้าย)")
        if self._ring.node_count == 1:
            raise LastNodeError("ลบอาคารสุดท้ายไม่ได้ ระบบต้องมีอาคารอย่างน้อย 1 หลัง (N ≥ 1)")
        report = MoveReport("remove_node", node_id, "ch-" + self.reassign,
                            len(self._guests), self._ring.node_count)
        t0 = time.perf_counter()
        self._ring.remove_node(node_id)
        t1 = time.perf_counter()
        if self.reassign == "range":
            # แขกที่ได้รับผลกระทบคือแขกในช่วงของอาคารที่ถูกลบ = แขกของอาคารนั้นพอดี
            locate = self._ring.locate
            moves = []
            for key in self._node_guests[node_id]:
                guest = self._guests[key]
                moves.append(Move(guest.c, guest.s, node_id, locate(guest.position),
                                  guest.room_no))
        else:
            moves = self._scan_changes()
        t2 = time.perf_counter()
        self._apply_moves(moves)
        del self._node_guests[node_id]
        t3 = time.perf_counter()
        report.moves = moves
        report.ring_update_s, report.find_s, report.apply_s = t1 - t0, t2 - t1, t3 - t2
        return report

    def _scan_changes(self):
        """แบบ ก: คำนวณอาคารใหม่ให้แขกทุกคน O(K log M)"""
        locate = self._ring.locate
        moves = []
        for guest in self._guests.values():
            new_node = locate(guest.position)
            if new_node != guest.node_id:
                moves.append(Move(guest.c, guest.s, guest.node_id, new_node, guest.room_no))
        return moves

    def _apply_moves(self, moves):
        """ปรับ Guest, _room_index และ _node_guests ให้สอดคล้องกัน: O(m) เมื่อ m = จำนวนที่ย้าย
        (_sorted ไม่ต้องแก้ เพราะตำแหน่งบนวงแหวนของแขกไม่เปลี่ยน)
        """
        for m in moves:
            key = (m.channel_id, m.sequence_id)
            guest = self._guests[key]
            del self._room_index[(m.old_node, m.room_no)]
            self._node_guests[m.old_node].discard(key)
            guest.node_id = m.new_node
            self._room_index[(m.new_node, m.room_no)] = guest
            self._node_guests[m.new_node].add(key)

    def check_consistency(self):
        problems = []
        k = len(self._guests)
        if len(self._room_index) != k:
            problems.append(f"room_index มี {len(self._room_index)} รายการ แต่มีแขก {k} คน")
        if len(self._sorted) != k:
            problems.append(f"ดัชนีตำแหน่งมี {len(self._sorted)} รายการ แต่มีแขก {k} คน")
        if sum(len(v) for v in self._node_guests.values()) != k:
            problems.append("ผลรวมแขกรายอาคารไม่เท่ากับ K")
        if set(self._node_guests) != set(self._ring.node_ids()):
            problems.append("รายชื่ออาคารในดัชนีไม่ตรงกับวงแหวน")
        if any(self._sorted[i] > self._sorted[i + 1] for i in range(len(self._sorted) - 1)):
            problems.append("ดัชนีตำแหน่งไม่ได้เรียง")
        for key, g in self._guests.items():
            if g.room_no != cantor_room(g.c, g.s):
                problems.append(f"{key}: room_no ไม่ตรงสูตร")
            if g.position != self._guest_pos_fn(g.c, g.s):
                problems.append(f"{key}: ตำแหน่งไม่ตรงแฮช")
            if g.node_id != self._ring.locate(g.position):
                problems.append(f"{key}: อาคารที่บันทึกไม่ตรงกับที่คำนวณจากวงแหวน")
            if self._room_index.get(g.address) is not g:
                problems.append(f"{key}: ค้นด้วยที่อยู่ห้องแล้วไม่ได้แขกคนนี้")
            if key not in self._node_guests.get(g.node_id, ()):
                problems.append(f"{key}: ไม่อยู่ในรายชื่อแขกของอาคาร {g.node_id}")
        if {(p, c, s) for p, c, s in self._sorted} != \
                {(g.position, g.c, g.s) for g in self._guests.values()}:
            problems.append("ดัชนีตำแหน่งมีสมาชิกไม่ตรงกับข้อมูลแขก")
        return problems