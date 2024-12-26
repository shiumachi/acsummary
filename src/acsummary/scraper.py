from datetime import date
import logging
from typing import Any, AsyncIterator
import aiohttp
from bs4 import BeautifulSoup
from .models import Article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScrapingError(Exception):
    """スクレイピング処理で発生するエラーを表すカスタム例外"""


class AdventCalendarScraper:
    def __init__(self, calendar_url: str) -> None:
        """
        AdventCalendarScraperの初期化

        Args:
            calendar_url: スクレイピング対象のアドベントカレンダーURL
        """
        self.calendar_url = calendar_url
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "AdventCalendarScraper":
        """非同期コンテキストマネージャのエントリーポイント"""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """非同期コンテキストマネージャの終了処理"""
        if self._session:
            await self._session.close()
            self._session = None

    async def _fetch_page(self, url: str) -> str:
        """
        指定URLのページを取得

        Args:
            url: 取得対象のURL

        Returns:
            ページのHTML文字列

        Raises:
            ScrapingError: ページの取得に失敗した場合
        """
        if not self._session:
            raise ScrapingError("セッションが初期化されていません")

        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            raise ScrapingError(f"ページの取得に失敗しました: {url} - {e}")

    def _parse_calendar_page(
        self, html: str
    ) -> list[tuple[date, str, str, str | None]]:
        """
        カレンダーページからエントリー情報を抽出

        Args:
            html: パース対象のHTML文字列

        Returns:
            (日付, 投稿者名, 記事URL, コメント)のタプルのリスト

        Raises:
            ScrapingError: パースに失敗した場合
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            entries: list[tuple[date, str, str, str | None]] = []

            # 各日付のセルを取得
            cells = soup.find_all("td", class_="cell")

            for cell in cells:
                # 空のセルはスキップ
                if "inner" not in str(cell):
                    continue

                # 日付を取得
                day_elem = cell.select_one(".day")
                if not day_elem or not day_elem.text.strip().isdigit():
                    continue

                day = int(day_elem.text.strip())
                entry_date = date(2024, 12, day)  # 年月は固定

                # 投稿者名を取得
                user_elem = cell.select_one(".userName")
                if not user_elem:
                    continue
                handle_name = user_elem.text.strip()

                # 記事URLとコメントを取得（記事が投稿済みの場合）
                article_info = self._find_article_info(day, soup)
                if not article_info:
                    continue

                url, comment = article_info
                entries.append((entry_date, handle_name, url, comment))

            return entries

        except Exception as e:
            raise ScrapingError(f"カレンダーページのパースに失敗しました: {e}")

    def _find_article_info(
        self, day: int, soup: BeautifulSoup
    ) -> tuple[str, str | None] | None:
        """
        記事の情報（URL、コメント）を取得

        Args:
            day: 対象の日付
            soup: パース済みのBeautifulSoupオブジェクト

        Returns:
            (URL, コメント)のタプル。記事が未投稿の場合はNone
        """
        # 記事リストから該当日の記事を探す
        articles = soup.find_all("li", class_="item")
        for article in articles:
            date_elem = article.select_one(".date")
            if not date_elem:
                continue

            # 日付が一致するかチェック
            article_day = date_elem.text.strip().split("/")[-1]
            if not article_day.isdigit() or int(article_day) != day:
                continue

            # URLを取得
            link_elem = article.select_one(".link a")
            if not link_elem or not link_elem.get("href"):
                continue
            url = link_elem["href"]

            # コメントを取得（任意）
            comment_elem = article.select_one(".comment")
            comment = comment_elem.text.strip() if comment_elem else None

            return url, comment

        return None

    async def scrape_articles(self) -> AsyncIterator[Article]:
        """
        カレンダーの全記事をスクレイピング

        Yields:
            Article: スクレイピングした記事情報

        Raises:
            ScrapingError: スクレイピングに失敗した場合
        """
        try:
            # カレンダーページを取得・パース
            calendar_html = await self._fetch_page(self.calendar_url)
            entries = self._parse_calendar_page(calendar_html)

            # 各記事を処理
            for entry_date, handle_name, url, comment in entries:
                try:
                    # 記事オブジェクトを生成
                    # content はAI処理で使用するため取得しない
                    article = Article(
                        date=entry_date,
                        handle_name=handle_name,
                        title="",  # APIでタイトルを取得予定
                        genre=None,  # AI処理で設定
                        summary=comment,  # とりあえずコメントを設定
                        url=url,
                        content=None,
                    )

                    yield article

                except Exception as e:
                    logger.error(f"記事のスクレイピングに失敗しました: {url} - {e}")
                    continue

        except Exception as e:
            raise ScrapingError(f"スクレイピング処理に失敗しました: {e}")
