import hashlib


RING_BITS = 64
RING_SIZE = 1 << RING_BITS       # 2^64 ตำแหน่ง
RING_MAX = RING_SIZE - 1


def ring_position(text): #hash function หลัก
    # ใช้ SHA-256 เพื่อให้ค่า hash คงที่ทุกครั้งที่รัน
    digest = hashlib.sha256(text.encode("utf-8")).digest()

    # เลือก 8 bytes แรก แล้วแปลงเป็น unsigned integer
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _with_salt(base, salt):
    salt = str(salt)

    if salt == "":
        return base

    return f"{base}|salt:{salt}"


def guest_text(c, s, salt=""):
    # สร้างข้อความสำหรับ guest ก่อนนำไป hash
    base = f"guest:{c}:{s}"
    return _with_salt(base, salt)


def node_text(node_id, j, salt=""):
    # j คือ index ของ virtual node (0 ถึง V-1)
    base = f"node:{node_id}:{j}"
    return _with_salt(base, salt)


def guest_position(c, s, salt=""):
    """หาตำแหน่งของ guest (c, s) บนวงแหวน"""

    text = guest_text(c, s, salt)
    return ring_position(text)


def node_position(node_id, j, salt=""):
    """หาตำแหน่ง virtual node ของอาคาร"""

    text = node_text(node_id, j, salt)
    return ring_position(text)