import asyncio
import logging
from datetime import datetime
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

from .models import Article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScrapingError(Exception):
    """スクレイピング処理で発生するエラーを表すカスタム例外"""

    pass


class AdventCalendarScraper:
    def __init__(self, calendar_url: str):
        self.calendar_url = calendar_url
        # 非同期HTTPクライアントの設定。タイムアウトを30秒に設定
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0), follow_redirects=True
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def scrape_calendar(self) -> List[Article]:
        """
        アドベントカレンダーのメインページから記事の一覧を取得します。
        各記事の基本情報を含むArticleオブジェクトのリストを返します。
        """
        try:
            response = await self.client.get(self.calendar_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            articles: List[Article] = []

            # エントリーリストから各記事の情報を抽出
            for entry in soup.select(".EntryList .item"):
                try:
                    # 日付を取得 (例: "12/1" -> 2024-12-01)
                    date_str = entry.select_one(".date").text.strip()
                    month, day = map(int, date_str.split("/"))
                    entry_date = date(2024, month, day)

                    # ユーザー名を取得
                    handle_name = entry.select_one(".user a").text.strip()

                    # 記事情報を取得
                    article_div = entry.select_one(".article")
                    if article_div:
                        url = article_div.select_one(".link a")["href"]
                        title = article_div.select_one(
                            ".left div:nth-child(2)"
                        ).text.strip()
                    else:
                        # 記事がまだ投稿されていない場合はスキップ
                        continue

                    # コメントセクションから概要を取得（存在する場合）
                    comment_div = entry.select_one(".comment")
                    summary = comment_div.text.strip() if comment_div else None

                    article = Article(
                        date=entry_date,
                        handle_name=handle_name,
                        title=title,
                        genre=None,  # ジャンルは後続のAI処理で設定
                        summary=summary,
                        url=url,
                    )
                    articles.append(article)

                except (AttributeError, KeyError, ValueError) as e:
                    logger.warning(f"記事エントリーの解析に失敗しました: {e}")
                    continue

            return sorted(articles, key=lambda x: x.date)

        except httpx.HTTPError as e:
            raise ScrapingError(f"カレンダーページの取得に失敗しました: {e}")

    async def scrape_article(self, article: Article, retry_count: int = 3) -> None:
        """
        個別の記事ページのHTMLを取得し、Articleオブジェクトのcontentフィールドに設定します。
        後続のAI処理のための生のHTMLを保持します。
        """
        for attempt in range(retry_count):
            try:
                # サーバーへの負荷を考慮して、リクエスト間に短い待機を入れる
                await asyncio.sleep(1)

                response = await self.client.get(article.url)
                response.raise_for_status()

                # 記事ページのHTMLをそのまま保持
                article.content = response.text
                return

            except httpx.HTTPError as e:
                if attempt == retry_count - 1:  # 最後のリトライの場合
                    logger.error(
                        f"記事の取得に失敗しました（{retry_count}回目）: {article.url}"
                    )
                    raise ScrapingError(f"記事の取得に失敗しました: {e}")

                logger.warning(f"記事の取得に失敗しました（{attempt + 1}回目）: {e}")
                # 次のリトライまでの待機時間を指数関数的に増やす
                await asyncio.sleep(2**attempt)
