class HotelError(Exception):
    """Base exception ของระบบโรงแรม"""


class InvalidInputError(HotelError, ValueError):
    """ค่าที่รับเข้ามาไม่ถูกต้อง เช่น type ผิด หรืออยู่นอกช่วงที่กำหนด"""


class DuplicateNodeError(HotelError):
    """เกิดเมื่อพยายามเพิ่ม node ที่มีอยู่แล้ว"""


class NodeNotFoundError(HotelError):
    """ไม่พบ node ที่ต้องการอ้างถึง"""


class LastNodeError(HotelError):
    """ไม่สามารถลบ node สุดท้ายได้ เพราะ N ต้องไม่น้อยกว่า 1"""


class EmptyRingError(HotelError):
    """เกิดเมื่อค้นหาบน ring ที่ไม่มี virtual node อยู่เลย"""


class DuplicateGuestError(HotelError):
    """เพิ่ม guest (c, s) ซ้ำกับข้อมูลที่มีอยู่แล้ว"""


class GuestNotFoundError(HotelError):
    """ไม่พบ guest ที่ต้องการนำออก"""