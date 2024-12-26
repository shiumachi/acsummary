import asyncio
import logging
from datetime import date, datetime
from typing import TypeAlias
import httpx
from bs4 import BeautifulSoup
from .models import Article

# 型エイリアスの定義
ResponseType: TypeAlias = httpx.Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScrapingError(Exception):
    """スクレイピング処理で発生するエラーを表すカスタム例外"""

class AdventCalendarScraper:
    def __init__(self, calendar_url: str) -> None:
        self.calendar_url = calendar_url
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0), 
            follow_redirects=True
        )

    async def __aenter__(self) -> "AdventCalendarScraper":
        return self

    async def __aexit__(self, 
                        exc_type: type[BaseException] | None, 
                        exc_val: BaseException | None, 
                        exc_tb: object | None) -> None:
        await self.client.aclose()

    async def scrape_calendar(self) -> list[Article]:
        """アドベントカレンダーのメインページから記事の一覧を取得"""
        try:
            response: ResponseType = await self.client.get(self.calendar_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            articles: list[Article] = []

            for entry in soup.select(".EntryList .item"):
                try:
                    date_str: str = entry.select_one(".date").text.strip()
                    month, day = map(int, date_str.split("/"))
                    entry_date = date(2024, month, day)

                    handle_name: str = entry.select_one(".user a").text.strip()

                    article_div = entry.select_one(".article")
                    if article_div:
                        url: str = article_div.select_one(".link a")["href"]
                        title: str = article_div.select_one(
                            ".left div:nth-child(2)"
                        ).text.strip()
                    else: