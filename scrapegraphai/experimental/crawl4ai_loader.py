"""
Experimental: Crawl4AI backend for ScrapeGraphAI.

Crawl4AI (https://github.com/unclecode/crawl4ai) is a Python async web crawler
with advanced markdown generation, content filtering, and structured data extraction.

This loader uses Crawl4AI's AsyncWebCrawler as an alternative document fetcher,
providing clean markdown output suitable for LLM consumption.

If Crawl4AI fails due to anti-bot protection (e.g. Cloudflare), the loader
automatically falls back to launching a stealth-hardened Chrome instance via
Playwright + Malenia and connecting Crawl4AI to it via CDP.

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
import os
import subprocess
import tempfile
import time
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
        page_timeout: int = 60000,
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

    def _ensure_chrome_with_cdp(self):
        """Launch Chrome with remote debugging port for stealth CDP mode."""
        chrome_paths = [
            "chrome", "chromium", "google-chrome", "google-chrome-stable",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        chrome_bin = None
        for cmd in chrome_paths:
            try:
                if cmd.startswith("C:") and os.path.isfile(cmd):
                    chrome_bin = cmd
                    break
                subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
                chrome_bin = cmd
                break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        if chrome_bin is None:
            return None, None

        user_data_dir = tempfile.mkdtemp(prefix="crawl4ai_")
        debug_port = 9223  # use different port to avoid conflicts

        args = [
            chrome_bin,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-web-security",
        ]
        if self.headless:
            args.append("--headless")

        proc = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        cdp_url = f"ws://127.0.0.1:{debug_port}/devtools/browser"
        for _ in range(15):
            time.sleep(1)
            try:
                import urllib.request, json
                resp = urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json/version", timeout=3)
                info = json.loads(resp.read())
                if "webSocketDebuggerUrl" in info:
                    cdp_url = info["webSocketDebuggerUrl"]
                    break
            except Exception:
                continue

        logger.info(f"Chrome CDP ready at {cdp_url}")
        return proc, cdp_url

    async def _afetch_with_cdp_stealth(self, url: str) -> str:
        """Fetch via Crawl4AI connected to our own stealth Chrome via CDP."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        chrome_proc, cdp_url = self._ensure_chrome_with_cdp()
        if chrome_proc is None:
            return ""

        try:
            browser_config = BrowserConfig(
                use_managed_browser=True,
                cdp_url=cdp_url,
                headless=self.headless,
                viewport_width=self.viewport_width,
                viewport_height=self.viewport_height,
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            )
            crawler_config = CrawlerRunConfig(
                page_timeout=self.page_timeout,
                delay_before_return_html=4.0,
                verbose=False,
            )
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=crawler_config)
                if result.success:
                    return self._get_content(result, url)
                err = getattr(result, 'error_message', '') or 'unknown error'
                logger.warning(f"Crawl4AI CDP stealth also failed for {url}: {err}")
                return ""
        finally:
            try:
                chrome_proc.terminate()
                chrome_proc.wait(timeout=5)
            except Exception:
                pass

    async def afetch_page(self, url: str) -> str:
        """
        Fetch a single page using Crawl4AI.
        Falls back to CDP stealth mode if anti-bot protection is detected.
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
            "enable_stealth": True,
            "ignore_https_errors": True,
            "extra_args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            "headers": {
                "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
            },
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        }
        if self.proxy:
            browser_kwargs["proxy_config"] = self.proxy

        browser_config = BrowserConfig(**browser_kwargs)

        crawler_config = CrawlerRunConfig(
            page_timeout=self.page_timeout,
            delay_before_return_html=4.0,
            verbose=False,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawler_config)

            if result.success:
                content = self._get_content(result, url)
                if not content:
                    logger.warning(f"Crawl4AI returned empty content for {url}")
                return content

            err = getattr(result, 'error_message', '') or 'unknown error'
            logger.warning(f"Crawl4AI failed to fetch {url}: {err}")

            # If blocked by anti-bot, try CDP stealth fallback
            is_blocked = "blocked" in err.lower() or "cloudflare" in err.lower() or "challenge" in err.lower()
            if is_blocked:
                logger.info(f"Crawl4AI blocked for {url}, trying CDP stealth fallback...")
                content = await self._afetch_with_cdp_stealth(url)
                if content:
                    logger.info(f"CDP stealth fallback succeeded for {url}")
                    return content
                logger.warning(f"Crawl4AI CDP fallback also blocked for {url}")

            return ""

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
