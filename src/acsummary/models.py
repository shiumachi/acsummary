from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class Article:
    date: date
    handle_name: str
    title: str
    genre: Optional[str]
    summary: Optional[str]
    url: str
    content: Optional[str] = None  # スクレイピングした記事本文