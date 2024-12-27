from datetime import date
import pytest
from unittest.mock import AsyncMock, patch
import pytest_asyncio
from ..ai_processor import ContentAnalyzer, Article


@pytest_asyncio.fixture
async def rate_limiter_mock():
    mock = AsyncMock()
    mock.acquire = AsyncMock()
    return mock


@pytest_asyncio.fixture
async def analyzer(rate_limiter_mock):
    return ContentAnalyzer("dummy_api_key", rate_limiter_mock)


@pytest.mark.asyncio
async def test_analyze_content_empty_response(analyzer):
    with patch("litellm.acompletion", return_value=None):
        genre, summary = await analyzer.analyze_content(
            Article(
                date=date(2020, 1, 1),
                title="Title",
                handle_name="User",
                genre=None,
                summary="Some summary",
                url="http://example.com",
                content="content",
            )
        )
        assert genre == "未分類"
        assert summary == "要約の生成に失敗しました"


@pytest.mark.asyncio
async def test_analyze_content_json_error(analyzer):
    mock_response = {"choices": [{"message": {"content": "Not a JSON"}}]}
    with patch("litellm.acompletion", return_value=mock_response):
        genre, summary = await analyzer.analyze_content(
            Article(
                date=date(2020, 1, 1),
                title="Title",
                handle_name="User",
                genre=None,
                summary="Some summary",
                url="http://example.com",
                content="content",
            )
        )
        assert genre == "未分類"
        assert summary == "要約の生成に失敗しました"


@pytest.mark.asyncio
async def test_analyze_content_exception(analyzer, rate_limiter_mock):
    rate_limiter_mock.acquire.side_effect = Exception("Limiter Error")
    genre, summary = await analyzer.analyze_content(
        Article(
            date=date(2020, 1, 1),
            title="Title",
            handle_name="User",
            genre=None,
            summary="Some summary",
            url="http://example.com",
            content="content",
        )
    )
    assert genre == "未分類"
    assert summary == "要約の生成に失敗しました"
