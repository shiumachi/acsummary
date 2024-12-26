import json
import logging
from typing import TypeAlias, Any
import os

import html2text
from litellm import acompletion
from .models import Article
from .rate_limiter import RateLimiter

# 型エイリアスの定義
JsonDict: TypeAlias = dict[str, Any]
CompletionResponse: TypeAlias = Any  # litellmの戻り値の型

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """コンテンツ分析処理で発生するエラーを表すカスタム例外"""


class ContentAnalyzer:
    content_size_max: int = 524288

    def __init__(self, api_key: str, rate_limiter: RateLimiter) -> None:
        """
        ContentAnalyzerの初期化

        Args:
            api_key: Gemini APIのキー
            rate_limiter: リクエストのレート制限を管理するインスタンス
        """
        os.environ["GEMINI_API_KEY"] = api_key
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = True
        self.html_converter.ignore_images = True
        self.rate_limiter = rate_limiter

    def _clean_html_content(self, html_content: str) -> str:
        """
        HTMLコンテンツをプレーンテキストに変換し、適切な長さに調整

        Args:
            html_content: 変換対象のHTML文字列

        Returns:
            変換・調整済みのプレーンテキスト
        """
        text_content = self.html_converter.handle(html_content)
        return text_content[: self.content_size_max]

    def _create_analysis_prompt(self, article: Article) -> str:
        """
        分析用のプロンプトを生成

        Args:
            article: 分析対象の記事

        Returns:
            生成されたプロンプト文字列
        """
        clean_content = self._clean_html_content(article.content or "")
        return f"""以下の技術ブログ記事を分析し、ジャンルと要約を生成してください。

記事タイトル: {article.title}
投稿者: {article.handle_name}
投稿日: {article.date}
コメント: {article.summary if article.summary else 'なし'}

記事本文:
{clean_content}

以下の形式のJSONで出力してください:
{{
    "genre": "記事の主なジャンル（技術カテゴリ）を1つ選択",
    "summary": "記事の主要なポイントを300字程度で要約"
}}

ジャンルの例:
- プログラミング（Python, Go, JavaScriptなど）
- インフラ・運用（AWS, Docker, Kubernetes など）
- 機械学習・AI
- セキュリティ
- 開発手法・プロジェクト管理
- キャリア・組織
- ライフハック
- レビュー・トラブルシューティング
"""

    async def analyze_content(self, article: Article) -> tuple[str, str]:
        """
        記事の内容を分析してジャンルと要約を生成

        Args:
            article: 分析対象の記事

        Returns:
            ジャンルと要約のタプル

        Raises:
            AnalysisError: 分析処理に失敗した場合
        """
        try:
            # レート制限に従ってリクエストを実行
            await self.rate_limiter.acquire()

            response: CompletionResponse = await acompletion(
                model="gemini/gemini-2.0-flash-exp",
                messages=[
                    {"role": "user", "content": self._create_analysis_prompt(article)}
                ],
                response_format={"type": "json_object"},
            )

            if (
                not response
                or not response.choices
                or not response.choices[0].message.content
            ):
                raise AnalysisError("AIからの応答が空でした")

            try:
                result: JsonDict = json.loads(response.choices[0].message.content)
                genre: str | None = result.get("genre")
                summary: str | None = result.get("summary")

                if not genre or not summary:
                    raise AnalysisError("必要な情報が含まれていません")

                return genre, summary

            except json.JSONDecodeError as e:
                raise AnalysisError(f"JSONの解析に失敗しました: {e}")

        except Exception as e:
            logger.error(f"記事の分析に失敗しました: {e}")
            return "未分類", "要約の生成に失敗しました"


async def process_article(analyzer: ContentAnalyzer, article: Article) -> None:
    """
    1つの記事を処理し、分析結果を設定

    Args:
        analyzer: 分析を行うContentAnalyzerインスタンス
        article: 処理対象の記事
    """
    try:
        genre, summary = await analyzer.analyze_content(article)
        article.genre = genre
        article.summary = summary
        logger.info(f"記事の分析が完了しました: {article.title}")

    except Exception as e:
        logger.error(f"記事の処理に失敗しました: {article.title} - {e}")


async def process_articles(api_key: str, articles: list[Article]) -> None:
    """
    全ての記事を処理

    Args:
        api_key: Gemini APIのキー
        articles: 処理対象の記事リスト
    """
    # 10秒に1リクエストの制限を設定
    rate_limiter = RateLimiter(requests_per_period=1, period_seconds=10.0)
    analyzer = ContentAnalyzer(api_key, rate_limiter)

    for article in articles:
        await process_article(analyzer, article)
