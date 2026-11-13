"""รันการทดสอบทั้งหมดแล้วบันทึกผลผ่าน/ไม่ผ่านลง results/test_results.txt"""

import io
import os
import platform
import sys
import unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def main():
    suite = unittest.defaultTestLoader.discover(
        start_dir=os.path.join(ROOT, "tests"),
        pattern="test*.py",
        top_level_dir=ROOT,
    )
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    failed = len(result.failures) + len(result.errors)
    passed = result.testsRun - failed - len(result.skipped)
    summary = (f"วันที่รัน: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
               f"Python {platform.python_version()} ({platform.system()})\n"
               f"ทดสอบทั้งหมด {result.testsRun} รายการ: ผ่าน {passed}, ไม่ผ่าน {failed}\n")
    text = summary + "\n" + stream.getvalue()
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "test_results.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
