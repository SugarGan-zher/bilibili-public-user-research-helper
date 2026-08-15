import hashlib
import json
import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from .parsers import dynamic_text, parse_video_id


API_ROOT = "https://api.bilibili.com"
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

FALLBACK_WBI_IMG_KEY = "7cd084941338484aae1ad9425b84077c"
FALLBACK_WBI_SUB_KEY = "4932caff0ff746eab6f01bf08b70ac45"


class BiliError(Exception):
    pass


class RiskControlError(BiliError):
    pass


class BiliClient:
    def __init__(self, interval=2.5):
        self.interval = max(float(interval), 1.5)
        self.last_request_time = 0.0
        self.mixin_key = ""
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                ),
                "Referer": "https://www.bilibili.com/",
                "Accept": "application/json, text/plain, */*",
            }
        )

        cookie = os.getenv("BILI_COOKIE", "").strip()
        self.has_cookie = bool(cookie)
        if cookie:
            self.session.headers["Cookie"] = cookie

    def _wait(self):
        elapsed = time.monotonic() - self.last_request_time
        wait_seconds = self.interval + random.uniform(0.15, 0.45) - elapsed
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    def get_json(self, path, params=None, referer=None, retries=2):
        url = API_ROOT + path
        last_error = None
        for attempt in range(retries + 1):
            self._wait()
            try:
                headers = {"Referer": referer} if referer else None
                response = self.session.get(url, params=params, headers=headers, timeout=15)
                self.last_request_time = time.monotonic()

                if response.status_code in (412, 429):
                    raise RiskControlError(f"HTTP {response.status_code}：平台拒绝访问")
                response.raise_for_status()
                if "text/html" in response.headers.get("Content-Type", "").lower():
                    raise RiskControlError("接口返回验证码页面")

                payload = response.json()
                code = payload.get("code", 0)
                if code in (-352, -799):
                    raise RiskControlError(f"接口风控：{payload.get('message', code)}")
                if code != 0:
                    raise BiliError(f"接口错误 {code}：{payload.get('message', '未知错误')}")
                return payload.get("data") or {}
            except (RiskControlError, BiliError):
                raise
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(2 ** attempt)
        raise BiliError(str(last_error))

    def resolve_video(self, value):
        id_type, video_id = parse_video_id(value)
        data = self.get_json("/x/web-interface/view", {id_type: video_id})
        return {
            "aid": str(data["aid"]),
            "bvid": data.get("bvid", ""),
            "title": data.get("title", ""),
        }

    def _load_mixin_key(self):
        if self.mixin_key:
            return self.mixin_key
        try:
            data = self.get_json("/x/web-interface/nav")
            wbi_img = data.get("wbi_img") or {}
            img_key = Path(wbi_img.get("img_url", "")).stem
            sub_key = Path(wbi_img.get("sub_url", "")).stem
        except RiskControlError:
            raise
        except BiliError:
            img_key = FALLBACK_WBI_IMG_KEY
            sub_key = FALLBACK_WBI_SUB_KEY

        raw_key = img_key + sub_key
        if len(raw_key) < 64:
            raise BiliError("未能取得WBI签名密钥")
        self.mixin_key = "".join(raw_key[index] for index in MIXIN_KEY_ENC_TAB)[:32]
        return self.mixin_key

    def wbi_get_json(self, path, params, referer=None):
        params = dict(params)
        params["wts"] = int(time.time())
        clean_params = {
            key: re.sub(r"[!'()*]", "", str(value))
            for key, value in sorted(params.items())
        }
        query = urlencode(clean_params)
        clean_params["w_rid"] = hashlib.md5(
            (query + self._load_mixin_key()).encode()
        ).hexdigest()
        return self.get_json(path, clean_params, referer=referer)

    def sample_comment_users(self, aid, target_users, max_pages, mode, min_level):
        users = {}
        offset = ""
        pages_scanned = 0

        while len(users) < target_users and pages_scanned < max_pages:
            data = self.wbi_get_json(
                "/x/v2/reply/wbi/main",
                {
                    "type": 1,
                    "oid": aid,
                    "mode": mode,
                    "pagination_str": json.dumps(
                        {"offset": offset}, ensure_ascii=False, separators=(",", ":")
                    ),
                    "plat": 1,
                    "web_location": 1315875,
                },
            )
            pages_scanned += 1
            replies = data.get("replies") or []
            if not replies:
                break

            for reply in replies:
                member = reply.get("member") or {}
                mid = str(reply.get("mid") or member.get("mid") or "")
                if not mid or mid == "0" or mid in users:
                    continue

                level = int((member.get("level_info") or {}).get("current_level") or 0)
                if level < min_level:
                    continue

                vip = member.get("vip") or {}
                vip_label = (vip.get("label") or {}).get("text", "")
                users[mid] = {
                    "mid": mid,
                    "username": member.get("uname", ""),
                    "account_level": level,
                    "vip_status": vip_label if vip.get("vipStatus") == 1 else "非大会员",
                }
                if len(users) >= target_users:
                    break

            cursor = data.get("cursor") or {}
            pagination = cursor.get("pagination_reply") or {}
            next_offset = str(pagination.get("next_offset") or "")
            if cursor.get("is_end") or not next_offset or next_offset == offset:
                break
            offset = next_offset

        return list(users.values()), pages_scanned

    def get_public_school(self, mid):
        data = self.wbi_get_json(
            "/x/space/wbi/acc/info",
            {"mid": mid},
            referer=f"https://space.bilibili.com/{mid}",
        )
        school = data.get("school") or {}
        return str(school.get("name") or "").strip() if isinstance(school, dict) else ""

    def scan_first_public_dynamic(self, mid, max_pages):
        offset = ""
        pages_scanned = 0
        items_scanned = 0
        earliest = None
        scan_complete = False

        while pages_scanned < max_pages:
            params = {"host_mid": mid, "timezone_offset": -480}
            if offset:
                params["offset"] = offset
            data = self.get_json(
                "/x/polymer/web-dynamic/v1/feed/space",
                params,
                referer=f"https://space.bilibili.com/{mid}/dynamic",
            )
            pages_scanned += 1
            items = data.get("items") or []

            for item in items:
                author = ((item.get("modules") or {}).get("module_author") or {})
                timestamp = int(author.get("pub_ts") or 0)
                if not timestamp:
                    continue
                items_scanned += 1
                candidate = {"timestamp": timestamp, "text": dynamic_text(item)}
                if earliest is None or timestamp < earliest["timestamp"]:
                    earliest = candidate

            next_offset = str(data.get("offset") or "")
            if not data.get("has_more") or not next_offset or not items:
                scan_complete = True
                break
            offset = next_offset

        return {
            "pages_scanned": pages_scanned,
            "items_scanned": items_scanned,
            "scan_complete": scan_complete,
            "first_timestamp": (earliest or {}).get("timestamp", 0),
            "first_text": (earliest or {}).get("text", ""),
        }
