import csv
from pathlib import Path


RESULT_FIELDS = [
    "anonymous_id",
    "mid",
    "username",
    "account_level",
    "vip_status",
    "school",
    "school_status",
    "first_visible_dynamic_time",
    "join_time_basis",
    "membership_number",
    "exam_score",
    "first_dynamic_text",
    "dynamic_items_scanned",
    "source_video_bvid",
    "source_video_title",
]

AUDIT_FIELDS = [
    "anonymous_id",
    "mid",
    "username",
    "account_level",
    "vip_status",
    "school",
    "school_status",
    "dynamic_pages_scanned",
    "dynamic_items_scanned",
    "dynamic_scan_complete",
    "first_visible_dynamic_time",
    "join_time_basis",
    "membership_text_matched",
    "scan_status",
    "source_video_bvid",
    "source_video_title",
]


def base_row(user, index, video):
    return {
        "anonymous_id": f"U{index:03d}",
        "mid": user["mid"],
        "username": user.get("username", ""),
        "account_level": user.get("account_level", ""),
        "vip_status": user.get("vip_status", ""),
        "source_video_bvid": video.get("bvid", ""),
        "source_video_title": video.get("title", ""),
    }


def write_csv(path, fields, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
