from .errors import InvalidInputError
def require_int(name, value, minimum=None): #เช็ค int
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