from dataclasses import dataclass
import logging
from typing import Protocol, AsyncIterator
import aiohttp
from bs4 import BeautifulSoup
import html2text
from .models import Article
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContentFetcher(Protocol):
    """コンテンツ取得のインターフェース"""
    async def __aenter__(self) -> "ContentFetcher":
        """
        非同期コンテキストマネージャのエントリポイント
        """
        ...

    async def __aexit__(self, exc_type: type[BaseException] | None, 
                        exc_val: BaseException | None, 
                        exc_tb: Any) -> None:
        """
        非同期コンテキストマネージャの終了ポイント
        """
        ...

    async def fetch(self, url: str) -> str:
        """
        指定URLのコンテンツを取得
        
        Args:
            url: 取得対象のURL
            
        Returns:
            取得したコンテンツ
        """
        ...

class DefaultContentFetcher:
    """デフォルトのコンテンツ取得実装"""
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        
    async def __aenter__(self) -> "DefaultContentFetcher":
        self._session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type: type[BaseException] | None, 
                        exc_val: BaseException | None, 
                        exc_tb: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def fetch(self, url: str) -> str:
        """
        指定URLのコンテンツを取得
        
        Args:
            url: 取得対象のURL
            
        Returns:
            取得したコンテンツ
            
        Raises:
            ValueError: URLが無効な場合
            aiohttp.ClientError: リクエストに失敗した場合
        """
        if not self._session:
            raise RuntimeError("セッションが初期化されていません")
            
        if not url:
            raise ValueError("URLが指定されていません")
            
        async with self._session.get(url) as response:
            response.raise_for_status()
            return await response.text()

@dataclass
class ContentProcessor:
    """記事コンテンツの処理を行うクラス"""
    fetcher: ContentFetcher
    converter: html2text.HTML2Text
    
    def __init__(self, fetcher: ContentFetcher | None = None) -> None:
        """
        ContentProcessorの初期化
        
        Args:
            fetcher: コンテンツ取得に使用するフェッチャー。
                    Noneの場合はDefaultContentFetcherを使用
        """
        self.fetcher = fetcher or DefaultContentFetcher()
        self.converter = html2text.HTML2Text()
        # リンクと画像は無視（テキストのみを抽出）
        self.converter.ignore_links = True
        self.converter.ignore_images = True
        
    async def process_articles(self, articles: list[Article]) -> AsyncIterator[Article]:
        """
        記事のコンテンツを取得・処理
        
        Args:
            articles: 処理対象の記事リスト
            
        Yields:
            Article: コンテンツを取得・処理した記事
        """
        async with self.fetcher:
            for article in articles:
                try:
                    # コンテンツを取得
                    html_content = await self.fetcher.fetch(article.url)
                    
                    # タイトルと本文を抽出
                    title, content = self._extract_content(html_content)
                    
                    # 記事オブジェクトを更新
                    article.title = title
                    article.content = self._clean_content(content)
                    
                    yield article
                    
                except Exception as e:
                    logger.error(f"記事のコンテンツ取得に失敗しました: {article.url} - {e}")
                    # エラーの場合も記事は yield するが、contentは None のまま
                    yield article
    
    def _extract_content(self, html: str) -> tuple[str, str]:
        """
        HTMLからタイトルと本文を抽出
        
        Args:
            html: 抽出対象のHTML文字列
            
        Returns:
            (タイトル, 本文)のタプル
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # タイトルを抽出（h1, title の順で探す）
        title_elem = (
            soup.find('h1') or 
            soup.find('title') or 
            soup.find('meta', {'property': 'og:title'})
        )
        title = title_elem.text.strip() if title_elem else ""
        
        # 本文を抽出（article, main, divの順で探す）
        content_elem = (
            soup.find('article') or 
            soup.find('main') or 
            soup.find('div', {'class': ['content', 'article', 'entry-content', 'post-content']})
        )
        content = content_elem.get_text() if content_elem else ""
        
        return title, content
    
    def _clean_content(self, content: str) -> str:
        """
        コンテンツを整形
        
        Args:
            content: 整形対象のコンテンツ文字列
            
        Returns:
            整形後のコンテンツ文字列
        """
        # HTMLをプレーンテキストに変換
        text = self.converter.handle(content)
        
        # 空行の削除と行の結合
        lines = [line.strip() for line in text.splitlines()]
        text = ' '.join(line for line in lines if line)
        
        # コンテキストウィンドウを考慮して長さを制限
        return text[:8000]  # GPTのコンテキストウィンドウに収まる長さ