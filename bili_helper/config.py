from dataclasses import dataclass


@dataclass
class Settings:
    """常用参数集中放在这里，后续只需要修改这一处。"""

    sample_users: int = 50
    min_level: int = 5
    comment_pages: int = 10
    dynamic_pages: int = 30
    interval_seconds: float = 2.5
    latest_comments: bool = True

    # 未设置 BILI_COOKIE 时自动只做等级与大会员抽样，保证程序仍能运行。
    sample_only_without_cookie: bool = True
