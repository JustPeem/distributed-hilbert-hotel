"""ส่งออกไฟล์ CSV แบบ UTF-8 (ฟังก์ชันที่ 10) ไฟล์ส่งออกมีข้อมูลครบทุกแถวเสมอ"""

import csv
import os


def write_rows(path, header, rows):
    """เขียน CSV แล้วคืนจำนวนแถวข้อมูล (ไม่นับหัวตาราง)"""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def export_guests(system, path):
    """ส่งออกรายชื่อแขก เรียงตามอาคารและห้อง"""
    rows = ((guest.c, guest.s, guest.node_id, guest.room_no, guest.position)
            for guest in system.list_rooms())
    return write_rows(path, ["channel_id", "sequence_id", "node_id", "room_no",
                             "ring_position"], rows)


def export_moves(report, path):
    """ส่งออกรายการย้าย พร้อมอาคารเดิมและอาคารใหม่"""
    rows = ((report.operation, report.node_id, move.channel_id, move.sequence_id,
             move.old_node, move.new_node, move.room_no)
            for move in report.sorted_moves())
    return write_rows(path, ["operation", "changed_node", "channel_id", "sequence_id",
                             "old_node_id", "new_node_id", "room_no"], rows)
