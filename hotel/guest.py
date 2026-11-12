from math import isqrt

from .validation import require_int


def cantor_room(c, s):
    require_int("c (ช่องทาง)", c, 1)
    require_int("s (ลำดับ)", s, 1)
    a = c - 1
    b = s - 1
    d = a + b
    return d * (d + 1) // 2 + b + 1


def cantor_unpair(room_no):
    require_int("room_no", room_no, 1)
    z = room_no - 1
    d = (isqrt(8 * z + 1) - 1) // 2
    b = z - d * (d + 1) // 2
    a = d - b
    return a + 1, b + 1


class Guest:

    __slots__ = ("c", "s", "room_no", "position", "node_id")

    def __init__(self, c, s, room_no, position, node_id):
        self.c = c
        self.s = s
        self.room_no = room_no
        self.position = position
        self.node_id = node_id

    @property
    def key(self):
        return (self.c, self.s)

    @property
    def address(self):
        return (self.node_id, self.room_no)

    def __repr__(self):
        return (f"Guest(c={self.c}, s={self.s}, node_id={self.node_id}, "
                f"room_no={self.room_no})")