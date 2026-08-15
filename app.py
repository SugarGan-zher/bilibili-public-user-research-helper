#!/usr/bin/env python3
import sys
from pathlib import Path

from bili_helper.client import BiliError
from bili_helper.config import Settings
from bili_helper.workflow import run_collection


def main():
    print("=" * 54)
    print(" Bilibili 高等级用户公开信息采集助手")
    print(" 默认筛选：Lv5 / Lv6，样本数量：50")
    print("=" * 54)

    video = input("\n请粘贴视频链接或BV号，然后按回车：\n> ").strip()
    if not video:
        print("没有输入视频链接，程序结束。")
        return 1

    settings = Settings()
    output_dir = Path(__file__).resolve().parent / "output"

    try:
        result = run_collection(video, settings, output_dir)
    except (ValueError, BiliError) as exc:
        print(f"\n运行失败：{exc}")
        return 1
    except KeyboardInterrupt:
        print("\n用户已停止运行。")
        return 130

    print("\n运行完成")
    print(f"抽样账号：{result['users_sampled']} 个")
    print(f"取得完整最早动态时间：{result['results_count']} 个")
    if result["risk_stopped"]:
        print("平台触发风控，程序已停止继续请求并保存已有日志。")
    if result["sample_only"]:
        print("本次未读取学校和动态；设置 BILI_COOKIE 后会自动运行完整模式。")
    print(f"完整结果：{result['result_path']}")
    print(f"扫描日志：{result['audit_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
