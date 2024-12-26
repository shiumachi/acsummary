import asyncio
import logging
from pathlib import Path
import click
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .scraper import AdventCalendarScraper
from .content_processor import ContentProcessor
from .ai_processor import process_articles
from .csv_writer import CSVWriter
from .models import Article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def collect_articles(scraper: AdventCalendarScraper) -> list[Article]:
    """
    スクレイパーを使って記事を収集
    
    Args:
        scraper: 使用するスクレイパーインスタンス
        
    Returns:
        収集した記事のリスト
    """
    articles: list[Article] = []
    async with scraper:
        async for article in scraper.scrape_articles():
            articles.append(article)
    return articles

async def process_content(processor: ContentProcessor, articles: list[Article]) -> list[Article]:
    """
    記事のコンテンツを取得・処理
    
    Args:
        processor: コンテンツ処理に使用するプロセッサ
        articles: 処理対象の記事リスト
        
    Returns:
        処理済みの記事リスト
    """
    processed_articles: list[Article] = []
    async for article in processor.process_articles(articles):
        processed_articles.append(article)
    return processed_articles

async def process_calendar(calendar_url: str, output_path: str, api_key: str) -> None:
    """
    アドベントカレンダーの処理メイン関数
    
    Args:
        calendar_url: アドベントカレンダーのURL
        output_path: 出力CSVのパス
        api_key: Gemini APIのキー
    """
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
        ) as progress:
            # 記事の収集
            progress.add_task(description="記事を収集中...", total=None)
            scraper = AdventCalendarScraper(calendar_url)
            articles = await collect_articles(scraper)
            
            if not articles:
                logger.warning("記事が見つかりませんでした")
                return
            
            # コンテンツの取得・処理
            progress.add_task(description="記事のコンテンツを取得中...", total=None)
            processor = ContentProcessor()
            articles_with_content = await process_content(processor, articles)
                
            # AI処理
            progress.add_task(description="記事を分析中...", total=None)
            await process_articles(api_key, articles_with_content)
            
            # CSV出力用のディレクトリを作成
            output_path_path = Path(output_path)
            output_path_path.parent.mkdir(parents=True, exist_ok=True)
            
            # CSV出力
            progress.add_task(description="CSVに出力中...", total=None)
            CSVWriter.write_articles(articles_with_content, output_path)
            
            logger.info(f"処理が完了しました。出力先: {output_path}")
            
    except Exception as e:
        logger.error(f"処理に失敗しました: {e}")
        raise click.ClickException(str(e))

@click.command()
@click.argument('calendar_url', type=str)
@click.argument('output_path', type=str)
@click.option('--api-key', required=True, help='Gemini API Key')
def main(calendar_url: str, output_path: str, api_key: str) -> None:
    """
    アドベントカレンダーの記事を要約してCSVに出力
    
    Args:
        calendar_url: アドベントカレンダーのURL
        output_path: 出力CSVのパス
        api_key: Gemini APIのキー
    """
    try:
        asyncio.run(process_calendar(calendar_url, output_path, api_key))
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
        raise click.ClickException(str(e))

if __name__ == '__main__':
    main()