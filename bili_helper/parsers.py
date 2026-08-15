import re
from datetime import datetime, timedelta, timezone


SHANGHAI_TZ = timezone(timedelta(hours=8))
MEMBER_PATTERN = re.compile(
    r"我已成为哔哩哔哩第\s*([\d,，]+)\s*位转正会员"
    r".*?挑战转正答题考试获得\s*(\d+)\s*分",
    re.DOTALL,
)


def format_time(timestamp):
    if not timestamp:
        return ""
    return datetime.fromtimestamp(int(timestamp), SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")


def parse_video_id(value):
    bvid_match = re.search(r"BV[0-9A-Za-z]{10}", value)
    if bvid_match:
        return "bvid", bvid_match.group(0)

    aid_match = re.search(r"(?:av)?(\d+)", value, re.IGNORECASE)
    if aid_match and (value.lower().startswith("av") or value.isdigit()):
        return "aid", aid_match.group(1)
    raise ValueError("无法识别视频编号，请输入完整链接、BV号或av号。")


def _strings_from_object(value):
    strings = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            strings.extend(_strings_from_object(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(_strings_from_object(child))
    return strings


def dynamic_text(item):
    modules = item.get("modules") or {}
    module_dynamic = modules.get("module_dynamic") or {}
    # 不读取 item.orig，避免把转发来源账号的文字算作当前用户的内容。
    text = " ".join(_strings_from_object(module_dynamic))
    return re.sub(r"\s+", " ", text).strip()


def match_membership_text(text):
    match = MEMBER_PATTERN.search(text or "")
    if not match:
        return None
    return {
        "membership_number": re.sub(r"[,，]", "", match.group(1)),
        "exam_score": match.group(2),
    }
