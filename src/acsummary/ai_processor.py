import asyncio
import json
import logging
import os
from dataclasses import asdict
from typing import Optional, Tuple

import html2text
from litellm import completion

from .models import Article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """コンテンツ分析処理で発生するエラーを表すカスタム例外"""

    pass


class ContentAnalyzer:
    def __init__(self, api_key: str):
        os.environ["GEMINI_API_KEY"] = api_key
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = True
        self.html_converter.ignore_images = True

    def _clean_html_content(self, html_content: str) -> str:
        """HTMLコンテンツをプレーンテキストに変換し、適切な長さに調整"""
        text_content = self.html_converter.handle(html_content)
        # 最初の8000文字程度を使用（コンテキストウィンドウを考慮）
        return text_content[:8000]

    def _create_analysis_prompt(self, article: Article) -> str:
        """分析用のプロンプトを生成"""
        clean_content = self._clean_html_content(article.content)
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

    async def analyze_content(self, article: Article) -> Tuple[str, str]:
        """記事の内容を分析してジャンルと要約を生成"""
        try:
            # Geminiによる分析処理
            response = await completion(
                model="gemini/gemini-pro",
                messages=[
                    {"role": "user", "content": self._create_analysis_prompt(article)}
                ],
                response_format={"type": "json_object"},
            )

            # レスポンスの解析
            if (
                not response
                or not response.choices
                or not response.choices[0].message.content
            ):
                raise AnalysisError("AIからの応答が空でした")

            try:
                result = json.loads(response.choices[0].message.content)
                genre = result.get("genre")
                summary = result.get("summary")

                if not genre or not summary:
                    raise AnalysisError("必要な情報が含まれていません")

                return genre, summary

            except json.JSONDecodeError as e:
                raise AnalysisError(f"JSONの解析に失敗しました: {e}")

        except Exception as e:
            logger.error(f"記事の分析に失敗しました: {e}")
            # 失敗した場合はデフォルト値を返す
            return "未分類", "要約の生成に失敗しました"


async def process_article(analyzer: ContentAnalyzer, article: Article) -> None:
    """1つの記事を処理し、分析結果を設定"""
    try:
        genre, summary = await analyzer.analyze_content(article)
        article.genre = genre
        article.summary = summary
        logger.info(f"記事の分析が完了しました: {article.title}")

    except Exception as e:
        logger.error(f"記事の処理に失敗しました: {article.title} - {e}")


async def process_articles(api_key: str, articles: list[Article]) -> None:
    """全ての記事を処理"""
    analyzer = ContentAnalyzer(api_key)

    for article in articles:
        await process_article(analyzer, article)
        # APIレート制限を考慮して待機
        await asyncio.sleep(1)
