import asyncio
import subprocess
import time
from typing import Any, AsyncIterator, Iterator, List, Optional

from langchain_community.document_loaders.base import BaseLoader
from langchain_core.documents import Document

from ..utils import get_logger

logger = get_logger("obscura-loader")

DEFAULT_CDP_URL = "ws://127.0.0.1:9222/devtools/browser"
OBSCURA_DOCKER_IMAGE = "h4ckf0r0day/obscura"
OBSCURA_DOCKER_CMD = [
    "docker", "run", "-d", "--rm",
    "--name", "scrapegraph-obscura",
    "-p", "127.0.0.1:9222:9222",
    OBSCURA_DOCKER_IMAGE,
]


class ObscuraLoader(BaseLoader):
    """
    Fetches web pages using Obscura headless browser via CDP.

    Supports three start modes:
      - "manual" (default): connect to an already-running Obscura instance.
      - "docker": auto-start Obscura via Docker.
      - "subprocess": auto-start Obscura binary as a subprocess.

    Usage in node_config:
        "experimental": {
            "backend": "obscura",
            "obscura": {
                "cdp_url": "ws://127.0.0.1:9222/devtools/browser",
                "auto_start": "docker",
                "timeout": 30
            }
        }
    """

    def __init__(
        self,
        urls: List[str],
        *,
        cdp_url: str = DEFAULT_CDP_URL,
        headless: bool = True,
        timeout: int = 30,
        storage_state: Optional[str] = None,
        auto_start: Optional[str] = None,
        proxy: Optional[dict] = None,
        **kwargs: Any,
    ):
        self.urls = urls
        self.cdp_url = cdp_url
        self.headless = headless
        self.timeout = timeout
        self.storage_state = storage_state
        self.auto_start = auto_start
        self.proxy = proxy
        self.browser_config = kwargs
        self._process = None

    def _start_docker(self):
        """Start Obscura via Docker."""
        logger.info("Starting Obscura via Docker...")
        try:
            subprocess.run(
                ["docker", "stop", "scrapegraph-obscura"],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass
        result = subprocess.run(OBSCURA_DOCKER_CMD, capture_output=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to start Obscura Docker container: "
                f"{result.stderr.decode().strip() or result.stdout.decode().strip()}"
            )
        logger.info("Obscura Docker container started, waiting for CDP...")
        time.sleep(2)

    def _start_subprocess(self):
        """Start Obscura binary as a subprocess."""
        logger.info("Starting Obscura as subprocess...")
        try:
            self._process = subprocess.Popen(
                ["obscura", "serve", "--port", "9222"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(2)
        except FileNotFoundError:
            raise RuntimeError(
                "Obscura binary not found in PATH. "
                "Download from https://github.com/h4ckf0r0day/obscura/releases"
            )

    def _ensure_running(self):
        """Ensure Obscura is running, auto-starting if configured."""
        if self.auto_start == "docker":
            self._start_docker()
        elif self.auto_start == "subprocess":
            self._start_subprocess()
        elif self.auto_start is not None:
            raise ValueError(f"Unknown auto_start mode: {self.auto_start}")

    def _cleanup(self):
        """Clean up any started processes."""
        if self._process is not None:
            self._process.terminate()
            self._process = None
        if self.auto_start == "docker":
            try:
                subprocess.run(
                    ["docker", "stop", "scrapegraph-obscura"],
                    capture_output=True, timeout=10,
                )
            except Exception:
                pass

    async def afetch_page(self, url: str) -> str:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "playwright is required for ObscuraLoader. "
                "Install it with: pip install playwright"
            )

        logger.info(f"Fetching via Obscura CDP: {url}")
        self._ensure_running()
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(self.cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context(
                storage_state=self.storage_state,
                ignore_https_errors=True,
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            content = await page.content()
            await page.close()
            return content

    def lazy_load(self) -> Iterator[Document]:
        try:
            for url in self.urls:
                html_content = asyncio.run(self.afetch_page(url))
                metadata = {"source": url, "backend": "obscura"}
                yield Document(page_content=html_content, metadata=metadata)
        finally:
            self._cleanup()

    async def alazy_load(self) -> AsyncIterator[Document]:
        try:
            for url in self.urls:
                html_content = await self.afetch_page(url)
                metadata = {"source": url, "backend": "obscura"}
                yield Document(page_content=html_content, metadata=metadata)
        finally:
            self._cleanup()
