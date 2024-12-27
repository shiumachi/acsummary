import pytest
import pytest_asyncio
from datetime import date
from unittest.mock import patch
from ..scraper import AdventCalendarScraper, ScrapingError
from ..models import Article


@pytest_asyncio.fixture
async def scraper():
    async with AdventCalendarScraper("http://fake.url") as s:
        yield s


@pytest.mark.asyncio
async def test_scrape_articles_success(scraper):
    mock_entries = [
        (date(2024, 12, 1), "test_user", "http://example.com", "test_comment")
    ]
    with (
        patch.object(scraper, "_fetch_page", return_value="fake_html") as mock_fetch,
        patch.object(
            scraper, "_parse_calendar_page", return_value=mock_entries
        ) as mock_parse,
    ):
        results = []
        async for article in scraper.scrape_articles():
            results.append(article)

        assert len(results) == 1
        assert isinstance(results[0], Article)
        assert results[0].handle_name == "test_user"
        mock_fetch.assert_called_once()
        mock_parse.assert_called_once()


@pytest.mark.asyncio
async def test_scrape_articles_scraping_error(scraper):
    with patch.object(scraper, "_fetch_page", side_effect=Exception("Error")):
        with pytest.raises(ScrapingError):
            async for _ in scraper.scrape_articles():
                pass
