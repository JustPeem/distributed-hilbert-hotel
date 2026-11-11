"""ตัวช่วยสำหรับตรวจสอบค่าที่รับเข้ามา"""

from .errors import InvalidInputError
def require_int(name, value, minimum=None):
    """ตรวจว่า value เป็น int และไม่ต่ำกว่า minimum"""

    # bool เป็น subclass ของ int ใน Python เลยต้องเช็คแยกก่อน
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidInputError(
            f"{name} ต้องเป็นจำนวนเต็ม (ได้รับ {value!r})"
        )

    if minimum is not None:
        if value < minimum:
            raise InvalidInputError(
                f"{name} ต้องมีค่าอย่างน้อย {minimum} (ได้รับ {value})"
            )
    return value