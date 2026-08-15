from datetime import datetime
from pathlib import Path

from .client import BiliClient, BiliError, RiskControlError
from .exporter import AUDIT_FIELDS, RESULT_FIELDS, base_row, write_csv
from .parsers import format_time, match_membership_text


def run_collection(video_input, settings, output_dir):
    client = BiliClient(settings.interval_seconds)
    output_dir = Path(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = output_dir / f"{timestamp}_完整结果.csv"
    audit_path = output_dir / f"{timestamp}_扫描日志.csv"
    sample_only = settings.sample_only_without_cookie and not client.has_cookie

    video = client.resolve_video(video_input)
    mode = 2 if settings.latest_comments else 3
    users, comment_pages = client.sample_comment_users(
        video["aid"],
        settings.sample_users,
        settings.comment_pages,
        mode,
        settings.min_level,
    )

    print(f"\n视频：{video['title']}（{video['bvid']}）")
    print(
        f"评论翻页 {comment_pages} 页，抽到 {len(users)} 个"
        f" Lv{settings.min_level}及以上账号。"
    )
    if sample_only:
        print("未检测到 BILI_COOKIE：本次自动采用基础抽样模式。")

    result_rows = []
    audit_rows = []
    risk_stopped = False

    for index, user in enumerate(users, start=1):
        base = base_row(user, index, video)
        audit = {
            **base,
            "school": "",
            "school_status": "未读取",
            "dynamic_pages_scanned": 0,
            "dynamic_items_scanned": 0,
            "dynamic_scan_complete": "否",
            "first_visible_dynamic_time": "",
            "join_time_basis": "未判定",
            "membership_text_matched": "未判定",
            "scan_status": "仅完成高等级账号抽样",
        }

        if sample_only:
            audit_rows.append(audit)
            continue

        print(f"[{index}/{len(users)}] 读取学校并回溯用户 {user['mid']}……")
        try:
            school = client.get_public_school(user["mid"])
            audit["school"] = school
            audit["school_status"] = "已取得" if school else "用户未公开填写"
        except RiskControlError as exc:
            audit["school_status"] = f"风控停止：{exc}"
            audit["scan_status"] = "学校接口触发风控，未扫描动态"
            audit_rows.append(audit)
            risk_stopped = True
            break
        except BiliError as exc:
            audit["school_status"] = f"读取失败：{exc}"

        try:
            dynamic = client.scan_first_public_dynamic(
                user["mid"], settings.dynamic_pages
            )
            audit["dynamic_pages_scanned"] = dynamic["pages_scanned"]
            audit["dynamic_items_scanned"] = dynamic["items_scanned"]
            audit["dynamic_scan_complete"] = "是" if dynamic["scan_complete"] else "否"
            audit["first_visible_dynamic_time"] = format_time(dynamic["first_timestamp"])

            if not dynamic["scan_complete"]:
                audit["scan_status"] = "达到动态页数上限，不能确认第一条"
            elif not dynamic["first_timestamp"]:
                audit["membership_text_matched"] = "否"
                audit["join_time_basis"] = "没有可见公开动态"
                audit["scan_status"] = "没有可见公开动态"
            else:
                membership = match_membership_text(dynamic["first_text"])
                if membership:
                    audit["membership_text_matched"] = "是"
                    audit["join_time_basis"] = "系统转正动态（较强代理）"
                else:
                    audit["membership_text_matched"] = "否"
                    audit["join_time_basis"] = "最早可见公开动态（弱代理）"

                audit["scan_status"] = "动态完整，已取得最早公开时间"
                result_rows.append(
                    {
                        **base,
                        "school": audit["school"],
                        "school_status": audit["school_status"],
                        "first_visible_dynamic_time": format_time(
                            dynamic["first_timestamp"]
                        ),
                        "join_time_basis": audit["join_time_basis"],
                        "membership_number": (membership or {}).get(
                            "membership_number", ""
                        ),
                        "exam_score": (membership or {}).get("exam_score", ""),
                        "first_dynamic_text": dynamic["first_text"],
                        "dynamic_items_scanned": dynamic["items_scanned"],
                    }
                )
        except RiskControlError as exc:
            audit["scan_status"] = f"风控停止：{exc}"
            risk_stopped = True
        except BiliError as exc:
            audit["scan_status"] = f"读取失败：{exc}"

        audit_rows.append(audit)
        if risk_stopped:
            break

    if risk_stopped:
        finished_mids = {row["mid"] for row in audit_rows}
        for index, user in enumerate(users, start=1):
            if user["mid"] in finished_mids:
                continue
            audit_rows.append(
                {
                    **base_row(user, index, video),
                    "school": "",
                    "school_status": "因风控未读取",
                    "dynamic_pages_scanned": 0,
                    "dynamic_items_scanned": 0,
                    "dynamic_scan_complete": "否",
                    "first_visible_dynamic_time": "",
                    "join_time_basis": "未判定",
                    "membership_text_matched": "未判定",
                    "scan_status": "因风控未继续扫描",
                }
            )

    write_csv(result_path, RESULT_FIELDS, result_rows)
    write_csv(audit_path, AUDIT_FIELDS, audit_rows)
    return {
        "video": video,
        "sample_only": sample_only,
        "users_sampled": len(users),
        "results_count": len(result_rows),
        "result_path": result_path,
        "audit_path": audit_path,
        "risk_stopped": risk_stopped,
    }
