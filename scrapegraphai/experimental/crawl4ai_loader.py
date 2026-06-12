"""
Experimental: Crawl4AI backend for ScrapeGraphAI.

Crawl4AI (https://github.com/unclecode/crawl4ai) is a Python async web crawler
with advanced markdown generation, content filtering, and structured data extraction.

This loader uses Crawl4AI's AsyncWebCrawler as an alternative document fetcher,
providing clean markdown output suitable for LLM consumption.

Usage in node_config:
    "experimental": {
        "backend": "crawl4ai",
        "crawl4ai": {
            "headless": true,
            "output_format": "markdown",
            "page_timeout": 30000,
            "viewport_width": 1920,
            "viewport_height": 1080,
            "cache_mode": null
        }
    }
"""

import asyncio
from typing import Any, AsyncIterator, Iterator, List, Optional

from langchain_community.document_loaders.base import BaseLoader
from langchain_core.documents import Document

from ..utils import get_logger

logger = get_logger("crawl4ai-loader")


class Crawl4aiLoader(BaseLoader):
    """
    Document loader that fetches web pages using Crawl4AI's AsyncWebCrawler.

    Crawl4AI provides clean markdown output, content filtering, and JS rendering,
    making it an excellent alternative backend for ScrapeGraphAI.

    Attributes:
        headless: Whether to run browser in headless mode.
        page_timeout: Maximum page load time in milliseconds.
        output_format: Content format - "markdown", "html", or "text".
        urls: List of URLs to scrape.
        cache_mode: Crawl4AI cache mode (None = no cache).
        viewport: Browser viewport dimensions.
    """

    def __init__(
        self,
        urls: List[str],
        *,
        headless: bool = True,
        page_timeout: int = 30000,
        output_format: str = "markdown",
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        cache_mode: Optional[str] = None,
        proxy: Optional[dict] = None,
        **kwargs: Any,
    ):
        self.urls = urls
        self.headless = headless
        self.page_timeout = page_timeout
        self.output_format = output_format
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.cache_mode = cache_mode
        self.proxy = proxy
        self.browser_config = kwargs

    def _get_content(self, result, url: str) -> str:
        """Extract content from Crawl4AI result based on output_format."""
        if self.output_format == "markdown":
            content = getattr(result, "markdown", "") or ""
            if not content:
                content = getattr(result, "html", "") or ""
            return content
        elif self.output_format == "html":
            return getattr(result, "html", "") or ""
        elif self.output_format == "text":
            return getattr(result, "cleaned_html", "") or getattr(result, "html", "") or ""
        return getattr(result, "markdown", "") or getattr(result, "html", "") or ""

    async def afetch_page(self, url: str) -> str:
        """
        Fetch a single page using Crawl4AI.
        """
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
        except ImportError:
            raise ImportError(
                "crawl4ai is required for Crawl4aiLoader. "
                "Install it with: pip install crawl4ai"
            )

        logger.info(f"Fetching via Crawl4AI: {url}")

        browser_kwargs = {
            "headless": self.headless,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
        }
        if self.proxy:
            browser_kwargs["proxy_config"] = self.proxy

        browser_config = BrowserConfig(**browser_kwargs)

        crawler_config = CrawlerRunConfig(
            page_timeout=self.page_timeout,
            delay_before_return_html=0.5,
            verbose=False,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawler_config)

            if not result.success:
                err = getattr(result, 'error_message', '') or 'unknown error'
                logger.warning(f"Crawl4AI failed to fetch {url}: {err}")
                return ""

            content = self._get_content(result, url)
            if not content:
                logger.warning(f"Crawl4AI returned empty content for {url}")
            return content

    def lazy_load(self) -> Iterator[Document]:
        """Synchronously load documents from URLs via Crawl4AI."""
        for url in self.urls:
            html_content = asyncio.run(self.afetch_page(url))
            metadata = {"source": url, "backend": "crawl4ai", "output_format": self.output_format}
            yield Document(page_content=html_content, metadata=metadata)

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Asynchronously load documents from URLs via Crawl4AI."""
        for url in self.urls:
            html_content = await self.afetch_page(url)
            metadata = {"source": url, "backend": "crawl4ai", "output_format": self.output_format}
            yield Document(page_content=html_content, metadata=metadata)
