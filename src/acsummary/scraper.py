from abc import ABC
from datetime import date
from typing import AsyncIterator, Protocol, Any, NamedTuple
from urllib.parse import urlparse
import logging
import aiohttp
from bs4 import BeautifulSoup

from .models import Article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScrapingError(Exception):
    """スクレイピング処理で発生するエラーを表すカスタム例外"""


class ArticleEntry(NamedTuple):
    """記事エントリーの情報を表す型定義"""

    entry_date: date
    handle_name: str
    url: str
    comment: str | None


class CalendarScraper(Protocol):
    """カレンダーのスクレイピングを行うインターフェース"""

    async def __aenter__(self) -> "CalendarScraper":
        """非同期コンテキストマネージャのエントリーポイント"""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,  # noqa: ANN401
    ) -> None:
        """非同期コンテキストマネージャの終了処理"""
        ...

    async def scrape_articles(self) -> AsyncIterator[Article]:
        """
        カレンダーの記事をスクレイピング

        Yields:
            Article: スクレイピングした記事情報
        """
        ...


class BaseCalendarScraper(ABC):
    """カレンダースクレイパーの基底クラス"""

    def __init__(self, calendar_url: str) -> None:
        """
        BaseCalendarScraperの初期化

        Args:
            calendar_url: スクレイピング対象のカレンダーURL
        """
        self.calendar_url = calendar_url
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "BaseCalendarScraper":
        """非同期コンテキストマネージャのエントリーポイント"""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,  # noqa: ANN401
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

    async def scrape_articles(self) -> AsyncIterator[Article]:
        """
        カレンダーの記事をスクレイピング

        Yields:
            Article: スクレイピングした記事情報

        Raises:
            ScrapingError: スクレイピングに失敗した場合
        """
        try:
            calendar_html = await self._fetch_page(self.calendar_url)
            entries = self._parse_calendar_page(calendar_html)

            for entry_date, handle_name, url, comment in entries:
                try:
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

    def _parse_calendar_page(self, html: str) -> list[ArticleEntry]:
        """
        カレンダーページからエントリー情報を抽出
        具象クラスで実装する必要がある

        Args:
            html: パース対象のHTML文字列

        Returns:
            ArticleEntryのリスト

        Raises:
            NotImplementedError: 具象クラスで実装されていない場合
        """
        raise NotImplementedError


class AdventarCalendarScraper(BaseCalendarScraper):
    """Adventar形式のカレンダーに対応したスクレイパー"""

    def _parse_calendar_page(self, html: str) -> list[ArticleEntry]:
        """
        Adventarのカレンダーページからエントリー情報を抽出

        Args:
            html: パース対象のHTML文字列

        Returns:
            ArticleEntryのリスト

        Raises:
            ScrapingError: パースに失敗した場合
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            entries: list[ArticleEntry] = []

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
                entries.append(
                    ArticleEntry(
                        entry_date=entry_date,
                        handle_name=handle_name,
                        url=url,
                        comment=comment,
                    )
                )

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


class QiitaCalendarScraper(BaseCalendarScraper):
    """Qiita形式のカレンダーに対応したスクレイパー"""

    def _parse_calendar_page(self, html: str) -> list[ArticleEntry]:
        """
        Qiitaのカレンダーページからエントリー情報を抽出

        Args:
            html: パース対象のHTML文字列

        Returns:
            ArticleEntryのリスト

        Raises:
            ScrapingError: パースに失敗した場合
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            entries: list[ArticleEntry] = []
            calendar_section = soup.find("section", class_="style-t7g594")
            if not calendar_section:
                raise ScrapingError("カレンダーセクションが見つかりませんでした")

            # シリーズ1のテーブルを取得
            calendar_table = calendar_section.find("table", class_="style-1lopqp4")
            if not calendar_table:
                raise ScrapingError("カレンダーテーブルが見つかりませんでした")

            # カレンダーのテーブル行を取得（ヘッダー行を除く）
            calendar_rows = calendar_table.find("tbody").find_all(
                "tr", class_="style-8kv4rj"
            )

            for row in calendar_rows:
                # 各日のセルを処理
                cells = row.find_all("td", class_="style-1dw8kp9")
                for cell_index, cell in enumerate(cells, start=1):
                    # 記事コンテナを取得
                    article_container = cell.find("div", class_="style-176zglo")
                    if not article_container:
                        continue

                    # 記事リンクを取得（これが存在する場合のみ記事が投稿されている）
                    article_link = article_container.find("a", class_="style-14mbwqe")
                    if not article_link or not article_link.get("href"):
                        continue

                    # 投稿者名を取得
                    author_link = article_container.find("a", class_="style-zfknvc")
                    if not author_link:
                        continue

                    handle_name = author_link.text.strip().replace("@", "")
                    url = article_link["href"]
                    title = article_link.text.strip()

                    # 日付計算: 行番号と列番号から日付を計算
                    day = (calendar_rows.index(row) * 7) + cell_index
                    entry_date = date(2024, 12, day)  # 年月は固定

                    entries.append(
                        ArticleEntry(
                            entry_date=entry_date,
                            handle_name=handle_name,
                            url=url,
                            comment=title,  # コメントの代わりにタイトルを使用
                        )
                    )

            if not entries:
                logger.warning("投稿された記事が見つかりませんでした")

            return entries

        except Exception as e:
            logger.error(f"Qiitaカレンダーページのパースに失敗しました: {e}")
            raise ScrapingError(f"Qiitaカレンダーページのパースに失敗しました: {e}")


def create_scraper(calendar_url: str) -> BaseCalendarScraper:
    """
    URLに応じた適切なスクレイパーを生成するファクトリ関数

    Args:
        calendar_url: スクレイピング対象のカレンダーURL

    Returns:
        適切なCalendarScraperのインスタンス

    Raises:
        ValueError: 未対応のドメインの場合
    """
    domain = urlparse(calendar_url).netloc

    if "adventar.org" in domain:
        return AdventarCalendarScraper(calendar_url)
    elif "qiita.com" in domain:
        return QiitaCalendarScraper(calendar_url)
    else:
        raise ValueError(f"未対応のドメインです: {domain}")
