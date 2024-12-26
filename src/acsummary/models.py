from dataclasses import dataclass
from datetime import date


@dataclass
class Article:
    date: date
    handle_name: str
    title: str
    genre: str | None
    summary: str | None
    url: str
    content: str | None = None  # スクレイピングした記事本文
